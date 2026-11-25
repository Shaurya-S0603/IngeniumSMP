"""IngeniumBot and local Minecraft supervisor."""
import asyncio, contextlib, datetime, hashlib, json, os, re, shutil, socket, uuid
from pathlib import Path
from collections import deque
import sys, threading
import discord
from discord import app_commands
from dotenv import load_dotenv
from mcstatus import JavaServer
from backup_manager import due, snapshot

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "server"
CONFIG = ROOT / "config.json"
NAME = re.compile(r"[A-Za-z0-9_]{1,16}\Z")
LOG = re.compile(r"^\[.*?\]\s*(?:\[[^\]]+\]\s*)+(?::\s*|\s+)(.*)$")
CHAT = re.compile(r"^(?:\[Not Secure\]\s*)?<([A-Za-z0-9_]{1,16})> (.*)$")
JOIN = re.compile(r"^([A-Za-z0-9_]{1,16}) (joined|left) the game$")
NO_MENTIONS = discord.AllowedMentions.none()


@contextlib.contextmanager
def runtime_guard(path):
    """Keep an OS-level lock for the life of the supervisor; never unlink it."""
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "r+b", buffering=0) as handle:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            raise RuntimeError("Another Ingenium host may be running. Stop it before launching again.") from e
        try:
            handle.seek(0)
            previous = handle.read()
            if previous and previous != b"INGENIUM_LOCK_V2\n":
                raise RuntimeError("Legacy runtime.lock detected. Verify that all old Ingenium Python and Java processes have stopped, then remove runtime.lock once and retry.")
            handle.seek(0)
            handle.write(b"INGENIUM_LOCK_V2\n")
            handle.truncate()
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

def require_free_port():
    # Catch a surviving Java process or another service before touching config.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", 25565)) == 0:
            raise RuntimeError("Port 25565 is already accepting connections. Stop the existing server before starting Ingenium.")

def load_config():
    c = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not 2 <= int(c["max_ram_gb"]) <= 12:
        raise ValueError("RAM must be between 2 and 12 GB")
    return c

def offline_uuid(name):
    return str(uuid.UUID(bytes=hashlib.md5(("OfflinePlayer:"+name).encode()).digest(),version=3))

def relay(author, message):
    def clean(s, limit):
        return "".join(ch if ch.isprintable() else " " for ch in s)[:limit]
    return "tellraw @a "+json.dumps({"text":"[Discord] "+clean(author,60)+": "+clean(message,400),"color":"aqua"},ensure_ascii=True)

def parse_line(line):
    # Support legacy and several newer log prefixes; live validation required.
    body=line.strip()
    if "]:" in body:
        body=body.split("]:",1)[1].strip()
    elif LOG.match(body):
        body=LOG.match(body).group(1)
    if body.startswith("System chat: "):
        body=body[13:]
    m=CHAT.fullmatch(body)
    if m and not m[2].lstrip().startswith("/"):
        return ("chat",m[1],m[2])
    m=JOIN.fullmatch(body)
    if m:
        return (m[2],m[1],"")
    return None

class Host:
    def __init__(self, cfg):
        self.cfg=cfg
        self.proc=None
        self.desired=False
        self.lock=asyncio.Lock()
        self.maintenance=asyncio.Lock()
        self.monitor=None
        self.bot=None
        self.closing=False
        self.ready=False
        self.failures=0
        self.last_start=0
        self.console_lines=deque(maxlen=200)

    async def send_channel(self, key, text):
        if not self.bot or not self.bot.is_ready():
            return
        channel=self.bot.get_channel(int(self.cfg.get(key,0)))
        if channel and getattr(channel,"guild",None) and channel.guild.id==self.cfg["guild_id"]:
            with contextlib.suppress(discord.HTTPException):
                await channel.send(discord.utils.escape_markdown(text)[:1900],allowed_mentions=NO_MENTIONS)

    def preflight(self):
        if not (SERVER/"world"/"level.dat").is_file():
            raise RuntimeError("Import the Aternos world first.")
        if not (SERVER/"server.jar").is_file():
            raise RuntimeError("Install the Fabric 26.3 launcher as server/server.jar.")
        if not any("easyauth" in p.name.lower() for p in (SERVER/"mods").glob("*.jar")):
            raise RuntimeError("EasyAuth jar missing; refusing offline-mode startup.")
        if "eula=true" not in (SERVER/"eula.txt").read_text().splitlines():
            raise RuntimeError("Read and explicitly accept the Minecraft EULA.")
        props={}
        for line in (SERVER/"server.properties").read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k,v=line.split("=",1); props[k]=v
        props.update({"server-ip":"127.0.0.1","server-port":"25565","online-mode":"false","enforce-secure-profile":"false","white-list":"false","enforce-whitelist":"false","enable-rcon":"false","enable-query":"false","level-name":"world","max-players":"10","pause-when-empty-seconds":"-1"})
        (SERVER/"server.properties").write_text("\n".join(k+"="+v for k,v in props.items())+"\n",encoding="utf-8")
        # Preserve any existing whitelist.json; access is disabled at startup.
        # No offline-mode in-game operator accounts.
        (SERVER/"ops.json").write_text("[]\n",encoding="utf-8")

    async def start(self):
        async with self.lock:
            if self.closing:
                return "Host is shutting down."
            if self.proc and self.proc.returncode is None:
                return "Minecraft is already running or starting."
            require_free_port()
            self.preflight()
            ram=int(self.cfg["max_ram_gb"])
            self.proc=await asyncio.create_subprocess_exec(self.cfg["java"],"-Xms2G",f"-Xmx{ram}G","-jar","server.jar","nogui",cwd=SERVER,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
            self.desired=True
            self.ready=False
            self.last_start=asyncio.get_running_loop().time()
            self.monitor=asyncio.create_task(self.watch(self.proc))
            return "Minecraft startup initiated."

    async def command(self, cmd):
        if "\n" in cmd or "\r" in cmd:
            raise ValueError("Multiline command rejected")
        p=self.proc
        if not p or p.returncode is not None or not p.stdin:
            raise RuntimeError("Minecraft is not running.")
        p.stdin.write((cmd+"\n").encode("utf-8"))
        await p.stdin.drain()

    async def stop(self):
        async with self.lock:
            self.desired=False
            p=self.proc
            if not p or p.returncode is not None:
                return "Minecraft is already stopped."
            await self.command("stop")
            try:
                await asyncio.wait_for(p.wait(),90)
            except asyncio.TimeoutError:
                return "Stop requested, but Java is still running. Inspect the local console; no force kill was attempted."
            return "Minecraft stopped safely."

    async def watch(self,p):
        while True:
            line=await p.stdout.readline()
            if not line: break
            s=line.decode("utf-8",errors="replace").rstrip()
            print(s,flush=True)
            self.console_lines.append(s[:2000])
            if "Done (" in s and "help" in s.lower():
                self.ready=True
                asyncio.create_task(self.send_channel("status_channel_id","Minecraft is ready."))
            ev=parse_line(s)
            if ev:
                kind,name,msg=ev
                text=f"{name}: {msg}" if kind=="chat" else f"{name} {kind} the game."
                asyncio.create_task(self.send_channel("chat_channel_id",text))
        code=await p.wait()
        if self.proc is not p:
            return
        self.ready=False
        await self.send_channel("status_channel_id",f"Minecraft stopped (exit {code}).")
        if self.proc is p and self.desired and not self.closing:
            elapsed=asyncio.get_running_loop().time()-self.last_start
            self.failures=0 if elapsed>300 else self.failures+1
            if self.failures>3:
                self.desired=False
                await self.send_channel("status_channel_id","Crash recovery paused after repeated failures.")
                return
            await asyncio.sleep(10*self.failures+5)
            async with self.maintenance:
                if self.proc is p and self.desired and not self.closing:
                    try: await self.start()
                    except Exception as e:
                        self.desired=False
                        await self.send_channel("status_channel_id","Restart failed; check local console.")
                        print("Restart failed:",e)

    async def console_command(self, raw):
        """Call with the maintenance lock held; never expose stdin publicly."""
        cmd=raw.strip()
        if cmd.startswith("/"):
            cmd=cmd[1:].strip()
        if not cmd or len(cmd)>1000 or any(ord(ch)<32 for ch in cmd):
            raise ValueError("Enter one nonempty Minecraft command (up to 1000 characters).")
        if self.closing:
            return "Host is shutting down."
        verb=cmd.split(None,1)[0].lower()
        if cmd.lower() in ("stop","minecraft:stop"):
            return await self.stop()
        if verb in ("stop","minecraft:stop"):
            return "Use stop without arguments."
        if cmd.lower()==":start":
            return await self.start()
        if cmd.lower()==":restart":
            await self.stop()
            if self.proc and self.proc.returncode is None:
                return "Restart deferred: Java has not stopped."
            return await self.start()
        if cmd.lower()==":backup":
            return await self.backup()
        if cmd.lower()==":status":
            return await self.status()
        if not self.ready:
            return "Minecraft is not ready. Use :start or wait for startup."
        await self.command(cmd)
        return "Command sent to Minecraft. Read the local console or /console_logs for output."

    def console_tail(self, count=20):
        """Bounded, best-effort filtered log excerpt for private staff responses."""
        count=max(1,min(50,count))
        lines=[]
        for line in list(self.console_lines)[-count:]:
            if re.search(r"(?i)(password|passwd|token|secret|credential|/register\b|/login\b|easyauth|authme|authorization|api[_ -]?key)",line):
                lines.append("[Sensitive authentication-related line omitted]")
            else:
                lines.append(discord.utils.escape_markdown(line,as_needed=False))
        return ("\n".join(lines)[-1650:] or "No recent Minecraft console output.") 

    async def status(self):
        try:
            s=await asyncio.to_thread(lambda:JavaServer.lookup("127.0.0.1:25565",timeout=3).status())
            return f"Online | {s.players.online}/{s.players.max} players | {s.version.name} | {s.latency:.0f} ms"
        except Exception:
            return "Starting or not responding." if self.proc and self.proc.returncode is None else "Offline"

    async def backup(self, automatic=False):
        """Serialize with staff operations via maintenance lock in caller."""
        if self.closing:
            return "Host is shutting down."
        running = self.proc is not None and self.proc.returncode is None
        if running:
            if not self.ready:
                return "Backup deferred: server is still starting."
            try:
                for n in range(2):
                    s=await asyncio.to_thread(lambda:JavaServer.lookup("127.0.0.1:25565",timeout=3).status())
                    if s.players.online:
                        return "Backup deferred: players are online."
                    if n==0:
                        await asyncio.sleep(10)
            except Exception:
                return "Backup deferred: player count unavailable."
        try:
            if running:
                await self.stop()
                if self.proc.returncode is None:
                    return "Backup deferred: Minecraft has not stopped."
                if self.proc.returncode != 0:
                    return "Backup deferred: Minecraft did not exit cleanly."
            elif self.desired:
                return "Backup deferred: crash recovery pending."
            async with self.lock:
                require_free_port()
                task=asyncio.create_task(asyncio.to_thread(snapshot, SERVER, ROOT/"backups", automatic, 7))
                try:
                    path=await asyncio.shield(task)
                except asyncio.CancelledError:
                    # A worker thread cannot be cancelled. Wait before allowing a new server.
                    await task
                    raise
            return "Verified local backup created: "+path.name
        finally:
            if running and not self.closing and self.proc.returncode is not None:
                try:
                    print(await self.start())
                except Exception as e:
                    print("Restart after backup failed:",e)
                    await self.send_channel("status_channel_id","Minecraft restart after backup failed; check host console.")

    async def scheduled_backups(self):
        await asyncio.sleep(60)
        while not self.closing:
            try:
                if self.cfg.get("automatic_backups",True) and due(ROOT/"backups"):
                    async with self.maintenance:
                        if not self.closing:
                            result=await self.backup(automatic=True)
                            print(result,flush=True)
                            if result.startswith("Verified"):
                                await self.send_channel("status_channel_id",result)
            except Exception as e:
                print("Automatic backup failed:",e,flush=True)
                await self.send_channel("status_channel_id","Automatic backup failed; inspect host console.")
            await asyncio.sleep(300)

class Ingenium(discord.Client):
    def __init__(self,host):
        intents=discord.Intents.default()
        intents.message_content=True
        super().__init__(intents=intents,allowed_mentions=NO_MENTIONS)
        self.host=host
        self.tree=app_commands.CommandTree(self)

    async def setup_hook(self):
        guild=discord.Object(id=self.host.cfg["guild_id"])
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self):
        print("IngeniumBot connected as",self.user)

    async def on_message(self,message):
        h=self.host
        if message.author.bot or message.webhook_id or not message.guild or message.guild.id!=h.cfg["guild_id"] or message.channel.id!=h.cfg["chat_channel_id"] or not h.ready:
            return
        if not message.content or message.content.lstrip().startswith("/"):
            return
        with contextlib.suppress(RuntimeError,OSError):
            await h.command(relay(message.author.display_name,message.content))

def is_console_admin(interaction, guild_id):
    """Guild owner or actual Administrator permission; never trust a role name."""
    guild=interaction.guild
    if guild is None or interaction.guild_id!=guild_id:
        return False
    user=interaction.user
    return user.id==guild.owner_id or bool(getattr(getattr(user,"guild_permissions",None),"administrator",False))


def start_local_console(host):
    """A daemon reader keeps blocking Windows console input off the asyncio loop."""
    if sys.stdin is None or not sys.stdin.isatty():
        print("[CONSOLE] No interactive terminal; staff Discord commands remain available.",flush=True)
        return
    loop=asyncio.get_running_loop()

    async def dispatch(line):
        async with host.maintenance:
            if host.closing:
                return "Host is shutting down."
            return await host.console_command(line)

    def reader():
        print("[CONSOLE] Local console ready. Type Minecraft commands, or :start, :restart, :backup, :status. Ctrl+C exits.",flush=True)
        while not host.closing:
            try:
                line=sys.stdin.readline()
            except (OSError,ValueError):
                return
            if not line or host.closing:
                return
            if not line.strip():
                continue
            coro=dispatch(line.rstrip("\r\n"))
            try:
                future=asyncio.run_coroutine_threadsafe(coro,loop)
            except RuntimeError:
                coro.close()
                return
            try:
                print("[CONSOLE] "+future.result(),flush=True)
            except Exception as exc:
                if host.closing:
                    return
                print("[CONSOLE] Command failed: "+str(exc),flush=True)

    threading.Thread(target=reader,name="ingenium-console",daemon=True).start()


def install_commands(bot,h):
    tree=bot.tree
    def member(i):
        return i.guild_id==h.cfg["guild_id"]
    def staff(i):
        return is_console_admin(i,h.cfg["guild_id"])
    async def run(i,fn,admin=False):
        if not (staff(i) if admin else member(i)):
            await i.response.send_message("Not authorized.",ephemeral=True)
            return
        await i.response.defer(ephemeral=admin,thinking=True)
        try:
            if admin:
                async with h.maintenance:
                    result=await fn() if staff(i) and not h.closing else "Not authorized or host shutting down."
            else:
                result=await fn()
        except Exception as e:
            print("Command error:",e)
            result="Operation failed. Check the host console."
        await i.followup.send(result,allowed_mentions=NO_MENTIONS,ephemeral=admin)

    @tree.command(name="status",description="Ingenium SMP live status")
    async def status(i:discord.Interaction):
        await run(i,h.status)

    @tree.command(name="ip",description="Minecraft server address")
    async def ip(i:discord.Interaction):
        async def result():
            return h.cfg["public_address"] or "Public address not configured." if h.cfg["public_access_verified"] else "Public access is not enabled yet."
        await run(i,result)

    @tree.command(name="players",description="Live player count and reported sample")
    async def players(i:discord.Interaction):
        async def result():
            try:
                s=await asyncio.to_thread(lambda:JavaServer.lookup("127.0.0.1:25565",timeout=3).status())
                sample=", ".join(x.name for x in s.players.sample or [])
                return f"{s.players.online}/{s.players.max} online. Reported sample: {sample or 'not available'}."
            except Exception:
                return "Server not responding."
        await run(i,result)

    @tree.command(name="start",description="Start Minecraft (staff)")
    async def start(i:discord.Interaction):
        await run(i,h.start,True)

    @tree.command(name="stop",description="Save and stop Minecraft (staff)")
    async def stop(i:discord.Interaction):
        await run(i,h.stop,True)

    @tree.command(name="restart",description="Gracefully restart Minecraft (staff)")
    async def restart(i:discord.Interaction):
        async def result():
            await h.stop()
            return await h.start()
        await run(i,result,True)

    @tree.command(name="backup",description="Back up server when empty or stopped (staff)")
    async def backup(i:discord.Interaction):
        await run(i,h.backup,True)

    @tree.command(name="console",description="Run a Minecraft console command (owner/admin only)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(command="One Minecraft command, e.g. list or time set day")
    async def console(i:discord.Interaction, command:str):
        async def result():
            # Do not print raw Discord command arguments to logs.
            print(f"[CONSOLE] Authorized Discord command requested by user {i.user.id}",flush=True)
            try:
                return await h.console_command(command)
            except ValueError as exc:
                return str(exc)
        await run(i,result,True)

    @tree.command(name="console_logs",description="View recent private Minecraft console logs (owner/admin only)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(lines="Number of recent lines, 1 to 50")
    async def console_logs(i:discord.Interaction, lines:app_commands.Range[int,1,50]=20):
        if not staff(i):
            await i.response.send_message("Not authorized.",ephemeral=True)
            return
        await i.response.send_message(h.console_tail(lines),ephemeral=True,allowed_mentions=NO_MENTIONS)

    @tree.command(name="setup_channels",description="Create Ingenium SMP channels (server owner)")

    async def setup_channels(i:discord.Interaction):
        if not staff(i) or not i.guild or i.guild.owner_id!=i.user.id:
            await i.response.send_message("Server owner only.",ephemeral=True)
            return
        await i.response.defer(ephemeral=True,thinking=True)
        try:
            g=i.guild
            for category,names in {"INFORMATION":["rules","announcements","how-to-join","server-status"],"COMMUNITY":["general","minecraft-chat","screenshots","trading","events"]}.items():
                cat=discord.utils.get(g.categories,name=category)
                if cat is None: cat=await g.create_category(category)
                for name in names:
                    ch=discord.utils.get(cat.text_channels,name=name)
                    if ch is None: ch=await g.create_text_channel(name,category=cat)
                    if name=="minecraft-chat": h.cfg["chat_channel_id"]=ch.id
                    if name=="server-status": h.cfg["status_channel_id"]=ch.id
            cfg_tmp=CONFIG.with_suffix(".tmp")
            cfg_tmp.write_text(json.dumps(h.cfg,indent=2),encoding="utf-8")
            cfg_tmp.replace(CONFIG)
            await i.followup.send("Channels configured. Review channel permissions before inviting players.",ephemeral=True)
        except discord.HTTPException:
            await i.followup.send("Channel setup incomplete. Check Manage Channels permission, then retry.",ephemeral=True)

async def main():
    load_dotenv(ROOT/".env")
    cfg=load_config()
    token=os.getenv("DISCORD_TOKEN","")
    if not token or not cfg["guild_id"] or not cfg["owner_ids"]:
        raise RuntimeError("Configure Discord token, guild_id and owner_ids first.")
    with runtime_guard(ROOT/"runtime.lock"):
        h=Host(cfg)
        bot=Ingenium(h); h.bot=bot
        install_commands(bot,h)
        schedule=None
        try:
            if cfg.get("autostart"):
                try: print(await h.start())
                except Exception as e: print("Autostart failed:",e)
            schedule=asyncio.create_task(h.scheduled_backups())
            start_local_console(h)
            await bot.start(token)
        finally:
            h.closing=True
            if schedule:
                schedule.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await schedule
            try:
                async with h.maintenance:
                    await h.stop()
                    if h.proc and h.proc.returncode is None:
                        print("Waiting for Java to stop before releasing runtime lock.")
                        await h.proc.wait()
            finally:
                await bot.close()

if __name__=="__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
    except RuntimeError as e:
        print("Host startup failed:", e)
        raise SystemExit(1)
