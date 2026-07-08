import os
import sys
import sqlite3
import asyncio
import threading
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from telegram import Update, Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

sys.stdout = sys.stderr

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
DB_PATH = "/tmp/users.db"
DEBUG_FILE = "/tmp/debug.txt"

def debug_log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(DEBUG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

# ---------- دیتابیس ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS notify_list (
            chat_id INTEGER PRIMARY KEY,
            username TEXT
        )
    ''')
    conn.commit()
    conn.close()
    debug_log("✅ دیتابیس ساخته شد")

def add_user(chat_id, username, full_name):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO users (chat_id, username, full_name) VALUES (?, ?, ?)",
            (chat_id, username, full_name)
        )
        conn.commit()
        conn.close()
        debug_log(f"✅ کاربر ذخیره شد: {full_name} | {chat_id}")
        return True
    except Exception as e:
        debug_log(f"❌ خطا در add_user: {e}\n{traceback.format_exc()}")
        return False

def add_to_notify(chat_id, username):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO notify_list (chat_id, username) VALUES (?, ?)",
            (chat_id, username)
        )
        conn.commit()
        conn.close()
        debug_log(f"🔔 کاربر به لیست اعلان اضافه شد: {chat_id}")
    except Exception as e:
        debug_log(f"❌ خطا در add_to_notify: {e}")

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ---------- ربات ----------
ptb_app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    debug_log("🚀 تابع start فراخوانی شد")
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = user.username if user.username else "بدون یوزرنیم"
    full_name = user.full_name

    success = add_user(chat_id, username, full_name)
    if not success:
        await update.message.reply_text("⚠️ خطایی در ثبت اطلاعات رخ داد. لطفاً مجدد تلاش کنید.")
    else:
        message_text = (
            "با سلام و احترام\n\n"
            "با توجه به استقبال گسترده و حجم بالای درخواست‌ها، در حال حاضر با ازدحام موقت سامانه مواجه هستیم. "
            "از این‌رو ظرفیت پاسخ‌گویی آنی محدود شده است.\n\n"
            "خواهشمندیم با شکیبایی همراه باشید؛ به تمامی همراهان گرامی به‌ترتیب اولویت رسیدگی خواهد شد. "
            "لطفاً چند ساعت دیگر مجدداً پیام دهید.\n\n"
            "چنانچه مایلید به‌محض در دسترس قرار گرفتن اکانت‌ها به شما اطلاع‌رسانی شود، دکمهٔ زیر را ارسال فرمایید:"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔔 خبرم کن", callback_data="notify_me")]
        ])
        await update.message.reply_text(message_text, reply_markup=keyboard)

    if OWNER_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=int(OWNER_CHAT_ID),
                text=f"🆕 کاربر جدید:\nنام: {full_name}\nیوزرنیم: @{username}\nآیدی: {chat_id}"
            )
        except Exception as e:
            debug_log(f"❌ خطا در ارسال به مالک: {e}")

async def notify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "notify_me":
        user = query.from_user
        chat_id = query.message.chat.id
        username = user.username if user.username else "بدون یوزرنیم"
        add_to_notify(chat_id, username)
        await query.edit_message_text(
            text="✅ ثبت شد!\nبه‌محض در دسترس قرار گرفتن اکانت‌ها، به شما اطلاع‌رسانی خواهد شد.",
        )

ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(CallbackQueryHandler(notify_callback))

# ---------- Flask ----------
flask_app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>داشبورد کاربران ربات</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Tahoma', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
            width: 100%;
            max-width: 1000px;
            backdrop-filter: blur(10px);
        }
        h1 { text-align: center; color: #333; margin-bottom: 10px; font-size: 28px; }
        .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .counter { background: #764ba2; color: white; padding: 8px 20px; border-radius: 30px; font-size: 16px; }
        button.refresh {
            background: #667eea; color: white; border: none; padding: 10px 25px;
            border-radius: 30px; cursor: pointer; font-size: 16px; transition: 0.3s;
            display: flex; align-items: center; gap: 8px;
        }
        button.refresh:hover { background: #5a67d8; transform: scale(1.03); }
        .table-wrapper { overflow-x: auto; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 15px; overflow: hidden; }
        th { background: #667eea; color: white; padding: 15px; text-align: center; font-weight: normal; }
        td { padding: 12px 15px; text-align: center; border-bottom: 1px solid #eee; color: #444; }
        tr:last-child td { border-bottom: none; }
        tr:hover { background: #f0f0ff; }
        .no-data { text-align: center; padding: 40px; color: #888; font-size: 18px; }
        .loading { text-align: center; color: #888; padding: 20px; }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        tbody tr { animation: fadeIn 0.3s ease-in; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 کاربران ثبت‌نامی</h1>
        <div class="header-row">
            <span class="counter" id="userCount">۰ کاربر</span>
            <button class="refresh" onclick="fetchUsers()">🔄 به‌روزرسانی</button>
        </div>
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>ردیف</th>
                        <th>نام</th>
                        <th>یوزرنیم</th>
                        <th>شناسه عددی</th>
                        <th>تاریخ ثبت</th>
                    </tr>
                </thead>
                <tbody id="userTableBody">
                    <tr><td colspan="5" class="loading">در حال بارگذاری...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    <script>
        async function fetchUsers() {
            const tbody = document.getElementById('userTableBody');
            tbody.innerHTML = '<tr><td colspan="5" class="loading">در حال دریافت...</td></tr>';
            try {
                const response = await fetch('/api/users');
                const users = await response.json();
                document.getElementById('userCount').textContent = users.length + ' کاربر';
                if (users.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="no-data">هنوز کاربری ثبت نشده است</td></tr>';
                    return;
                }
                let html = '';
                users.forEach((user, index) => {
                    html += `
                        <tr>
                            <td>${index + 1}</td>
                            <td>${escapeHtml(user.full_name)}</td>
                            <td>@${escapeHtml(user.username || 'ندارد')}</td>
                            <td><code>${user.chat_id}</code></td>
                            <td>${new Date(user.created_at).toLocaleString('fa-IR')}</td>
                        </tr>`;
                });
                tbody.innerHTML = html;
            } catch (err) {
                tbody.innerHTML = '<tr><td colspan="5" class="loading">خطا در دریافت داده‌ها</td></tr>';
                console.error(err);
            }
        }
        function escapeHtml(text) {
            const map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};
            return String(text).replace(/[&<>"']/g, m => map[m]);
        }
        fetchUsers();
        setInterval(fetchUsers, 10000);
    </script>
</body>
</html>
'''

@flask_app.route("/")
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@flask_app.route("/api/users")
def api_users():
    return jsonify(get_all_users())

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    # تزریق آپدیت به صف ربات (که توسط ترد زیر پردازش می‌شود)
    ptb_app.update_queue.put_nowait(update)
    return "OK"

# ---------- اجرای ربات در یک Event Loop جداگانه ----------
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_bot())
    except Exception as e:
        debug_log(f"❌ Bot thread crashed: {e}")
        traceback.print_exc()

async def start_bot():
    debug_log("🚀 راه‌اندازی ربات...")
    await ptb_app.initialize()
    await ptb_app.start()
    debug_log("✅ ربات start شد. در حال پردازش آپدیت‌ها...")

    # تنظیم Webhook (اگر متغیر محیطی موجود بود)
    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    if external_url:
        webhook_url = f"{external_url}/webhook"
        bot = Bot(token=BOT_TOKEN)
        await bot.delete_webhook()
        await bot.set_webhook(url=webhook_url)
        debug_log(f"✅ Webhook تنظیم شد: {webhook_url}")
    else:
        debug_log("⚠️ RENDER_EXTERNAL_URL پیدا نشد. Webhook را دستی تنظیم کنید.")

    # زنده نگه داشتن رویداد
    while True:
        await asyncio.sleep(3600)

# ---------- اجرا ----------
if __name__ == "__main__":
    debug_log("===== شروع برنامه =====")
    init_db()
    debug_log("✅ دیتابیس آماده شد.")

    # ربات را در یک ترد جداگانه راه‌اندازی کن
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    debug_log("✅ ترد ربات شروع شد.")

    # Flask در ترد اصلی
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
