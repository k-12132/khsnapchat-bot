import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from telegram.error import TelegramError
import bot

class MembershipTests(unittest.IsolatedAsyncioTestCase):
    def context(self, status='member', is_member=False):
        return NS(bot=NS(get_chat_member=AsyncMock(return_value=NS(status=status, is_member=is_member))))
    def update(self):
        message = NS(reply_text=AsyncMock(), text='https://snapchat.com/t/example')
        return NS(effective_user=NS(id=42), effective_chat=NS(type='private'), effective_message=message, message=message, callback_query=NS(answer=AsyncMock()))
    async def test_statuses(self):
        for status, flag, expected in [
            ('creator', False, True), ('administrator', False, True), ('member', False, True),
            ('left', False, False), ('kicked', False, False), ('restricted', True, True), ('restricted', False, False),
        ]:
            with self.subTest(status=status, flag=flag):
                self.assertEqual(await bot.subscribed(self.context(status, flag), 42), expected)
    async def test_api_failure_denies_access(self):
        context = self.context()
        context.bot.get_chat_member.side_effect = TelegramError('test')
        update = self.update()
        self.assertFalse(await bot.require_subscription(update, context))
        update.message.reply_text.assert_awaited_once()
    async def test_nonmember_does_not_download(self):
        update = self.update()
        with patch.object(bot, 'ALLOWED', set()), patch.object(bot, 'media_links') as links:
            await bot.handle(update, self.context('left'))
            links.assert_not_called()
        self.assertEqual(update.message.reply_text.await_count, 1)
    async def test_callback_verifies_membership(self):
        update = self.update()
        context = self.context()
        with patch.object(bot, 'ALLOWED', set()):
            await bot.check_subscription(update, context)
        update.callback_query.answer.assert_awaited_once()
        context.bot.get_chat_member.assert_awaited_once_with('@kh01ed', 42)
        update.message.reply_text.assert_awaited_once()
    async def test_membership_rechecked_after_leaving(self):
        update = self.update()
        context = self.context()
        self.assertTrue(await bot.require_subscription(update, context))
        context.bot.get_chat_member.return_value = NS(status='left')
        self.assertFalse(await bot.require_subscription(update, context))

if __name__ == '__main__':
    unittest.main()
