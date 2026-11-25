"""Ingenium SMP public dashboard. Read-only Minecraft status and community hub."""
from pathlib import Path
from datetime import datetime, timezone
from html import escape
import base64
import mimetypes
import streamlit as st
from mcstatus import JavaServer

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
CURRENT_ADDRESS = "wap-mojo.tun.ply.gg:9350"
CURRENT_IP = "147.185.221.220"

st.set_page_config(page_title="Ingenium SMP | The Forge", page_icon="🔥", layout="wide")

def setting(key, default=""):
    try:
        return str(st.secrets.get(key, default)).strip() or default
    except Exception:
        return default

address = setting("server_address", CURRENT_ADDRESS)
# Migrate the retired endpoint even if the old Cloud secret has not been edited.
if address.lower().rstrip(".") in {"wap-sane.tun.ply.gg", "wap-sane.tun.ply.gg:9350", "147.185.221.217:9350", "wap-mojo.tun.ply.gg"}:
    address = CURRENT_ADDRESS
invite = setting("discord_invite", "https://discord.gg/2g6tmVde59")
if not invite.startswith(("https://discord.gg/", "https://discord.com/invite/")):
    invite = "https://discord.gg/2g6tmVde59"
owner = setting("staff_owner", "Server owner")

def asset(name):
    # Prefer original PNGs when added; lightweight originals-derived WebP fallbacks are bundled.
    for ext in (".png", ".webp", ".jpg"):
        path = ASSETS / (name + ext)
        if path.is_file():
            return path
    return None

def data_uri(path):
    if not path:
        return ""
    return "data:" + (mimetypes.guess_type(path.name)[0] or "image/png") + ";base64," + base64.b64encode(path.read_bytes()).decode("ascii")

logo = asset("logo")
banner = asset("banner")
logo_html = f'<img class="crest" src="{data_uri(logo)}" alt="Ingenium SMP lava crest">' if logo else '<div class="crest fallback">◆</div>'

st.markdown("""
<style>
:root {--ember:#ff7652;--gold:#ffbf75;--ink:#100b0d;--muted:#d8bdb5;}
.stApp {background:radial-gradient(ellipse at 8% 0%,#411510 0%,transparent 34%),radial-gradient(ellipse at 100% 28%,#27121d 0%,transparent 37%),#100b0d;color:#fff2eb;}
[data-testid="stHeader"] {background:transparent;}
.block-container {max-width:1200px;padding:2.3rem 2rem 3rem;}
h1,h2,h3 {letter-spacing:-.035em;color:#fff2eb;}
.forge-nav {display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:8px 0 18px;border-bottom:1px solid #542b2b;}
.forge-nav strong {color:#ffbc87;font-size:.82rem;letter-spacing:.15em;}
.forge-nav nav {display:flex;gap:20px;flex-wrap:wrap;}
.forge-nav a {color:#e2c4ba!important;text-decoration:none!important;font-size:.84rem;font-weight:650;}
.forge-nav a:hover {color:#ffae75!important;}
.forge-hero {position:relative;isolation:isolate;overflow:hidden;display:grid;grid-template-columns:minmax(0,1.5fr) minmax(140px,1fr);align-items:center;gap:22px;min-height:345px;padding:clamp(24px,5vw,66px);border:1px solid #80372b;border-radius:24px;background:radial-gradient(ellipse at 86% 54%,#a8321355,transparent 55%),linear-gradient(125deg,#251012,#140d0f 62%,#371211);box-shadow:0 18px 70px #0007;}
.forge-hero:before {content:"";position:absolute;inset:0;z-index:-1;background-image:linear-gradient(#ff9a5010 1px,transparent 1px),linear-gradient(90deg,#ff9a5010 1px,transparent 1px);background-size:32px 32px;mask-image:linear-gradient(90deg,transparent,#000);}
.forge-hero:after {content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;background-image:radial-gradient(2px 2px at 13% 71%,#ffad62 80%,transparent),radial-gradient(2px 2px at 32% 18%,#ff682f 80%,transparent),radial-gradient(3px 3px at 89% 20%,#ffd49b 80%,transparent),radial-gradient(2px 2px at 67% 81%,#ff6b35 80%,transparent);animation:embers 7s ease-in-out infinite alternate;}
@keyframes embers {from {transform:translateY(9px);opacity:.45;}to {transform:translateY(-9px);opacity:1;}}
.eyebrow {font-size:.75rem;font-weight:800;letter-spacing:.19em;color:#ffab77;text-transform:uppercase;}
.forge-hero h1 {font-size:clamp(2.6rem,6vw,5.2rem);line-height:.94;margin:16px 0;color:#fff1e5;font-weight:900;text-shadow:0 3px 30px #e83b2345;}
.forge-hero h1 span {color:#ff8154;}
.forge-hero p {font-size:1.05rem;line-height:1.6;color:#ebd2c7;max-width:520px;}
.crest {display:block;width:100%;max-width:260px;aspect-ratio:1;object-fit:contain;justify-self:center;border-radius:20px;filter:drop-shadow(0 0 24px #fa411d55);}
.fallback {font-size:6rem;color:#ff874e;text-align:center;}
.hero-actions {display:flex;gap:12px;flex-wrap:wrap;margin:24px 0 12px;}
.forge-cta {display:inline-flex;align-items:center;justify-content:center;padding:12px 20px;border-radius:10px;text-decoration:none!important;font-weight:800;min-height:46px;transition:transform .2s,background .2s,box-shadow .2s;}
.forge-cta.primary {background:linear-gradient(110deg,#ff9863,#ff573e);color:#21100b!important;animation:glow 3s ease-in-out infinite;}
.forge-cta.secondary {border:1px solid #a85546;color:#ffe0d2!important;background:#31191c;}
.forge-cta:hover {transform:translateY(-3px);box-shadow:0 0 28px #ff754c55;}
.forge-cta:focus-visible,.forge-nav a:focus-visible {outline:3px solid #ffce91;outline-offset:4px;}
@keyframes glow {0%,100% {box-shadow:0 0 12px #ff613c40;}50% {box-shadow:0 0 25px #ff613c70;}}
.hero-meta {font-size:.79rem;color:#e9baab;letter-spacing:.035em;}
.section-head {margin:28px 0 10px;padding-top:8px;scroll-margin-top:65px;}
.section-head h2 {font-size:clamp(1.65rem,3.5vw,2.25rem);margin:3px 0 5px;font-weight:800;}
.section-head p {color:var(--muted);margin:0;font-size:.94rem;}
.stat-grid,.feature-grid {display:grid;gap:12px;grid-template-columns:repeat(4,minmax(0,1fr));}
.feature-grid {grid-template-columns:repeat(3,minmax(0,1fr));}
.tile {background:linear-gradient(150deg,#2a171b,#1a1115);border:1px solid #583033;border-radius:15px;padding:19px;min-width:0;transition:transform .2s,border-color .2s,box-shadow .2s;}
.tile:hover {transform:translateY(-4px);border-color:#bb6249;box-shadow:0 12px 28px #0005,0 0 20px #fa602216;}
.tile .label {color:#dec1b7;font-size:.76rem;letter-spacing:.09em;text-transform:uppercase;font-weight:750;}
.tile .number {font-size:clamp(1.25rem,3vw,2rem);font-weight:850;color:#fff2eb;overflow-wrap:anywhere;margin:6px 0;}
.tile .detail {color:#d6b9b1;font-size:.84rem;line-height:1.5;}
.tile h3 {font-size:1.18rem;margin:8px 0;}
.tile .icon {font-size:1.65rem;}
.status-dot {display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px;background:#ffad67;}
.status-dot.online {background:#83e6ad;box-shadow:0 0 0 0 #83e6ad80;animation:pulse 2.5s infinite;}
@keyframes pulse {70%{box-shadow:0 0 0 8px #83e6ad00;}100%{box-shadow:0 0 0 0 #83e6ad00;}}
.online-text {color:#a0efbc!important;}
.occupancy {height:7px;background:#42262a;border-radius:99px;overflow:hidden;margin:9px 0 4px;}
.occupancy span {display:block;height:100%;background:linear-gradient(90deg,#ff653d,#ffc18a);border-radius:99px;}
[data-testid="stButton"] button,[data-testid="stLinkButton"] a {border-radius:10px;border-color:#965141;transition:transform .18s,box-shadow .18s;}
[data-testid="stButton"] button:hover,[data-testid="stLinkButton"] a:hover {transform:translateY(-2px);box-shadow:0 0 18px #ff6c3b42;}
[data-testid="stVerticalBlockBorderWrapper"] {border-color:#583033!important;background:#1c1216;border-radius:15px;}
[data-testid="stImage"] img {border-radius:12px;}
[data-testid="stExpander"] {border-color:#583033!important;}
.art-card {display:flex;flex-direction:column;gap:12px;}
.art-card img {width:100%;max-height:190px;object-fit:contain;border-radius:10px;background:#100b0d;}
.footer {margin-top:32px;border-top:1px solid #583033;padding:22px 0;color:#d8b9af;text-align:center;font-size:.85rem;}
@media(max-width:800px) {.stat-grid,.feature-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.block-container{padding:1.5rem 1rem;}.forge-hero{min-height:0;grid-template-columns:1fr;}.crest{max-width:170px;grid-row:1;}.forge-hero h1{font-size:3rem;}}
@media(max-width:440px) {.feature-grid{grid-template-columns:1fr;}.tile{padding:13px;}.forge-nav nav{gap:12px;}}
@media(prefers-reduced-motion:reduce) {*,*:before,*:after {animation:none!important;transition:none!important;scroll-behavior:auto!important;}}
</style>
""", unsafe_allow_html=True)

def section(anchor, kicker, title, subtitle):
    st.markdown(f'<div class="section-head" id="{anchor}"><div class="eyebrow">{kicker}</div><h2>{title}</h2><p>{subtitle}</p></div>', unsafe_allow_html=True)

st.markdown('<div class="forge-nav"><strong>◆ &nbsp; INGENIUM / THE FORGE</strong><nav aria-label="Sections"><a href="#status">Live status</a><a href="#join">Join</a><a href="#world">World</a><a href="#gallery">Gallery</a><a href="#staff">Staff</a><a href="#faq">FAQ</a></nav></div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="forge-hero">
  <div><div class="eyebrow">JAVA EDITION 26.3 · VANILLA+ SURVIVAL</div>
  <h1>Forge your<br><span>own legend.</span></h1>
  <p>Ingenium SMP is a world of dramatic terrain, dangerous dimensions and community-built stories. Make your mark, block by block.</p>
  <div class="hero-actions"><a class="forge-cta primary" href="#join">Start playing ↗</a><a class="forge-cta secondary" href="{escape(invite, quote=True)}" target="_blank" rel="noopener noreferrer">Join Discord ↗</a></div>
  <div class="hero-meta">CRACKED &amp; PREMIUM · EASYAUTH · 10 PLAYER SLOTS</div></div>
  {logo_html}
</div>
""", unsafe_allow_html=True)

@st.cache_data(ttl=20, show_spinner=False)
def query(endpoint):
    checked = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M:%S UTC")
    try:
        response = JavaServer.lookup(endpoint, timeout=4).status(tries=1)
        return {"state":"Online", "count":response.players.online, "max":response.players.max,
                "latency":round(response.latency), "version":response.version.name, "checked":checked}
    except Exception:
        return {"state":"Unreachable","checked":checked}

section("status", "01 / Live telemetry", "The heartbeat", "Real Minecraft status, refreshed while this page is open.")

@st.fragment(run_every="30s")
def live_status():
    if st.button("Refresh status", key="refresh-status"):
        query.clear()
    data = query(address)
    online = data["state"] == "Online"
    count = data.get("count")
    capacity = data.get("max")
    percent = max(0, min(100, round(100*count/capacity))) if online and capacity else 0
    occupancy = f'<div class="occupancy" role="progressbar" aria-label="Player slots occupied" aria-valuenow="{percent}" aria-valuemin="0" aria-valuemax="100"><span style="width:{percent}%"></span></div>' if online else ""
    status = '<span class="status-dot online"></span>Online' if online else '<span class="status-dot"></span>Unreachable'
    players = f"{count}/{capacity}" if online else "—"
    ping = f'{data["latency"]} ms' if online else "—"
    version = escape(str(data.get("version","—")))
    st.markdown(f'<div class="stat-grid"><div class="tile"><div class="label">Server</div><div class="number {"online-text" if online else ""}">{status}</div><div class="detail">Public tunnel</div></div><div class="tile"><div class="label">Players</div><div class="number">{players}</div>{occupancy}<div class="detail">Slots occupied</div></div><div class="tile"><div class="label">Latency</div><div class="number">{ping}</div><div class="detail">Dashboard → server</div></div><div class="tile"><div class="label">Version</div><div class="number">{version}</div><div class="detail">Minecraft Java</div></div></div>', unsafe_allow_html=True)
    st.caption("Last checked: "+data["checked"]+" · Refresh every 30 seconds · Latency is from the dashboard, not your device.")
    if not online:
        st.info("The server or tunnel is not responding to this dashboard. The host may be offline, restarting, or experiencing a DNS/network problem.")

live_status()

section("join", "02 / Enter the world", "Ready to play?", "No whitelist required on the updated host. Use your own username and protect it with EasyAuth.")
left,right = st.columns([1,1])
with left:
    with st.container(border=True):
        st.markdown("### 01 · Add the server")
        st.write("Open Minecraft Java 26.3 → Multiplayer → Add Server.")
        st.code(address, language=None)
        st.caption("Copy the hostname and explicit port. Do not use the numeric IP alone.")
        if address == CURRENT_ADDRESS:
            with st.expander("Unknown Host? Windows DNS fix"):
                st.write("Open Notepad as Administrator. Open the following file (choose All Files if needed):")
                st.code(r"C:\Windows\System32\drivers\etc\hosts", language=None)
                st.write("Append this line, then save:")
                st.code(CURRENT_IP+" wap-mojo.tun.ply.gg", language=None)
                st.code("ipconfig /flushdns", language=None)
                st.write("Restart Minecraft and join with the hostname above. This mapping must be updated if Playit changes the IP.")
with right:
    with st.container(border=True):
        st.markdown("### 02 · Secure your account")
        st.write("First join: follow the EasyAuth prompt to register.")
        st.code("/register password password", language=None)
        st.write("Returning players: log in when prompted.")
        st.code("/login password", language=None)
        st.caption("Use a unique password, never share it in Discord or chat, and keep your Minecraft username consistent.")
        st.link_button("Open the community Discord", invite)

section("world", "03 / Explore", "Beyond ordinary survival", "Three dimensions, six datapacks and endless room to build.")
packs = [
    ("🌿","Terralith","2.6.5 + 26.3","Discover new Overworld biomes, mountains and dramatic terrain."),
    ("🪨","Terralith ReStoned","1.3.1","Companion terrain enhancement for the Overworld."),
    ("🔥","Incendium Legacy","5.5.4 + 26.3","Venture into a redesigned, more dramatic Nether."),
    ("✦","Nullscape","2.0.1 + 26.3","Explore a reimagined End with varied terrain."),
    ("⛏","OreVeinMiner","3.2.0 + 26.3","Mine connected ore veins with less repetitive work."),
    ("🌲","TreeVeinMiner","4.3.2 + 26.3","Harvest trees more efficiently.")
]
st.markdown('<div class="feature-grid">'+"".join(f'<article class="tile"><div class="icon">{icon}</div><div class="label">{escape(ver)}</div><h3>{escape(name)}</h3><div class="detail">{escape(desc)}</div></article>' for icon,name,ver,desc in packs)+'</div>', unsafe_allow_html=True)
st.caption("Datapack catalogue from the original world export; enabled status is not queried live.")

section("gallery", "04 / Field notes", "Gallery", "Community builds, adventures and the artwork behind the Forge.")
gallery = ASSETS / "gallery"
shots = sorted(p for p in gallery.iterdir() if p.is_file() and p.suffix.lower() in {".png",".jpg",".jpeg",".webp"}) if gallery.is_dir() else []
if shots:
    for i in range(0,len(shots),3):
        for col,path in zip(st.columns(3),shots[i:i+3]):
            with col:
                st.image(str(path), caption=path.stem.replace("-"," ").replace("_"," ").title(), use_container_width=True)
else:
    st.markdown('<div class="tile"><div class="eyebrow">Screenshot collection</div><h3>Be the first to leave your mark.</h3><div class="detail">No gameplay screenshots have been published yet. Share your builds, discoveries and adventures in Discord #screenshots for the gallery.</div></div>', unsafe_allow_html=True)
st.markdown("#### Branding & artwork")
art = []
for path,title,desc in [(logo,"The lava crest","Official Ingenium SMP identity"),(banner,"IngeniumBot","Official Discord bot banner")]:
    if path:
        art.append(f'<article class="tile art-card"><img src="{data_uri(path)}" alt="{title}"><h3>{title}</h3><div class="detail">{desc} · Artwork, not gameplay</div></article>')
if art:
    st.markdown('<div class="feature-grid">'+"".join(art)+'</div>', unsafe_allow_html=True)

section("staff", "05 / Community", "Keepers of the Forge", "The people and tools keeping the world running.")
st.markdown(f'<div class="feature-grid"><article class="tile"><div class="icon">♛</div><div class="label">Administration</div><h3>{escape(owner)}</h3><div class="detail">Server operations, player support and community management. Contact through Discord.</div></article><article class="tile"><div class="icon">⚙</div><div class="label">Automation · not a human staff member</div><h3>IngeniumBot</h3><div class="detail">Server status, chat relay and authorized staff commands. Availability depends on the host.</div></article><article class="tile"><div class="icon">◇</div><div class="label">Community</div><h3>Players</h3><div class="detail">Builders, explorers and adventurers. Share screenshots, coordinate projects and report issues in Discord.</div></article></div>', unsafe_allow_html=True)
st.link_button("Visit Ingenium SMP Discord", invite)

section("faq", "06 / Help", "Frequently asked questions", "Everything you need to get into the world.")
for question,answer in [
    ("Can I join with cracked Minecraft?", "Yes. The server uses offline-mode with EasyAuth; both cracked and premium Java clients can join using version 26.3."),
    ("Do I need to be whitelisted?", "No, after the host has been updated to disable the whitelist. Register your own account when you first connect."),
    ("Do I need mods?", "No client gameplay mods are intended. The world enhancements are server-side."),
    ("Why does Minecraft say Unknown Host or Connection Reset?", "Use the exact hostname with its explicit port. If DNS resolution fails, follow the Windows hosts-file instructions above. Do not enter the numeric IP as the server address. If it still fails, contact staff."),
    ("Why can't I move after joining?", "EasyAuth may restrict movement until you register or log in. Follow the in-game instructions."),
    ("Is the server always online?", "The server runs on a local host. Sleep, maintenance, backups, or network interruptions may temporarily take it offline."),
    ("What if I forget my password?", "Contact an administrator privately. Never post a password in Discord or public chat.")
]:
    with st.expander(question):
        st.write(answer)

st.markdown('<div class="footer"><strong>INGENIUM SMP · THE FORGE</strong><br>Build together. Explore further. Make it yours.<br>Public read-only dashboard · Not affiliated with Mojang or Microsoft.</div>', unsafe_allow_html=True)
