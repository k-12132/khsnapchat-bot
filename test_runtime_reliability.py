import ast
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from telegram.error import NetworkError

class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry(self):
        import bot
        get = AsyncMock(side_effect=[NetworkError("temporary"), SimpleNamespace(status="member")])
        self.assertTrue(await bot.subscribed(SimpleNamespace(bot=SimpleNamespace(get_chat_member=get)), 123))
        self.assertEqual(get.await_count, 2)
    async def test_missing_chat(self):
        import bot
        self.assertFalse(bot.permitted(SimpleNamespace(effective_chat=None, effective_user=None)))
    def test_syntax(self):
        ast.parse(Path("bot.py").read_text())
