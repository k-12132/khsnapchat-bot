import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from telegram import Update
from telegram.error import InvalidToken
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from downloader import DownloadError, validate_url, media_links, download

# Avoid logging Telegram request URLs, which contain the bot token.
logging.basicConfig(level=logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
ALLOWED = {int(x.strip()) for x in os.getenv('ALLOWED_USER_IDS', '').split(',') if x.strip()}
BUSY = set()
SLOTS = asyncio.Semaphore(2)

def permitted(update):
    return update.effective_chat.type == 'private' and (not ALLOWED or update.effective_user.id in ALLOWED)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if permitted(update):
        await update.message.reply_text('أهلًا 👻\nأرسل رابط ستوري سناب شات عام وسأحاول إرسال وسائطه هنا.\nحتى 20 ملفًا في الطلب، و45 ميجابايت للملف.\nالقصص الخاصة والمنتهية غير مدعومة.\n/myid لمعرفة رقم حسابك.')

async def myid(update, context):
    if permitted(update):
        await update.message.reply_text(str(update.effective_user.id))

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not permitted(update):
        return
    uid = update.effective_user.id
    if uid in BUSY:
        await update.message.reply_text('طلبك السابق قيد المعالجة، انتظر قليلًا.')
        return
    urls = re.findall(r'https://[^\s<>]+', update.message.text or '')
    if len(urls) != 1:
        await update.message.reply_text('أرسل رابط سناب شات واحدًا في كل رسالة.')
        return
    try:
        url = validate_url(urls[0])
    except (ValueError, DownloadError):
        await update.message.reply_text('أرسل رابط HTTPS صحيحًا من snapchat.com.')
        return
    BUSY.add(uid)
    status = None
    try:
        status = await update.message.reply_text('⏳ طلبك قيد المعالجة…')
        async with SLOTS:
            links = await asyncio.to_thread(media_links, url)
            sent, failed = 0, 0
            with tempfile.TemporaryDirectory(prefix='snapbot-') as tmp:
                for i, link in enumerate(links, 1):
                    try:
                        path = await asyncio.to_thread(download, link, Path(tmp), i)
                    except Exception:
                        failed += 1
                        continue
                    # Documents preserve original bytes and support images/videos alike.
                    with path.open('rb') as f:
                        await update.message.reply_document(f, filename=path.name, caption=f'👻 {i}/{len(links)}', read_timeout=90, write_timeout=90)
                    path.unlink(missing_ok=True)
                    sent += 1
            await status.edit_text(f'✅ أُرسل {sent} ملف. تعذر تنزيل {failed} ملف.' if sent else 'تعذر تنزيل الوسائط الموجودة في الرابط.')
    except DownloadError as exc:
        if status:
            await status.edit_text(str(exc))
    except Exception:
        if status:
            try:
                await status.edit_text('تعذر إكمال الطلب. حاول لاحقًا أو جرّب رابطًا عامًا آخر.')
            except Exception:
                pass
    finally:
        BUSY.discard(uid)

async def error(update, context):
    logging.warning('Telegram update failed (%s)', type(context.error).__name__)

async def ready(app):
    logging.warning("Bot authenticated successfully: @%s", app.bot.username)

def main():
    token = os.environ.get('BOT_TOKEN', '').strip()
    if not token:
        raise SystemExit('Set BOT_TOKEN in the server environment.')
    app = Application.builder().token(token).concurrent_updates(8).post_init(ready).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('myid', myid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_error_handler(error)
    try:
        app.run_polling(allowed_updates=['message'])
    except InvalidToken:
        raise SystemExit('BOT_TOKEN was rejected. Check the token in Render environment settings.') from None

if __name__ == '__main__':
    main()
