"""Safe Aternos world import and local configuration."""
import argparse, json, shutil, stat, tempfile, zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "server"

def import_world(archive, target=SERVER / "world"):
    target = Path(target)
    if target.exists():
        raise RuntimeError("Destination exists; refusing to overwrite.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        roots = []
        for e in entries:
            p = PurePosixPath(e.filename)
            if p.is_absolute() or "\\" in e.filename or ".." in p.parts or any(":" in x for x in p.parts) or stat.S_ISLNK(e.external_attr >> 16):
                raise ValueError("Unsafe archive entry: " + e.filename)
            if not e.is_dir() and p.name == "level.dat":
                roots.append(p.parent)
        if len(roots) != 1:
            raise ValueError("Expected exactly one level.dat")
        prefix = roots[0]
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
            stage = Path(tmp) / "world"
            stage.mkdir()
            seen = set()
            for e in entries:
                p = PurePosixPath(e.filename)
                if e.is_dir() or not p.is_relative_to(prefix):
                    continue
                rel = p.relative_to(prefix)
                if rel.name == "session.lock" and len(rel.parts) == 1:
                    continue
                for x in rel.parts:
                    if x.endswith((" ", ".")) or x.split(".")[0].upper() in {"CON","PRN","AUX","NUL",*[f"COM{i}" for i in range(1,10)],*[f"LPT{i}" for i in range(1,10)]}:
                        raise ValueError("Unsafe Windows filename")
                key = str(rel).casefold()
                if key in seen:
                    raise ValueError("Duplicate path: " + key)
                seen.add(key)
                out = stage.joinpath(*rel.parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(e) as src, out.open("xb") as dst:
                    shutil.copyfileobj(src,dst)
            if not (stage/"level.dat").stat().st_size:
                raise ValueError("Empty level.dat")
            stage.rename(target)
    print("Imported world:", target)

def configure():
    SERVER.mkdir(exist_ok=True)
    (SERVER/"mods").mkdir(exist_ok=True)
    cfg = ROOT/"config.json"
    if not cfg.exists():
        shutil.copyfile(ROOT/"config.example.json",cfg)
    files = {
        "server.properties": "server-ip=127.0.0.1\nserver-port=25565\nlevel-name=world\nonline-mode=false\nenforce-secure-profile=false\nwhite-list=true\nenforce-whitelist=true\nmax-players=10\ngamemode=survival\nview-distance=8\nsimulation-distance=6\nenable-rcon=false\nenable-query=false\npause-when-empty-seconds=-1\nmotd=Ingenium SMP\n",
        "eula.txt": "eula=false\n",
        "ops.json": "[]\n"
    }
    for name, contents in files.items():
        p = SERVER/name
        if not p.exists():
            p.write_text(contents, encoding="utf-8")
    env = ROOT/".env"
    if not env.exists():
        env.write_text("DISCORD_TOKEN=\n",encoding="utf-8")
    print("Local settings created; existing files untouched.")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action",required=True)
    imp = sub.add_parser("import-world")
    imp.add_argument("archive",type=Path)
    sub.add_parser("configure")
    args = p.parse_args()
    if args.action == "import-world":
        import_world(args.archive)
    else:
        configure()
