import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
import activation
import bot

class ActivationTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_issues_account_bound_return_link(self):
        secret = 'test-only-' * 5
        message = NS(reply_text=AsyncMock())
        update = NS(effective_user=NS(id=42), effective_chat=NS(type='private'), effective_message=message, message=message)
        context = NS(args=['activate_test_bot'], user_data={})
        with patch.dict('os.environ', {'BOT_ACTIVATION_SECRET': secret}), patch.object(bot, 'require_subscription', AsyncMock(return_value=True)), patch.object(bot, 'ALLOWED', set()):
            await bot.start(update, context)
        url = message.reply_text.call_args.kwargs['reply_markup'].inline_keyboard[0][0].url
        self.assertTrue(url.startswith('https://t.me/test_bot?start='))
        token = url.split('?start=')[1]
        self.assertTrue(activation.verify(secret, token, 42))
        self.assertFalse(activation.verify(secret, token, 43))

    async def test_nonmember_waits_for_channel_verification(self):
        update = NS(effective_user=NS(id=42), effective_chat=NS(type='private'))
        context = NS(args=['activate'], user_data={})
        with patch.object(bot, 'ALLOWED', set()), patch.object(bot, 'require_subscription', AsyncMock(return_value=False)), patch.object(bot, 'send_activation_receipt', AsyncMock()) as receipt:
            await bot.start(update, context)
            receipt.assert_not_awaited()
        self.assertTrue(context.user_data['activate_tiktok'])
