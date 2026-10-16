import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch
import bot

class StatsCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_other_users_cannot_access_statistics(self):
        update = NS(effective_user=NS(id=88), effective_chat=NS(type='private'), effective_message=NS(reply_text=AsyncMock()))
        store = Mock()
        with patch.object(bot, 'OWNER_USER_ID', 99):
            await bot.stats(update, NS(bot_data={'statistics': store}))
        store.summary.assert_not_called()
        update.effective_message.reply_text.assert_not_awaited()
    async def test_owner_gets_counts_and_storage_notice(self):
        message = NS(reply_text=AsyncMock())
        update = NS(effective_user=NS(id=99), effective_chat=NS(type='private'), effective_message=message)
        store = Mock()
        store.summary.return_value = dict(users=4, active_today=2, requests=3, files=8, since='2026-10-17')
        with patch.object(bot, 'OWNER_USER_ID', 99):
            await bot.stats(update, NS(bot_data={'statistics': store, 'statistics_persistent': False}))
        text = message.reply_text.call_args.args[0]
        self.assertIn('4', text)
        self.assertIn('الحفظ مؤقت', text)
