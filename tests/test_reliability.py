import asyncio
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

import bot
import downloader
from telegram.error import BadRequest, NetworkError


class NetworkTests(unittest.IsolatedAsyncioTestCase):
    async def test_membership_recovers_after_network_failure(self):
        context = NS(bot=NS(get_chat_member=AsyncMock(side_effect=[NetworkError('offline'), NS(status='member')])))
        with patch.object(bot.asyncio, 'sleep', AsyncMock()):
            self.assertTrue(await bot.subscribed(context, 42))
        self.assertEqual(context.bot.get_chat_member.await_count, 2)

    async def test_exhausted_network_retry_denies_access_with_correct_message(self):
        context = NS(bot=NS(get_chat_member=AsyncMock(side_effect=NetworkError('offline'))))
        message = NS(reply_text=AsyncMock())
        with patch.object(bot.asyncio, 'sleep', AsyncMock()):
            self.assertFalse(await bot.require_subscription(NS(effective_user=NS(id=42), effective_message=message), context))
        self.assertEqual(context.bot.get_chat_member.await_count, 3)
        self.assertIn('تعذر الاتصال', message.reply_text.call_args.args[0])

    async def test_bad_request_is_not_retried(self):
        context = NS(bot=NS(get_chat_member=AsyncMock(side_effect=BadRequest('chat not found'))))
        self.assertIsNone(await bot.subscribed(context, 42))
        self.assertEqual(context.bot.get_chat_member.await_count, 1)

    async def test_status_edit_retry_does_not_repeat_upload(self):
        status = NS(edit_text=AsyncMock(side_effect=[NetworkError('offline'), None]))
        with patch.object(bot.asyncio, 'sleep', AsyncMock()):
            await bot.edit_status(status, 'done')
        self.assertEqual(status.edit_text.await_count, 2)


class DownloaderRetryTests(unittest.TestCase):
    def test_retries_network_and_temporary_http_errors(self):
        response = Mock()
        for error in (urllib.error.URLError('offline'), urllib.error.HTTPError('https://snapchat.com/test', 503, 'temporary', {}, io.BytesIO())):
            opener = NS(open=Mock(side_effect=[error, response]))
            with patch.object(downloader.time, 'sleep'):
                self.assertIs(downloader.open_with_retry(opener, Mock()), response)
            self.assertEqual(opener.open.call_count, 2)

    def test_forbidden_is_not_retried(self):
        error = urllib.error.HTTPError('https://snapchat.com/test', 403, 'forbidden', {}, io.BytesIO())
        opener = NS(open=Mock(side_effect=error))
        with self.assertRaises(urllib.error.HTTPError):
            downloader.open_with_retry(opener, Mock())
        self.assertEqual(opener.open.call_count, 1)

    def test_network_retries_are_bounded_and_safe(self):
        opener = NS(open=Mock(side_effect=urllib.error.URLError('private https://example.org/?secret=hidden')))
        with patch.object(downloader.time, 'sleep'), self.assertRaises(downloader.DownloadError) as error:
            downloader.open_with_retry(opener, Mock())
        self.assertEqual(opener.open.call_count, 3)
        self.assertEqual(error.exception.reason, 'network')
        self.assertNotIn('secret', str(error.exception))

    def test_redirect_target_is_validated_before_following(self):
        opener = NS(open=Mock(side_effect=urllib.error.HTTPError('https://snapchat.com/test', 302, 'redirect', {'Location': 'https://example.org/private'}, io.BytesIO())))
        with patch.object(downloader.urllib.request, 'build_opener', return_value=opener), self.assertRaises(downloader.DownloadError):
            with downloader.get('https://snapchat.com/test'):
                pass
        self.assertEqual(opener.open.call_count, 1)

    def test_large_content_length_rejected_without_reading_body(self):
        response = Mock(headers={'Content-Type': 'video/mp4', 'Content-Length': str(downloader.MAX_BYTES + 1)})
        opener = NS(open=Mock(return_value=response))
        with tempfile.TemporaryDirectory() as directory, patch.object(downloader.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaises(downloader.DownloadError) as error:
                downloader.download('https://sc-cdn.net/video.mp4', Path(directory), 1)
        self.assertEqual(error.exception.reason, 'too_large')
        response.read.assert_not_called()
        response.close.assert_called_once()


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    def request(self):
        status = NS(edit_text=AsyncMock())
        message = NS(text='https://snapchat.com/test?secret=hidden', message_id=1,
                     reply_text=AsyncMock(return_value=status), reply_document=AsyncMock())
        update = NS(effective_user=NS(id=42), effective_chat=NS(id=42, type='private'), effective_message=message, message=message)
        return update, NS(bot_data={'statistics': Mock()}), status

    async def test_partial_download_reports_reason_and_counts_only_sent_files(self):
        update, context, status = self.request()
        def download(url, directory, index):
            if index == 1:
                raise downloader.DownloadError('too big', 'too_large')
            path = directory / 'video.mp4'
            path.write_bytes(b'media')
            return path
        with patch.object(bot, 'require_subscription', AsyncMock(return_value=True)), patch.object(bot, 'media_links', return_value=['first', 'second']), patch.object(bot, 'download', download), patch.object(bot, 'send_follow_invitation', AsyncMock()), patch.object(bot.logging, 'warning') as log, patch.object(bot, 'ALLOWED', set()):
            await bot.handle(update, context)
        update.message.reply_document.assert_awaited_once()
        self.assertIn('45', status.edit_text.call_args.args[0])
        context.bot_data['statistics'].downloaded.assert_called_once_with('42:1', 1)
        record = json.loads([c.args[1] for c in log.call_args_list if c.args[0] == 'snap_performance %s'][0])
        self.assertEqual(record['result'], 'partial')
        self.assertEqual(record['sent'], 1)
        self.assertNotIn('secret', json.dumps(record))
        self.assertNotIn(42, bot.BUSY)

    async def test_uncertain_upload_is_not_retried(self):
        update, context, status = self.request()
        update.message.reply_document.side_effect = NetworkError('offline')
        def download(url, directory, index):
            path = directory / 'video.mp4'
            path.write_bytes(b'media')
            return path
        with patch.object(bot, 'require_subscription', AsyncMock(return_value=True)), patch.object(bot, 'media_links', return_value=['first', 'second']), patch.object(bot, 'download', download), patch.object(bot, 'ALLOWED', set()):
            await bot.handle(update, context)
        update.message.reply_document.assert_awaited_once()
        self.assertIn('تحقق من الملفات', status.edit_text.call_args.args[0])
        context.bot_data['statistics'].downloaded.assert_not_called()
        self.assertNotIn(42, bot.BUSY)

    async def test_full_queue_rejects_without_starting_download(self):
        update, context, status = self.request()
        with patch.object(bot, 'require_subscription', AsyncMock(return_value=True)), patch.object(bot, 'BUSY', set(range(bot.MAX_PENDING_REQUESTS))), patch.object(bot, 'media_links') as links, patch.object(bot, 'ALLOWED', set()):
            await bot.handle(update, context)
            links.assert_not_called()
        self.assertIn('مشغول', update.message.reply_text.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
