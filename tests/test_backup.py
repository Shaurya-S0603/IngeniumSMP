import datetime as dt
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from backup_manager import snapshot, due, archives

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.server = self.root / "server"
        self.dest = self.root / "backups"
        for path, data in {
            "world/level.dat": b"level",
            "world/DIM-1/region/r.0.0.mca": b"nether",
            "world/playerdata/test.dat": b"player",
            "world/datapacks/test.zip": b"pack",
            "world/session.lock": b"lock",
            "config/EasyAuth/auth.db": b"auth",
            "libraries/cache.jar": b"cache",
        }.items():
            p = self.server / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)

    def test_snapshot(self):
        path = snapshot(self.server, self.dest, True)
        with zipfile.ZipFile(path) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.read("world/level.dat"), b"level")
            self.assertEqual(z.read("world/DIM-1/region/r.0.0.mca"), b"nether")
            self.assertEqual(z.read("world/playerdata/test.dat"), b"player")
            self.assertEqual(z.read("world/datapacks/test.zip"), b"pack")
            self.assertEqual(z.read("config/EasyAuth/auth.db"), b"auth")
            self.assertNotIn("world/session.lock", z.namelist())
            self.assertNotIn("libraries/cache.jar", z.namelist())
        self.assertFalse(due(self.dest))

    def test_retention_preserves_manual(self):
        manual = snapshot(self.server, self.dest)
        for _ in range(3):
            snapshot(self.server, self.dest, True, 2)
        self.assertEqual(len(archives(self.dest)), 2)
        self.assertTrue(manual.exists())

    def test_due(self):
        self.assertTrue(due(self.dest))
        path = snapshot(self.server, self.dest, True)
        old = (dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=25)).timestamp()
        os.utime(path,(old,old))
        self.assertTrue(due(self.dest))

    def test_missing_level(self):
        (self.server/"world"/"level.dat").unlink()
        with self.assertRaises(RuntimeError):
            snapshot(self.server,self.dest,True)
        self.assertFalse(self.dest.exists())
