"""Consistent offline snapshots. No network access or third-party storage."""
import datetime as dt
import os
from pathlib import Path
import zipfile

SKIP_ROOT = {"libraries", "versions", ".fabric", "logs", "crash-reports"}

def archives(directory, automatic=True):
    prefix = "ingenium-auto-" if automatic else "ingenium-"
    return sorted((p for p in Path(directory).glob(prefix+"*.zip")
                   if p.is_file()), key=lambda p: p.name, reverse=True)

def due(directory, now=None, interval_hours=24):
    now = now or dt.datetime.now(dt.timezone.utc)
    old = archives(directory)
    if not old:
        return True
    last = dt.datetime.fromtimestamp(old[0].stat().st_mtime, dt.timezone.utc)
    return (now-last).total_seconds() >= interval_hours*3600

def snapshot(server, directory, automatic=False, retention=7):
    """Call ONLY after Minecraft has completely stopped."""
    server, directory = Path(server), Path(directory)
    if not (server/"world"/"level.dat").is_file():
        raise RuntimeError("No world level.dat found; backup aborted.")
    directory.mkdir(parents=True, exist_ok=True)
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S-%fZ")
    name=("ingenium-auto-" if automatic else "ingenium-manual-")+stamp+".zip"
    final=directory/name
    partial=directory/(name+".partial")
    try:
        with zipfile.ZipFile(partial,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as z:
            for p in sorted(server.rglob("*")):
                rel=p.relative_to(server)
                if rel.parts[0] in SKIP_ROOT or p.name=="session.lock":
                    continue
                if p.is_symlink():
                    raise RuntimeError("Unexpected symlink in server: "+str(rel))
                if p.is_file():
                    z.write(p,rel.as_posix())
        with zipfile.ZipFile(partial) as z:
            if "world/level.dat" not in z.namelist() or z.testzip() is not None:
                raise RuntimeError("Snapshot verification failed.")
        os.replace(partial,final)
    finally:
        partial.unlink(missing_ok=True)
    if automatic:
        for old in archives(directory)[max(1,retention):]:
            try:
                old.unlink()
            except OSError as e:
                print("Backup retention warning:",e)
    return final
