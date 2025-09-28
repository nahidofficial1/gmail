import time, base64, re, random, requests, asyncio
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from telegram import Bot, Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.ext import CallbackContext
from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import uvicorn
import base64, json

# এখানে বসাও 👇
app_webhook = FastAPI()
telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# ==========================
# User Settings
# ==========================
TELEGRAM_TOKEN = "7996167358:AAFxm9pOeiC2yeOO6BwoIkK4ghxL_KrNa3c"

ADMIN_ID = 7982728873   # আপনার টেলিগ্রাম আইডি (CHAT_ID কেটে দিন)
GLOBAL_LIMIT = 0
CLIENT_ID = "847903205447-0071tvj3osupk3chu3gitu9589chrgtm.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REFRESH_TOKEN = "1//0ch75pNMGjwExCgYIARAAGAwSNwF-L9IriMNVu3K0INZUoAW9hysbUlXhrVsfVz6dys7bvk4xbP2dD2rBDqzvIg1Yil1M7z-9PWI"

bot = Bot(token=TELEGRAM_TOKEN)

# প্রিয় ইউজারদের লিস্ট (whitelist)
favorite_users = {
    7831083389,
    8098492183,
    7566775855,
    7800920494,
    8097531747,
    6664751741,
    7535032861,
    6204788933
}

# প্রতিটি ইউজারের জন্য আলাদা last_checked_time রাখার dict
user_last_checked = {}

# প্রতিটি ইউজারের জন্য আলাদা processed_ids রাখার dict
user_processed_ids = {}

# অনুমোদিত ইউজারদের লিস্ট (শুধু অ্যাডমিন এড করতে পারবে)
approved_for_numbers = set()

admin_pending_range = {}   # এডমিন কোন রেঞ্জ বানাচ্ছে সেটা ট্র্যাক করবে

import json, os

RANGE_FILE = "ranges.json"

def load_ranges():
    if not os.path.exists(RANGE_FILE):
        return {}
    with open(RANGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_ranges(ranges):
    with open(RANGE_FILE, "w", encoding="utf-8") as f:
        json.dump(ranges, f, ensure_ascii=False, indent=2)

USERS_FILE = "users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# ইউজারের সিলেক্ট করা রেঞ্জ এবং প্রগ্রেস ডাটা
user_selected_range = {}
user_data = {}
support_data = {}

# ==========================
# Auto get Access Token
# ==========================
def get_access_token():
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    r = requests.post(token_url, data=data)
    j = r.json()
    if "access_token" not in j:
        raise Exception(f"Failed to get token: {j}")
    return j["access_token"]

# ==========================
# Gmail API Service
# ==========================
ACCESS_TOKEN = get_access_token()

creds = Credentials(
    token=ACCESS_TOKEN,
    refresh_token=REFRESH_TOKEN,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    scopes=["https://mail.google.com/"]
)

if creds.expired and creds.refresh_token:
    creds.refresh(Request())

service = build('gmail', 'v1', credentials=creds)

# ==========================
# বাকি আপনার Copy5 কোড (Inbox Check, Random Gmail, Telegram Handlers ইত্যাদি) একদম আগের মতো থাকবে
# শুধু উপরে এই Access Token এর অংশটা নতুন
# ==========================

# ==========================
# Track last checked time
# ==========================
last_checked_time = int(time.time() * 1000)  # বর্তমান সময় (মিলিসেকেন্ড)

# ==========================
# Track processed message IDs
# ==========================
processed_ids = set()

# ==========================
# Gmail OTP Checker
# ==========================
def check_email(max_results=10, since_time=0, filter_email=None, return_with_email=False, user_id=None):
    if user_id not in user_processed_ids:
        user_processed_ids[user_id] = set()
    processed_ids = user_processed_ids[user_id]
    try:
        results = service.users().messages().list(
            userId='me',
            maxResults=max_results,
            q=f"after:{int(since_time/1000)}" if since_time else None
        ).execute()

        messages = results.get('messages', [])
        found_codes = []
        newest_time = since_time

        for msg in messages:
            msg_id = msg['id']
            if msg_id in processed_ids:
                continue

            txt = service.users().messages().get(userId='me', id=msg_id, format="full").execute()

            # === To address বের করা ===
            headers = txt["payload"].get("headers", [])
            to_address = None
            for h in headers:
                if h["name"] == "To":
                    to_address = h["value"]
                    break

            if filter_email and to_address and to_address.strip() != filter_email.strip():
                continue

            mail_time = int(txt.get("internalDate", 0))
            if mail_time > newest_time:
                newest_time = mail_time

            parts = []
            payload = txt.get('payload', {})

            def extract_parts(payload):
                if 'parts' in payload and payload['parts']:
                    for part in payload['parts']:
                        extract_parts(part)
                if 'body' in payload and payload['body'] and 'data' in payload['body']:
                    parts.append(payload['body']['data'])

            extract_parts(payload)

            for p in parts:
                try:
                    data = base64.urlsafe_b64decode(p).decode(errors='ignore')
                except Exception:
                    continue

                otp_matches = re.findall(r'\b\d{4,8}\b', data)
                for o in otp_matches:
                    if to_address:
                        if return_with_email:
                            found_codes.append((to_address, o))   # (email, otp)
                        else:
                            found_codes.append(f"{o}  (📥 To: {to_address})")
                    else:
                        found_codes.append(o)

            processed_ids.add(msg_id)

        return found_codes, newest_time
    except Exception as e:
        return [f"⚠️ Error: {e}"], since_time

# ==========================
# Random Gmail Casing
# ==========================
def random_case_gmail(email):
    name, domain = email.split("@")
    new_name = "".join(
        c.upper() if random.choice([True, False]) else c.lower()
        for c in name
    )
    return f"{new_name}@{domain}"

# ==========================
# Telegram Handlers
# ==========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [["🎯 Gmail", "📞 নাম্বার নিন", "Capacity 🔋"]]
    if update.effective_user.id == ADMIN_ID:
        reply_keyboard.append(["🗑 Delete OTPs"])
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "✋ হ্যালো! নিচের বাটন থেকে বেছে নিন:",
        reply_markup=markup
    )    
    

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

# ==========================
# Auto-check OTP
# ==========================
async def auto_check_otp(app):
    while True:
        try:
            for user_id, assigned_email in user_gmail_map.items():
                last_time = user_last_checked.get(user_id, 0)

                codes, newest_time = check_email(
                    max_results=10,
                    since_time=last_time,
                    filter_email=assigned_email,
                    return_with_email=True,
                    user_id=user_id
                )

                if codes:
                    for email, otp in codes:
                        if assigned_email.lower() == email.lower():
                            otp_text = (
                                "✅ *New OTP Received!*\n\n"
                                f"📧 *Email:* `{assigned_email}`\n"
                                f"🔑 *OTP Code:* \n\n"
                                f"━━━━━━━━━━━━━━\n"
                                f"🔐 `{otp}`\n"
                                f"━━━━━━━━━━━━━━\n\n"
                                "_Use this code to complete your verification._"
                            )

                            await app.bot.send_message(
                                chat_id=user_id,
                                text=otp_text,
                                parse_mode="Markdown"
                            )

                # প্রতিটি ইউজারের জন্য আলাদা last_checked_time আপডেট
                user_last_checked[user_id] = newest_time

        except Exception as e:
            print("Auto-check error:", e)

        await asyncio.sleep(1)  # প্রতি 1 সেকেন্ড পর চেক করবে (ফাস্ট রেসপন্সের জন্য)

# ইউজার-ভিত্তিক Gmail ম্যাপ
user_gmail_map = {}

# Gmail + Number Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # 🎯 Gmail ফিচার
    if text == "🎯 Gmail":
        gmail = "nahidkhan4op@gmail.com"
        randomized = random_case_gmail(gmail)

        # ইউজারের সাথে Gmail লিঙ্ক করো
        user_gmail_map[user_id] = randomized

        keyboard = [[InlineKeyboardButton("📥 Check OTP", callback_data=f"otp|{randomized}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🎲 Random Gmail: `{randomized}`",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return

    # 🗑 OTP ডিলিট (শুধু অ্যাডমিন)
    elif text == "🗑 Delete OTPs" and user_id == ADMIN_ID:
        msgs = service.users().messages().list(
            userId="me",
            q="newer_than:30d",
            maxResults=100
        ).execute().get("messages", [])
        count = len(msgs)

        if count == 0:
            await update.message.reply_text("❌ কোনো OTP মেইল পাওয়া যায়নি।")
        else:
            keyboard = [[InlineKeyboardButton(f"🗑 Delete All ({count})", callback_data="deleteall")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"📥 ইনবক্সে {count} টি OTP মেইল পাওয়া গেছে।\n👉 ডিলিট করতে নিচের বাটনে ক্লিক করুন:",
                reply_markup=reply_markup
            )
        return

    elif text == "📞 নাম্বার নিন":
        user_id = update.effective_user.id
        if user_id != ADMIN_ID and user_id not in favorite_users:
            await update.message.reply_text("🚫 আপনার এই ফিচার ব্যবহার করার অনুমতি নেই।")
            return

        support_data.pop(user_id, None)
        user_data.pop(user_id, None)

        ranges = load_ranges()
        if not ranges:
            await update.message.reply_text("❌ কোনো নাম্বার রেঞ্জ পাওয়া যায়নি।")
            return

        # Inline Keyboard দিয়ে রেঞ্জ দেখানো
        range_names = list(ranges.keys())
        buttons = [
            [InlineKeyboardButton(name, callback_data=f"selectrange_{i}")]
            for i, name in enumerate(range_names)
        ]
        context.chat_data[f"range_map_{user_id}"] = range_names
        reply_markup = InlineKeyboardMarkup(buttons)

        await update.message.reply_text("📂 কোন রেঞ্জের নাম্বার নিতে চান?", reply_markup=reply_markup)
        return

# 📦 Capacity চেক (Admin + Favorite Users)
    elif text == "Capacity 🔋":
        if update.effective_user.id != ADMIN_ID and update.effective_user.id not in favorite_users:
            await update.message.reply_text("🚫 আপনার এই ফিচার ব্যবহার করার অনুমতি নেই।")
            return

        ranges = load_ranges()
        total = sum(len(v) for v in ranges.values())
        msg = [f"📦 মোট বাকি নাম্বার: {total} টি"]

        if ranges:
            msg.append("\n📂 রেঞ্জভিত্তিক স্ট্যাটাস:")
            for rn, lst in ranges.items():
                msg.append(f"• {rn}: {len(lst)}")

        await update.message.reply_text("\n".join(msg))
        return

    # 📝 ইউজার নাম্বার কাউন্ট দিলে
    elif user_id in user_data and user_data[user_id] == "awaiting_number_count":
        try:
            count = int(text.strip())
        except:
            await update.message.reply_text("❌ একটি সঠিক সংখ্যা দিন।")
            return

        users = load_users()
        u = users.get(str(user_id), {"count": 0, "limit": GLOBAL_LIMIT, "total": 0})

        # এডমিন হলে লিমিট চেক হবে না
        if user_id != ADMIN_ID:
            # 🔥 কেস ১: ইউজারের লিমিট একদম শেষ হয়ে গেছে
            if u["count"] >= u["limit"]:
                await update.message.reply_text("⚠️ আপনি পরবর্তী সুযোগের জন্য অপেক্ষা করুন।")

                # 👉 এডমিনকে জানানো
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        f"⛔ ইউজার `{user_id}` তার {u['limit']} টির লিমিট শেষ করেছে।\n"
                        f"👉 তাকে নতুন সুযোগ দিতে চান?"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ সুযোগ দিন", callback_data=f"resetuser_{user_id}")]
                    ])
                )
                return

            # 🔥 কেস ২: ইউজার লিমিট ছাড়িয়ে নিতে চাইছে
            if u["count"] + count > u["limit"]:
                await update.message.reply_text(
                    f"⚠️ আপনার লিমিট {u['limit']} টি। আপনি ইতিমধ্যে {u['count']} টি নিয়েছেন, "
                    f"তাই আর {u['limit'] - u['count']} টির বেশি নিতে পারবেন না।"
                )
                return

            # 🔥 কেস ৩: একবারে গ্লোবাল লিমিটের বেশি চাইছে
            if count > GLOBAL_LIMIT:
                await update.message.reply_text(
                    f"⚠️ একবারে সর্বোচ্চ {GLOBAL_LIMIT} টি নাম্বার নিতে পারবেন।"
                )
                return

        selected_range = user_selected_range.get(user_id)
        ranges = load_ranges()

        if not selected_range or selected_range not in ranges:
            await update.message.reply_text("❌ রেঞ্জ পাওয়া যায়নি। আবার 📞 নাম্বার নিন দিন।")
            user_data.pop(user_id, None)
            return

        available = ranges[selected_range]
        if count > len(available):
            await update.message.reply_text(
                f"⚠️ {selected_range} রেঞ্জে মাত্র {len(available)} টি নাম্বার আছে।"
            )
            return

        # ✅ নাম্বার সরবরাহ
        taken = available[:count]
        ranges[selected_range] = available[count:]
        save_ranges(ranges)

        # ✅ ইউজারের count আপডেট
        u["count"] += count
        u["total"] += count
        users[str(user_id)] = u
        save_users(users)

        user_data.pop(user_id, None)
        await update.message.reply_text(
            f"✅ আপনার নাম্বারগুলো:\n\n" + "\n".join(taken)
        )
        return

    # 📝 এডমিন রেঞ্জের নাম দিলে
    elif user_id in user_data and user_data[user_id] == "awaiting_range_name":
        range_name = text.strip()
        admin_pending_range[user_id] = range_name
        user_data[user_id] = "awaiting_range_numbers"

        await update.message.reply_text(
            f"📂 রেঞ্জ নির্ধারিত: {range_name}\n\n"
            "📝 এখন .txt ফাইল আপলোড করুন অথবা নাম্বারগুলো ম্যানুয়ালি লিখে পাঠান (প্রতি লাইনে একটি করে নাম্বার)।"
        )
        return

    # 📝 এডমিন নাম্বার লিস্ট দিলে
    elif user_id in user_data and user_data[user_id] == "awaiting_range_numbers":
        numbers = text.strip().split("\n")
        range_name = admin_pending_range.get(user_id)

        ranges = load_ranges()
        if range_name not in ranges:
            ranges[range_name] = []

        ranges[range_name].extend(numbers)
        save_ranges(ranges)

        user_data.pop(user_id, None)
        admin_pending_range.pop(user_id, None)

        await update.message.reply_text(
            f"✅ {range_name} রেঞ্জে {len(numbers)} টি নাম্বার যোগ করা হয়েছে।"
        )
        return


# ✅ Gmail Pub/Sub webhook route
@app_webhook.post("/webhook")
async def gmail_webhook(request: Request):
    body = await request.json()
    message = body.get("message", {})
    data = message.get("data")

    if data:
        decoded = base64.b64decode(data).decode("utf-8")
        msg_json = json.loads(decoded)
        print("📩 Gmail Push Notification:", msg_json)

        # 👉 এখানেই OTP process ফাংশন কল করবেন
        # await process_new_mail(msg_json)

    return {"status": "ok"}


# ✅ Telegram webhook route
@app_webhook.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


@app_webhook.get("/")
@app_webhook.head("/")
async def root():
    return {"status": "ok", "message": "Bot server is running 🚀"}




# ✅ Inline Button এর হ্যান্ডলার
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("otp|"):
        email = query.data.split("|")[1]
        user_id = query.from_user.id
        last_time = user_last_checked.get(user_id, 0)

        codes, newest_time = check_email(
            max_results=10,
            since_time=last_time,
            filter_email=email,
            user_id=user_id
        )
        user_last_checked[user_id] = newest_time

        # Inline Button: Refresh + Copy
        keyboard = [
            [InlineKeyboardButton("📥 Refresh OTP", callback_data=f"otp|{email}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if codes and not codes[0].startswith("⚠️"):
            # শুধু সর্বশেষ OTP নিন
            otp_code = codes[0]

            otp_text = (
                "✅ *New OTP Received!*\n\n"
                f"📧 *Email:* `{email}`\n"
                f"🔑 *OTP Code:* \n\n"
                f"━━━━━━━━━━━━━━\n"
                f"🔐 `{otp_code}`\n"
                f"━━━━━━━━━━━━━━\n\n"
                "_Use this code to complete your verification._"
            )

            if query.message.text != otp_text:
                await query.edit_message_text(
                    text=otp_text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_reply_markup(reply_markup=reply_markup)
        else:
            new_text = f"❌ No OTP found yet for {email}"
            if query.message.text != new_text:
                await query.edit_message_text(
                    text=new_text,
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_reply_markup(reply_markup=reply_markup)

    elif query.data == "deleteall" and query.from_user.id == ADMIN_ID:
        msgs = service.users().messages().list(
            userId="me",
            q="newer_than:30d",
            maxResults=100
        ).execute().get("messages", [])
        count = len(msgs)

        if count == 0:
            await query.edit_message_text("❌ কোনো OTP মেইল পাওয়া যায়নি।")
        else:
            for m in msgs:
                service.users().messages().delete(userId="me", id=m["id"]).execute()

            await query.edit_message_text(f"✅ {count} টি OTP মেইল সফলভাবে ডিলিট করা হয়েছে।")

    elif query.data.startswith("selectrange_"):   # ⚡ এটা ফাংশনের ভেতরে রাখতে হবে
        user_id = query.from_user.id
        map_key = f"range_map_{user_id}"
        range
