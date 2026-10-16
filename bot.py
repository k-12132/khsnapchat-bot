import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import InvalidToken, TelegramError
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
from downloader import DownloadError, validate_url, media_links, download

# Avoid logging Telegram request URLs, which contain the bot token.
logging.basicConfig(level=logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
ALLOWED = {int(x.strip()) for x in os.getenv('ALLOWED_USER_IDS', '').split(',') if x.strip()}
REQUIRED_CHANNEL = '@kh01ed'
CHANNEL_URL = 'https://t.me/kh01ed'
BUSY = set()
SLOTS = asyncio.Semaphore(2)

def permitted(update):
    return update.effective_chat.type == 'private' and (not ALLOWED or update.effective_user.id in ALLOWED)


def subscription_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📢 اشترك في القناة', url=CHANNEL_URL)],
        [InlineKeyboardButton('✅ تحقّق من اشتراكي', callback_data='check_subscription')],
    ])


def membership_error_reason(exc):
    message = str(exc).lower()
    for reason in ('chat not found', 'bot is not a member', 'member list is inaccessible', 'not enough rights', 'user not found', 'forbidden'):
        if reason in message:
            return reason
    return type(exc).__name__

async def subscribed(context, user_id):
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
    except TelegramError as exc:
        logging.warning('Subscription check unavailable: %s', membership_error_reason(exc))
        return None
    return member.status in ('creator', 'administrator', 'member') or (
        member.status == 'restricted' and bool(getattr(member, 'is_member', False))
    )

async def require_subscription(update, context):
    result = await subscribed(context, update.effective_user.id)
    if result is True:
        return True
    message = '🎬 حمّل ستوري Snapchat بسهولة !\n\n📢 للبدء، اشترك في القناة التالية ثم اضغط زر تحقق من اشتراكي :'
    await update.effective_message.reply_text(message, reply_markup=subscription_buttons())
    return False

async def check_subscription(update, context):
    if not permitted(update):
        return
    await update.callback_query.answer()
    if await require_subscription(update, context):
        await update.effective_message.reply_text('✅ تم التحقق من اشتراكك! أرسل رابط ستوري سناب عام للتحميل.')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if permitted(update) and await require_subscription(update, context):
        await update.message.reply_text('أهلًا 👻\nأرسل رابط ستوري سناب شات عام وسأحاول إرسال وسائطه هنا.\nحتى 20 ملفًا في الطلب، و45 ميجابايت للملف.\nالقصص الخاصة والمنتهية غير مدعومة.\n/myid لمعرفة رقم حسابك.')

async def myid(update, context):
    if permitted(update):
        await update.message.reply_text(str(update.effective_user.id))

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not permitted(update):
        return
    if not await require_subscription(update, context):
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
            if sent:
                await send_follow_invitation(update.message)
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


async def send_follow_invitation(message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('👻 تابعني على سناب', url='https://snapchat.com/t/d9GtFjtN')],
        [InlineKeyboardButton('🎵 تابعني على تيك توك', url='https://www.tiktok.com/@kh01ed')],
    ])
    try:
        await message.reply_text(
            '💛 استفدت من سنابك؟ متابعتك تسعدني وتدعم استمرار البوت!\n'
            'تابعني على سناب وتيك توك للمحتوى التقني والشروحات المفيدة 👇',
            reply_markup=keyboard,
        )
    except TelegramError:
        logging.warning('Follow invitation could not be sent.')

async def error(update, context):
    logging.warning('Telegram update failed (%s)', type(context.error).__name__)

async def ready(app):
    logging.warning("Bot authenticated successfully: @%s", app.bot.username)
    try:
        member = await app.bot.get_chat_member(REQUIRED_CHANNEL, app.bot.id)
        logging.warning('Subscription gate channel=%s bot_admin=%s', REQUIRED_CHANNEL, member.status in ('administrator', 'creator'))
    except TelegramError as exc:
        logging.warning('Subscription gate access unavailable: %s', membership_error_reason(exc))

def main():
    token = os.environ.get('BOT_TOKEN', '').strip()
    if not token:
        raise SystemExit('Set BOT_TOKEN in the server environment.')
    app = Application.builder().token(token).concurrent_updates(8).post_init(ready).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('myid', myid))
    app.add_handler(CallbackQueryHandler(check_subscription, pattern='^check_subscription$'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_error_handler(error)
    try:
        app.run_polling(allowed_updates=['message', 'callback_query'])
    except InvalidToken:
        raise SystemExit('BOT_TOKEN was rejected. Check the token in Render environment settings.') from None

if __name__ == '__main__':
    main()
