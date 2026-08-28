# Telegram Anonymous Bot

یک بات تلگرام شخصی و آزمایشی برای انتقال پیام‌های ناشناس از کاربران به صاحب بات و امکان پاسخ‌دهی ناشناس از طرف صاحب بات.

## ✨ ویژگی‌ها

- **Long Polling** با `run_polling()` - بدون نیاز به Webhook، سرور یا دامنه
- **فوروارد پیام‌ها** با اطلاعات کامل فرستنده (نام، یوزرنیم، User ID)
- **پاسخ‌دهی ناشناس** - صاحب بات با Reply به پیام فوروارد شده پاسخ می‌دهد
- **پشتیبانی از انواع پیام**: متن، عکس، ویدئو، فایل، صدا، Voice، Sticker
- **محدودیت نرخ (Rate Limiting)** برای جلوگیری از اسپم
- **ذخیره‌سازی پایدار** با SQLite - مپینگ‌ها بعد از ریستارت حفظ می‌شوند
- **آماده Deploy روی Railway Free Tier**
- **امنیت**: توکن و Owner ID در Environment Variables

---

## 📁 ساختار پروژه

```
telegram-anonymous-bot/
├── bot.py              # کد اصلی بات
├── requirements.txt    # وابستگی‌های Python
├── Procfile           # دستور اجرا برای Railway
├── messages.db        # دیتابیس SQLite (ایجاد خودکار)
└── README.md          # این فایل
```

---

## 🚀 راهنمای Deploy روی Railway

### ۱. ساخت Bot با BotFather

1. در تلگرام به [@BotFather](https://t.me/BotFather) مراجعه کنید
2. دستور `/newbot` را بفرستید
3. نام و یوزرنیم ربات را انتخاب کنید
4. **توکن (Token)** دریافت شده را کپی کنید - بعداً در Railway استفاده می‌شود

### ۲. ساخت GitHub Repository

1. در [GitHub](https://github.com) یک Repository جدید بسازید (مثلاً `telegram-anonymous-bot`)
2. Repository را `Public` یا `Private` انتخاب کنید
3. فایل‌های پروژه را Push کنید:

```bash
git init
git add .
git commit -m "Initial commit: Telegram Anonymous Bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/telegram-anonymous-bot.git
git push -u origin main
```

### ۳. اتصال GitHub به Railway

1. به [Railway](https://railway.app) بروید و با GitHub وارد شوید
2. روی **New Project** → **Deploy from GitHub repo** کلیک کنید
3. Repository خود را انتخاب کنید
4. Railway به‌صورت خودکار `Procfile` و `requirements.txt` را تشخیص می‌دهد

### ۴. تنظیم `BOT_TOKEN`

1. در داشبورد Railway، روی سرویس خود کلیک کنید
2. تب **Variables** را باز کنید
3. **New Variable** بزنید:
   - **Name**: `BOT_TOKEN`
   - **Value**: توکنی که از BotFather گرفتید (مثال: `123456789:AAAbcdefghijklmnopqrstuvwxyz`)

### ۵. تنظیم `OWNER_ID`

1. در همان تب **Variables**، **New Variable** بزنید:
   - **Name**: `OWNER_ID`
   - **Value**: آیدی عددی تلگرام شما (مثال: `8638588520`)

> **نحوه پیدا کردن User ID خود:**
> - به [@userinfobot](https://t.me/userinfobot) مراجعه کنید
> - یا در تلگرام دسکتاپ: راست‌کلیک روی پروفایل → Copy User ID

### ۶. Deploy

1. Railway به‌صورت خودکار Build و Deploy را شروع می‌کند
2. در تب **Deployments** پیشرفت را ببینید
3. وقتی **Active** شد، بات در حال اجراست ✅

### ۷. مشاهده Logs

1. در داشبورد Railway، تب **Logs** را باز کنید
2. باید پیام‌های زیر را ببینید:
   ```
   Loaded X message mappings from database
   Starting bot with long polling...
   ```

### ۸. تست `/start`

1. در تلگرام، ربات خود را باز کنید
2. دستور `/start` را بفرستید
3. باید پیام خوشامدگویی را ببینید

### ۹. تست ارسال و Reply

**از حساب کاربری دیگر (یا دوستان):**
1. به ربات پیام بدهید (متن، عکس، ویدئو، ...)
2. پیام باید با подтверждением «پیام شما ارسال شد» مواجه شود

**از حساب خودتان (Owner):**
1. در چت ربات، پیامی که فوروارد شده را پیدا کنید
2. روی آن پیام **Reply** (پاسخ) بزنید
3. متن/مدیای پاسخ را بفرستید
4. باید «پاسخ به کاربر ارسال شد» را ببینید
5. کاربر باید پاسخ را از طرف ربات دریافت کند

---

## ⚙️ تنظیمات پیشرفته

### Rate Limiting (محدودیت ارسال)

در `bot.py` می‌توانید این مقادیر را تغییر دهید:

```python
RATE_LIMIT_MAX = 5      # حداکثر پیام در بازه زمانی
RATE_LIMIT_WINDOW = 60  # بازه زمانی به ثانیه (۶۰ ثانیه = ۱ دقیقه)
```

### پاک‌سازی خودکار مپینگ‌های قدیمی

بات به‌صورت خودکار مپینگ‌های قدیمی‌تر از ۳۰ روز را در استارتاپ پاک می‌کند. برای تغییر:

```python
# در تابع main():
cleaned = db.cleanup_old(max_age_seconds=86400 * 30)  # ۳۰ روز
```

---

## 🔄 دو نسخه پیاده‌سازی

### نسخه فعلی (SQLite - پیشنهادی)
- **فایل**: `bot.py`
- **مپینگ‌ها در**: `messages.db` (SQLite)
- **مزیت**: مپینگ‌ها بعد از ریستارت Railway حفظ می‌شوند
- **مناسب برای**: تولید و استفاده واقعی

### نسخه در حافظه (In-Memory - ساده)
اگر می‌خواهید نسخه ساده‌تر بدون دیتابیس داشته باشید، در `bot.py`:
1. کلاس `MessageDatabase` و متغیر `db` را حذف کنید
2. فقط از `_message_cache` (dictionary) استفاده کنید
3. تابع `load_mappings_to_cache` و فراخوانی `db.cleanup_old` را حذف کنید

> ⚠️ **نکته مهم**: در نسخه In-Memory، با هر ریستارت Railway (deploy جدید، restart دستی، crash) تمام مپینگ‌ها از بین می‌روند و Reply به پیام‌های قبلی امکان‌پذیر نخواهد بود.

---

## 🛡️ امنیت و حریم خصوصی

- **توکن در Environment Variable** - هرگز در کد، GitHub، لاگ‌ها یا پیام‌ها نیست
- **Owner ID در Environment Variable** - قابل تغییر بدون Deploy مجدد
- **بدون لاگ‌گذاری پیام‌ها** - محتوای پیام‌های کاربران در لاگ‌ها ذخیره نمی‌شود
- **فقط Owner می‌تواند Reply کند** - چک `filters.User(OWNER_ID)` در هندلر
- **Rate Limiting** - جلوگیری از اسپم و سواستفاده

---

## 🐛 عیب‌یابی

### بات استارت نمی‌شود (Crash Loop)
1. Logs را در Railway چک کنید
2. متغیرهای `BOT_TOKEN` و `OWNER_ID` را تأیید کنید
3. مطمئن شوید توکن معتبر است (از BotFather چک کنید)

### Reply کار نمی‌کند
1. آیا روی پیام **فوروارد شده توسط بات** Reply زده شده؟ (روی پیام‌های دیگر Reply ندهید)
2. آیا `OWNER_ID` درست ست شده؟
3. Logs را برای خطای `Mapping not found` چک کنید

### پیام‌ها به Owner نرسیده
1. آیا Bot در چت Owner عضو است؟ (Owner باید یک‌بار `/start` بزند)
2. آیا `OWNER_ID` دقیقاً با آیدی عددی Owner مطابقت دارد؟

### Rate Limit خیلی سخت/نرم است
- `RATE_LIMIT_MAX` و `RATE_LIMIT_WINDOW` در `bot.py` را تنظیم کنید

---

## 📝 نکات فنی

### Python Version
- تست شده با **Python 3.10+**
- Railway به‌صورت پیش‌فرض Python 3.11+ استفاده می‌کند

### Dependencies
```txt
python-telegram-bot==21.6
```
نسخه ۲۱.x از PTB به‌صورت کامل async/await است و با Python 3.10+ سازگار است.

### Long Polling vs Webhook
این بات از **Long Polling** استفاده می‌کند:
- ✅ بدون نیاز به دامنه/SSL
- ✅ مناسب Railway Free Tier
- ✅ ساده‌تر برای پروژه‌های کوچک
- ❌ کمی بیشتر از منابع مصرف می‌کند (در حد قابل قبول)

### دیتابیس SQLite
- فایل `messages.db` در دایرکتوری پروژه ایجاد می‌شود
- Railway Free Tier سیستم فایل را در restart حفظ **نمی‌کند** (ephemeral filesystem)
- برای persistence واقعی در تولید، از **PostgreSQL** (Railway Add-on) یا **Redis** استفاده کنید

> **مهم**: در Railway Free Tier، فایل `messages.db` پس از هر Deploy/Restart **از بین می‌رود**. برای حفظ مپینگ‌ها در تولید، یکی از موارد زیر را انجام دهید:
> 1. PostgreSQL Add-on را در Railway فعال کنید و کد را برای استفاده از آن تغییر دهید
> 2. از Redis برای ذخیره مپینگ‌ها استفاده کنید
> 3. از Volume persistent (تنها در پلن‌های پولی Railway) استفاده کنید

---

## 📄 مجوز

این پروژه برای استفاده شخصی و آزمایشی است. استفاده از آن برای:
- ❌ آزار و اذیت کاربران
- ❌ تهدید یا ترساندن
- ❌ فریب‌دهی (Phishing/Scam)
- ❌ جمع‌آوری مخفیانه اطلاعات

**ممنوع** است. نویسنده هیچ مسئولیتی در قبال سوءاستفاده نمی‌پذیرد.

---

## 🤝 مشارکت

این یک پروژه آزمایشی شخصی است. برای پیشنهاد بهبود یا گزارش باگ، Issue در GitHub باز کنید.

---

**ساخته شده با ❤️ برای یادگیری و تست ایده‌ها**