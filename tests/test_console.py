"""Console authorization and command routing tests (no live Discord or Java)."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from host import Host, is_console_admin

class AuthorizationTests(unittest.TestCase):
    def test_owner_admin_member_and_wrong_guild(self):
        def interaction(uid,admin=False,gid=1,guild=True):
            return NS(guild=NS(owner_id=10) if guild else None,guild_id=gid,
                      user=NS(id=uid,guild_permissions=NS(administrator=admin)))
        self.assertTrue(is_console_admin(interaction(10),1))
        self.assertTrue(is_console_admin(interaction(20,True),1))
        self.assertFalse(is_console_admin(interaction(20),1))
        self.assertFalse(is_console_admin(interaction(20,True,2),1))
        self.assertFalse(is_console_admin(interaction(10,guild=False),1))

class ConsoleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.h=Host({})
        self.h.command=AsyncMock()
        self.h.stop=AsyncMock(return_value="stopped")
        self.h.ready=True
    async def test_regular_command_and_slash(self):
        await self.h.console_command("/list")
        self.h.command.assert_awaited_once_with("list")
    async def test_stop_uses_supervisor(self):
        self.assertEqual(await self.h.console_command("minecraft:stop"),"stopped")
        self.h.stop.assert_awaited_once()
        self.h.command.assert_not_awaited()
    async def test_multiline(self):
        with self.assertRaises(ValueError):
            await self.h.console_command("list\nstop")
    async def test_not_ready(self):
        self.h.ready=False
        self.assertIn("not ready",await self.h.console_command("list"))
        self.h.command.assert_not_awaited()
    async def test_logs_filter_and_bound(self):
        self.h.console_lines.extend(["normal log","user password hunter2","/login sensitive"])
        out=self.h.console_tail()
        self.assertIn("normal log",out)
        self.assertNotIn("hunter2",out)
        self.assertNotIn("sensitive",out.lower().replace("sensitive authentication-related line omitted",""))
        self.h.console_lines.extend(["x"*2000]*50)
        self.assertLessEqual(len(self.h.console_tail(50)),1650)
