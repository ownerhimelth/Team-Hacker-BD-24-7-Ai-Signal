import os, asyncio, logging, re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from db import DB
from api_client import fetch_history
from strategy import make_prediction, classify_number

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip()
REGISTRATION_LINK = os.getenv("REGISTRATION_LINK", "").strip()
INITIAL_ADMINS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "8717265614,8350956429").split(",") if x.strip()}
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "4"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("team-hacker-bot")

# Initialize the two owner admins on every boot; added admins persist in SQLite.
for admin_id in INITIAL_ADMINS:
    DB.add_admin(admin_id)

def admin(uid: int) -> bool:
    return uid in INITIAL_ADMINS or DB.is_admin(uid)

def main_menu(uid):
    rows = [
        [InlineKeyboardButton("📩 Contact Admin", callback_data="contact"),
         InlineKeyboardButton("📡 Live Signal", callback_data="live")],
    ]
    if admin(uid):
        rows.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin")])
    return InlineKeyboardMarkup(rows)

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Signal Format", callback_data="edit_signal"),
         InlineKeyboardButton("✏️ Result Format", callback_data="edit_result")],
        [InlineKeyboardButton("😀 Emoji / Text Style", callback_data="edit_emoji"),
         InlineKeyboardButton("🖼️ Upload Images", callback_data="images")],
        [InlineKeyboardButton("📣 Botcast", callback_data="broadcast"),
         InlineKeyboardButton("📊 Statistics", callback_data="stats")],
        [InlineKeyboardButton("🚫 Ban / Unban", callback_data="ban"),
         InlineKeyboardButton("➕ Add Admin", callback_data="addadmin")],
        [InlineKeyboardButton("🔗 Channel Settings", callback_data="channel"),
         InlineKeyboardButton("🔙 Main Menu", callback_data="home")],
    ])

async def check_channel(bot, uid):
    channel_id = DB.get_setting("channel_id", CHANNEL_ID)
    if not channel_id:
        return True
    try:
        member = await bot.get_chat_member(channel_id, uid)
        return member.status in ("member", "administrator", "creator")
    except Exception as exc:
        log.warning("Channel verification failed for %s: %s", uid, exc)
        return False

async def show_verification(update, context):
    buttons = []
    url = DB.get_setting("channel_url", CHANNEL_URL)
    if url:
        buttons.append([InlineKeyboardButton("📢 Join Channel", url=url)])
    buttons.append([InlineKeyboardButton("✅ I Joined — Verify", callback_data="verify")])
    await update.effective_message.reply_text(
        "বট ব্যবহার করতে আগে আমাদের Telegram Channel-এ Join করুন, তারপর Verify চাপুন।",
        reply_markup=InlineKeyboardMarkup(buttons))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    DB.add_user(uid)
    if DB.is_banned(uid):
        await update.effective_message.reply_text("আপনার অ্যাকাউন্টটি নিষিদ্ধ করা হয়েছে।")
        return
    if not await check_channel(context.bot, uid):
        await show_verification(update, context)
        return
    await update.effective_message.reply_text(
        "স্বাগতম! নিচের মেনু থেকে নির্বাচন করুন।",
        reply_markup=main_menu(uid))

async def send_photo_or_text(bot, chat_id, setting_key, text, fallback_text=True):
    photo_id = DB.get_setting(setting_key, "")
    if photo_id:
        try:
            await bot.send_photo(chat_id, photo_id, caption=text)
            return
        except Exception as exc:
            log.warning("Could not send image %s: %s", setting_key, exc)
    if fallback_text:
        await bot.send_message(chat_id, text)

def render(template, values):
    # Safe named placeholders only. Unknown placeholders remain visible for easy correction.
    class Safe(dict):
        def __missing__(self, key): return "{" + key + "}"
    return template.format_map(Safe(values))

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if DB.is_banned(uid):
        await q.edit_message_text("আপনার অ্যাকাউন্টটি নিষিদ্ধ করা হয়েছে।")
        return
    data = q.data
    if data == "verify":
        if await check_channel(context.bot, uid):
            await q.edit_message_text("✅ Channel Verification সফল।", reply_markup=main_menu(uid))
        else:
            await q.answer("আগে চ্যানেলে Join করুন।", show_alert=True)
    elif data == "home":
        await q.edit_message_text("Main Menu", reply_markup=main_menu(uid))
    elif data == "contact":
        contact = DB.get_setting("contact_text", "অ্যাডমিনের সঙ্গে যোগাযোগ করতে Admin-এর নির্ধারিত Telegram link ব্যবহার করুন।")
        await q.edit_message_text(contact, reply_markup=main_menu(uid))
    elif data == "live":
        if not await check_channel(context.bot, uid):
            await q.edit_message_text("Channel verification প্রয়োজন। /start দিন।")
            return
        if DB.is_live(uid):
            await q.answer("আপনার Live Signal ইতোমধ্যে চালু আছে।", show_alert=True)
            return
        allowed, wait = DB.can_start(uid)
        if not allowed:
            await q.answer(f"আবার চালু করতে {wait} মিনিট অপেক্ষা করুন।", show_alert=True)
            return
        DB.start_session(uid)
        await q.edit_message_text(
            "📡 Live Signal চালু হয়েছে। নতুন Period এলে API যাচাই করে সিগন্যাল পাঠানো হবে।\n"
            "মনে রাখবেন: Prediction সম্ভাব্য অনুমান, নিশ্চিত ফল নয়।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop Signal", callback_data="stop")]]))
        context.application.create_task(signal_worker(context.application, uid))
    elif data == "stop":
        DB.stop_live(uid, cooldown=False)
        await q.edit_message_text("আপনার Live Signal বন্ধ হয়েছে।", reply_markup=main_menu(uid))
    elif data == "admin":
        if not admin(uid):
            await q.answer("Admin permission নেই।", show_alert=True); return
        await q.edit_message_text("⚙️ ADMIN PANEL\nপরিবর্তনগুলো সংরক্ষণের সঙ্গে সঙ্গে পরবর্তী মেসেজে কার্যকর হবে।", reply_markup=admin_menu())
    elif data in ("edit_signal", "edit_result", "edit_emoji", "broadcast", "ban", "addadmin", "channel"):
        if not admin(uid): return
        context.user_data["action"] = data
        prompts = {
            "edit_signal": ("Signal template পাঠান। Placeholder: {brand}, {market}, {period}, {entry}, {level}, {registration_link}", "signal_template"),
            "edit_result": ("Result template পাঠান। Placeholder: {brand}, {market}, {period}, {entry}, {result}, {status}, {level}", "result_template"),
            "edit_emoji": ("Emoji/style prefix পাঠান। এটি {brand} হিসেবে Signal ও Result template-এ ব্যবহার হবে।", "brand"),
            "broadcast": ("যে কোনো text/photo/video/document পাঠান; সেটি সব bot users-কে পাঠানো হবে।", None),
            "ban": ("User ID এবং action পাঠান এভাবে: 123456789 ban  অথবা  123456789 unban", None),
            "addadmin": ("নতুন Admin-এর numeric Telegram User ID পাঠান।", None),
            "channel": ("Channel ID/username এবং join URL এইভাবে পাঠান:\n@channelusername | https://t.me/channelusername", None),
        }
        await q.edit_message_text(prompts[data][0], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Admin Panel", callback_data="admin")]]))
    elif data == "images":
        if not admin(uid): return
        context.user_data["action"] = "images"
        await q.edit_message_text(
            "একটি ছবি পাঠান এবং caption-এ নিচের একটি key লিখুন:\n"
            "next = Next Prediction image\nwin = WIN image\nloss = LOSS image\njackpot = Number Jackpot image\n"
            "ছবি আপলোড করলে সেটি সঙ্গে সঙ্গে পরবর্তী সংশ্লিষ্ট মেসেজে ব্যবহার হবে।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Admin Panel", callback_data="admin")]]))
    elif data == "stats":
        if not admin(uid): return
        s = DB.stats()
        await q.edit_message_text(
            f"👥 Users: {s['users']}\n📨 Signals: {s['signals']}\n✅ WIN: {s['wins']}\n❌ LOSS: {s['losses']}\n💎 Jackpot: {s['jackpots']}\n"
            f"📡 Live users: {s['live']}",
            reply_markup=admin_menu())

async def admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    action = context.user_data.get("action")
    if not action or not admin(uid):
        return False
    msg = update.effective_message
    if action == "images":
        if not msg.photo:
            await msg.reply_text("ছবি হিসেবে পাঠান এবং caption-এ next / win / loss / jackpot লিখুন।")
            return True
        key = (msg.caption or "").strip().lower()
        if key not in ("next", "win", "loss", "jackpot"):
            await msg.reply_text("Caption-এ next, win, loss অথবা jackpot লিখুন।")
            return True
        DB.set_setting("image_" + key, msg.photo[-1].file_id)
        await msg.reply_text(f"✅ {key} image saved. এখন থেকেই কার্যকর।")
        context.user_data.pop("action", None)
        return True
    if not msg.text:
        await msg.reply_text("এই সেটিংয়ের জন্য text পাঠান।")
        return True
    text = msg.text.strip()
    if action in ("edit_signal", "edit_result"):
        DB.set_setting("signal_template" if action == "edit_signal" else "result_template", text)
        await msg.reply_text("✅ Template সংরক্ষিত। পরবর্তী Signal/Result থেকেই কার্যকর হবে।")
    elif action == "edit_emoji":
        DB.set_setting("brand", text)
        await msg.reply_text("✅ Brand/emoji style সংরক্ষিত।")
    elif action == "addadmin":
        try:
            new_id = int(text)
            DB.add_admin(new_id)
            await msg.reply_text(f"✅ {new_id} Admin হিসেবে যুক্ত হয়েছে।")
        except ValueError:
            await msg.reply_text("শুধু numeric Telegram User ID দিন।")
            return True
    elif action == "ban":
        try:
            parts = text.split()
            target, verb = int(parts[0]), parts[1].lower()
            if verb not in ("ban", "unban"): raise ValueError()
            DB.set_banned(target, verb == "ban")
            await msg.reply_text(f"✅ User {target}: {verb}")
        except Exception:
            await msg.reply_text("Format: 123456789 ban অথবা 123456789 unban")
            return True
    elif action == "channel":
        try:
            channel_id, channel_url = [x.strip() for x in text.split("|", 1)]
            DB.set_setting("channel_id", channel_id)
            DB.set_setting("channel_url", channel_url)
            await msg.reply_text("✅ Channel settings saved. Bot restart ছাড়াই নতুন setting ব্যবহার হবে।")
        except Exception:
            await msg.reply_text("Format: @channelusername | https://t.me/channelusername")
            return True
    elif action == "broadcast":
        sent, failed = 0, 0
        for target in DB.users():
            try:
                await context.bot.copy_message(target, msg.chat_id, msg.message_id)
                sent += 1
            except Exception:
                failed += 1
        await msg.reply_text(f"📣 Botcast সম্পন্ন। Sent: {sent}, Failed: {failed}")
    context.user_data.pop("action", None)
    return True

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await admin_input(update, context): return
    await update.effective_message.reply_text("মেনু দেখতে /start দিন।")

async def signal_worker(app, uid):
    log.info("Signal worker started for user %s", uid)
    while DB.is_live(uid):
        try:
            history = await fetch_history()
            if len(history) < 50:
                await asyncio.sleep(POLL_SECONDS); continue
            current_issue = str(history[0]["issueNumber"])
            pending = DB.pending_signal(uid)
            if pending:
                target = pending["target_period"]
                result_row = next((r for r in history if str(r["issueNumber"]) == target), None)
                if result_row:
                    result_num = int(result_row["number"])
                    result_side = classify_number(result_num)
                    status = DB.resolve_signal(uid, result_num, result_side)
                    values = DB.signal_values(uid, result_row, status)
                    template = DB.get_setting("result_template", DEFAULT_RESULT_TEMPLATE)
                    result_text = render(template, values)
                    image_key = {"WIN":"win", "LOSS":"loss", "JACKPOT":"jackpot"}[status]
                    await send_photo_or_text(app.bot, uid, "image_" + image_key, result_text)
                    if status in ("WIN", "JACKPOT"):
                        wins = DB.session_wins(uid)
                        if wins % 5 == 0:
                            await app.bot.send_message(uid, DB.make_report(uid))
                        if wins >= 20:
                            DB.stop_live(uid, cooldown=True)
                            await app.bot.send_message(uid, "🏁 ২০টি WIN পূর্ণ হয়েছে। Live Signal ১ ঘণ্টার জন্য বন্ধ। এরপর আবার Live Signal চালু করতে পারবেন।")
                            return
                    if DB.entry_level(uid) > 6:
                        DB.stop_live(uid, cooldown=True)
                        await app.bot.send_message(uid, "৬টি Entry Level শেষ হয়েছে। পরবর্তী সেশন ১ ঘণ্টা পরে চালু করতে পারবেন।")
                        return
            else:
                last_sent = DB.last_signal_source(uid)
                if last_sent != current_issue:
                    prediction = make_prediction(history)
                    target_period = str(int(current_issue) + 1)
                    level = DB.entry_level(uid)
                    values = {
                        "brand": DB.get_setting("brand", "𝐓𝐄𝐀𝐌 𝐇𝐀𝐂𝐊𝐄𝐑 𝐁𝐃 𝐀𝐈 𝐒𝐈𝐆𝐍𝐀𝐋🤩"),
                        "market": "⏰𝐖𝐈𝐍 𝐆𝐨 𝟏 𝐌𝐢𝐧⏰",
                        "period": target_period,
                        "entry": f"{prediction['side']} {prediction['numbers'][0]}•{prediction['numbers'][1]}",
                        "level": level,
                        "registration_link": REGISTRATION_LINK,
                    }
                    template = DB.get_setting("signal_template", DEFAULT_SIGNAL_TEMPLATE)
                    text = render(template, values)
                    photo_id = DB.get_setting("image_next", "")
                    if photo_id:
                        try: await app.bot.send_photo(uid, photo_id, caption=text)
                        except Exception: await app.bot.send_message(uid, text)
                    else:
                        await app.bot.send_message(uid, text)
                    DB.create_signal(uid, current_issue, target_period, prediction["side"], prediction["numbers"], level)
            await asyncio.sleep(POLL_SECONDS)
        except Exception as exc:
            log.exception("Signal worker error for %s: %s", uid, exc)
            await asyncio.sleep(10)
    log.info("Signal worker stopped for user %s", uid)

DEFAULT_SIGNAL_TEMPLATE = """{brand}
𝐌𝐚𝐫𝐤𝐞𝐭 ➡️ {market}
𝐏𝐞𝐫𝐢𝐨𝐝 𝐍𝐮𝐦𝐛𝐞𝐫 ▶️ {period}
𝐄𝐧𝐭𝐫𝐲 📊 {entry}
📎 REGISTRATION LINK 📱
{registration_link}
🔔 𝐀𝐥𝐥 𝐓𝐢𝐦𝐞 𝐅𝐥𝐨𝐰 𝟔 𝐒𝐭𝐞𝐩
𝐄𝐧𝐭𝐫𝐲 𝐋𝐞𝐯𝐞𝐥 ➖ {level}"""

DEFAULT_RESULT_TEMPLATE = """{brand}
𝐌𝐚𝐫𝐤𝐞𝐭 ➡️ {market}
𝐏𝐞𝐫𝐢𝐨𝐝 𝐍𝐮𝐦𝐛𝐞𝐫 ▶️ {period}
𝐄𝐧𝐭𝐫𝐲 📊 {entry}
⌛𝐑𝐞𝐬𝐮𝐥𝐭 : {result}
𝐒𝐭𝐚𝐭𝐞𝐬 : {status}"""

async def post_init(app):
    # Resume live sessions after a process restart.
    for uid in DB.live_users():
        app.create_task(signal_worker(app, uid))

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN নেই। .env.example কপি করে .env বানিয়ে BotFather token দিন।")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, text_handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
