# بوت تنزيل ستوري سناب شات 👻

نسخة أولية مستقلة بواجهة عربية. تستقبل رابط HTTPS من سناب شات وتحاول استخراج روابط الصور والفيديو من بيانات JSON المضمّنة في صفحة الويب العامة، ثم ترسل الملفات الأصلية في المحادثة الخاصة وتحذف الملفات المؤقتة.

## حالة التحقق
جرى اختبار تحليل الروابط واستخراج البيانات محليًا بصفحات اختبار مصطنعة. لم تُختبر هذه النسخة مع رابط سناب شات حقيقي أو حساب تيليجرام، ولم يتم نشرها. لم يمكن التحقق من بنية صفحات سناب الحالية بسبب تعذر الوصول الشبكي أثناء الإنشاء. لذلك المستخرج تجريبي وقد يحتاج تعديلاً بعد تجربة رابط عام. لا يوجد ضمان بدعم جميع روابط القصص أو الاختصارات. لا يدعم تجاوز تسجيل الدخول أو الوسائط المشفرة أو القصص الخاصة والمنتهية.

## إنشاء البوت وتشغيله
1. افتح https://t.me/BotFather وأرسل `/newbot`، ثم اختر اسمًا ومعرّفًا للبوت.
2. احفظ التوكن في متغير بيئة `BOT_TOKEN` على جهازك أو الاستضافة. لا تضعه في ملفات المشروع المنشورة أو في مستودع Git.
3. استخدم Python 3.11 أو أحدث:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
read -rsp 'Bot token: ' BOT_TOKEN
export BOT_TOKEN
python bot.py
```

على Windows فعّل البيئة بالأمر `.venv\Scripts\activate` واضبط متغير البيئة من إعدادات النظام. ملف `.env.example` مثال فقط؛ البرنامج لا يقرأ ملفات `.env` تلقائيًا.

افتح محادثة البوت وأرسل `/start` ثم رابط القصة العامة. لمعرفة رقم حسابك أرسل `/myid`. لقصر الاستخدام عليك، عيّن `ALLOWED_USER_IDS` إلى رقمك، أو عدة أرقام مفصولة بفواصل، ثم أعد تشغيل البوت. ترك المتغير فارغًا يسمح لأي مستخدم باستخدامه في الخاص.

## Docker أو Render
```bash
docker build -t snapchat-bot .
docker run --rm --env-file .env snapchat-bot
```
انسخ `.env.example` إلى `.env` وأدخل القيم محليًا قبل أمر Docker. لا تشارك هذا الملف. في Render استخدم خدمة Background Worker مع Docker، واضبط `BOT_TOKEN` و`ALLOWED_USER_IDS` من لوحة متغيرات البيئة. يحتاج البوت إلى عملية مستمرة واتصال خارجي بتيليجرام وسناب شات، ولا يحتاج Webhook أو منفذ HTTP. شغّل نسخة واحدة فقط من البوت لكل توكن. تكلفة الاستضافة تعتمد على المزود والخطة.

## الحدود
- حتى 20 وسيطًا لكل طلب؛ تُهمل الوسائط التالية لهذا الحد.
- 45 ميجابايت لكل ملف؛ تُتجاوز الملفات الكبيرة أو غير المدعومة.
- طلبان متزامنان، وطلب نشط واحد لكل مستخدم.
- الصور والفيديو تُرسل كمستندات للحفاظ على الملف الأصلي. لا توجد قاعدة بيانات أو أرشفة دائمة أو دمج للمقاطع.
- إذا تغيرت بنية صفحة سناب، يُعدّل المستخرج `extract_media` في `downloader.py` بعد فحص صفحة عامة فعلية.
- نزّل المحتوى الذي تملكه أو لديك إذن بحفظه.

## الاختبارات
```bash
python -m unittest discover -s tests -v
```


## إعداد @Khsnapchat_bot على Render
ملف `render.yaml` مرفق لخدمة مستقلة باسم `khsnapchat-bot`. ارفع محتويات مجلد `snapchat-bot` إلى جذر مستودع GitHub مستقل، ثم اربطه من Render عبر New → Blueprint. أدخل توكن @Khsnapchat_bot في BOT_TOKEN عندما يطلبه Render، وراجع الخطة والتكلفة قبل الإنشاء. لا يحتاج البوت منفذ HTTP لأن الخدمة Background Worker. أبقِ عدد النسخ نسخة واحدة. استخدم ALLOWED_USER_IDS لتحديد من يمكنه استخدام البوت عند الحاجة.

توثيق الإعدادات: https://render.com/docs/blueprint-spec

هذا تجهيز للنشر فقط؛ لم تُنشأ خدمة Render ولم يُضبط التوكن ولم يجر اختبار تنزيل فعلي بعد.

## Required Snapchat activation

Configure both services before deploying the TikTok gate. Set the same randomly generated `BOT_ACTIVATION_SECRET` (32+ characters) in both services. The activation link automatically includes the return bot username; `TIKTOK_BOT_USERNAME` is an optional fallback for old activation links. Keep secrets in server environment settings only. Deploy the Snapchat companion first.

Users join @kh01ed, open @Khsnapchat_bot using the activation button, press Start, then use its return button. Signed receipts expire in ten minutes and are bound to the Telegram user ID. TikTok stores activations in SQLite; use a persistent BOT_DB_PATH to retain them after deployments. This verifies starting Snapchat once, not whether it stays unblocked afterward. Missing or mismatched secrets deny new activations.
