import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from telegram.error import TelegramError
from bot import send_follow_invitation

class FollowInvitationTests(unittest.IsolatedAsyncioTestCase):
    async def test_links_match_creator_accounts(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        await send_follow_invitation(message)
        message.reply_text.assert_awaited_once()
        markup = message.reply_text.call_args.kwargs['reply_markup']
        self.assertEqual([row[0].url for row in markup.inline_keyboard], [
            'https://snapchat.com/t/d9GtFjtN', 'https://www.tiktok.com/@kh01ed',
        ])

    async def test_delivery_failure_does_not_fail_download(self):
        message = SimpleNamespace(reply_text=AsyncMock(side_effect=TelegramError('test')))
        await send_follow_invitation(message)
        message.reply_text.assert_awaited_once()
