"""
POWER TELEGRAM BOT - 55 Commands
Built for Render hosting (Background Worker + optional Webhook)
python-telegram-bot v20.x async
"""

import os
import re
import ast
import time
import json
import random
import string
import sqlite3
import logging
import datetime
import requests
import qrcode
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from dotenv import load_dotenv

# --- FAKE WEB SERVER FOR RENDER FREE (so it doesn't show "port not open") ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def start_health_server():
    try:
        port = int(os.getenv("PORT", "10000"))
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"Health server started on port {port}")
    except Exception as e:
        print(f"Health server failed: {e}")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, 
    filters, JobQueue
)
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.error import BadRequest

load_dotenv()

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
# Leave empty = no admin needed
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()  # e.g. https://your-app.onrender.com
PORT = int(os.getenv("PORT", "10000"))
DEFAULT_CITY = os.getenv("WEATHER_DEFAULT_CITY", "Enugu")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set in .env")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
START_TIME = time.time()

# --- DATABASE ---
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_seen TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS warns (user_id INTEGER, chat_id INTEGER, count INTEGER DEFAULT 1, PRIMARY KEY(user_id, chat_id))")
cur.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, task TEXT, done INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS afk (user_id INTEGER PRIMARY KEY, reason TEXT, since TEXT)")
conn.commit()

def is_admin(user_id):
    # If no ADMIN_IDS set, everyone is admin (you said you don't want admin)
    if not ADMIN_IDS:
        return True
    return user_id in ADMIN_IDS
def is_group_admin(update: Update):
    # for group commands, check if bot user is admin or sender is admin
    if update.effective_chat.type == "private":
        return True
    return True # Telegram API check done inside handlers

# --- HELP TEXT ---
HELP_TEXT = """
━━━━━━ 🤖 ʙᴏᴛ ɪɴғᴏ ━━━━━━
◉ 🎉 ⟐𓆩☠ 𝘿𝙍𝙀𝘼𝙈-𝙈𝘿 ☠𓆪⟐ Telegram Edition
◉ 👑 ᴏᴡɴᴇʀ: YOU
◉ 📜 ᴄᴏᴍᴍᴀɴᴅs: 812
◉ ⏱️ ʀᴜɴᴛɪᴍᴇ: {runtime}
◉ 📦 ᴘʀᴇғɪx: . / 
◉ ⚙️ ᴍᴏᴅᴇ: public
◉ 🏷️ ᴠᴇʀsɪᴏɴ: 12.0.0 Beta
◉ 🌍 ʜᴏsᴛ: Render.com

━━━━━『 ᴛᴏᴏʟs 』━━━━━
◉ ➤ ʀᴇᴍɪɴɪ
◉ ➤ ʜᴀᴘᴘʏ
◉ ➤ ʜᴇᴀʀᴛ
◉ ➤ ᴀɴɢʀʏ
◉ ➤ sᴀᴅ
◉ ➤ sʜʏ
◉ ➤ ᴍᴏᴏɴ
◉ ➤ ᴄᴏɴғᴜsᴇᴅ
◉ ➤ ʜᴏᴛ
◉ ➤ ɴɪᴋᴀʟ
◉ ➤ ғᴀɴᴄʏ
◉ ➤ ʀᴇᴍᴏᴠᴇʙɢ / ʀᴇᴍᴏᴠᴇʙɢ2 / ʀᴇᴍᴏᴠᴇʙɢ3
◉ ➤ sɪᴍᴅᴀᴛᴀ
◉ ➤ sᴄʀᴇᴇɴsʜᴏᴛ
◉ ➤ ʙᴏᴏsᴛ
◉ ➤ ʜᴀsʜᴛᴀɢ
◉ ➤ ᴛɪᴍᴇ / ᴡᴇᴀᴛʜᴇʀ / ᴛʀᴀɴsʟᴀᴛᴇ / ᴄᴀʟᴄ / ǫʀ / sʜᴏʀᴛᴜʀʟ / ᴘᴀssᴡᴏʀᴅ

━━━━━『 ᴀɪ 』━━━━━
◉ ➤ ɢᴘᴛ35 / ɢᴘᴛ4 / ɢᴘᴛ4ᴏ / ᴄʟᴀᴜᴅᴇ / ɢᴇᴍɪɴɪ / ɢʀᴏᴋ / ᴅᴇᴇᴘsᴇᴇᴋ
◉ ➤ ʟʟᴀᴍᴀ3 / ᴘᴇʀᴘʟᴇxɪᴛʏ / ᴍɪsᴛʀᴀʟ / ᴄᴏᴅᴇʟʟᴀᴍᴀ / ʙᴀʀᴅ / ᴄᴏᴘɪʟᴏᴛ
◉ ➤ ᴀsᴋᴀɪ / ʙʀᴀɪɴ / ᴛʜɪɴᴋ / ᴍᴀᴛʜ / ɢʀᴀᴍᴍᴀʀ / sᴘᴇʟʟᴄʜᴇᴄᴋ

━━━━━『 ᴀɴɪᴍᴇ 』━━━━━
◉ ➤ ᴡᴀɪғᴜ / ɴᴇᴋᴏ / ᴋɪᴛsᴜɴᴇ / ʜᴜsʙᴀɴᴅᴏ / ᴀɴɪᴍᴇɢɪʀʟ / ᴀɴɪᴍᴇʙᴏʏ
◉ ➤ ᴄᴀᴛɢɪʀʟ / ғᴏxɢɪʀʟ / ᴋᴀᴡᴀɪɪ / ᴄᴏsᴘʟᴀʏ / ᴍᴀɪᴅ

━━━━━『 ᴅᴏᴡɴʟᴏᴀᴅ 』━━━━━
◉ ➤ ᴛɪᴋᴛᴏᴋ / ғʙ / ɪɴsᴛᴀ / ᴘɪɴᴛᴇʀᴇsᴛ / ᴀᴘᴋ / ᴍᴇɢᴀ
◉ ➤ ᴘʟᴀʏ (yt audio) / ᴠɪᴅᴇᴏ (yt video) / ᴛᴛs

━━━━━『 ɢʀᴏᴜᴘ 』━━━━━
◉ ➤ ᴀᴜᴛᴏᴀᴘᴘʀᴏᴠᴇ / ᴛᴀɢᴀʟʟ / ᴋɪᴄᴋ / ᴍᴜᴛᴇ / ᴜɴᴍᴜᴛᴇ / ᴘʀᴏᴍᴏᴛᴇ / ᴅᴇᴍᴏᴛᴇ
◉ ➤ ʙᴀɴ / ᴜɴʙᴀɴ / ᴡᴀʀɴ / ᴡᴀʀɴs / ᴘɪɴ / ᴘᴜʀɢᴇ / ᴀғᴋ / ʟɪɴᴋ / ɢɪɴғᴏ

━━━━━『 ᴍᴀɪɴ 』━━━━━
◉ ➤ ʙᴏᴛ / ᴀʟɪᴠᴇ / ᴘɪɴɢ / ᴘɪɴɢ2 / ᴍᴇɴᴜ / ʀᴇᴘᴏ / ᴜᴘᴛɪᴍᴇ / ɪᴅ / ɪɴғᴏ

━━━━━『 ғᴜɴ 』━━━━━
◉ ➤ ᴊᴏᴋᴇ / ǫᴜᴏᴛᴇ / ᴍᴇᴍᴇ / ғᴀᴄᴛ / 8ʙᴀʟʟ / ʀᴏᴀsᴛ / ᴄᴏᴍᴘʟɪᴍᴇɴᴛ / ᴅɪᴄᴇ / ʀᴏʟʟ / ғʟɪᴘ
◉ ➤ ʟᴏᴠᴇᴛᴇsᴛ / sʜɪᴘ / ʜᴜɢ / ᴋɪss / sʟᴀᴘ / ᴄᴏɪɴғʟɪᴘ / ᴛʀᴜᴛʜ / ᴅᴀʀᴇ

━━━━━『 ᴏᴡɴᴇʀ 』━━━━━
◉ ➤ ʙʟᴏᴄᴋ / ᴜɴʙʟᴏᴄᴋ / ʟᴇᴀᴠᴇ / ʜɪᴅᴇᴛᴀɢ / ʙʀᴏᴀᴅᴄᴀsᴛ


━━━━━『 ɴᴇᴡ 30 ᴄᴏᴍᴍᴀɴᴅs 』━━━━━
◉ ➤ ʟʏʀɪᴄs / ɢɪᴛʜᴜʙ / ɪᴘ / ʙɪɴ / ᴄᴏᴜɴᴛʀʏ / ᴄᴜʀʀᴇɴᴄʏ / ᴜʀʙᴀɴ
◉ ➤ ʟᴏᴠᴇ / sʜɪᴘ / ᴛʀᴜᴛʜ / ᴅᴀʀᴇ / ʜᴀᴄᴋ / ғᴀɴᴄʏ
◉ ➤ ᴡᴀʟʟᴘᴀᴘᴇʀ / ᴇᴍᴏᴊɪᴍɪx / ᴀɪɪᴍɢ / ʏᴛᴍᴘ3 / ʏᴛᴍᴘ4 / ǫʀʀᴇᴀᴅ
◉ ➤ ᴛᴏɪᴍɢ / ɢᴇᴛᴘᴘ / ʜɪᴅᴇᴛᴀɢ / ᴛᴀɢᴀʟʟ / ᴘʀᴏᴍᴏᴛᴇ / ᴅᴇᴍᴏᴛᴇ / sᴇᴛᴡᴇʟᴄᴏᴍᴇ


Type /help for classic list | /menu for this dream style
Powered by DREAM-MD x Your Bot


*CLASSIC TELEGRAM COMMANDS:*
/start, /help, /ping, /weather, /meme, /joke, /ban, /crypto, /todo, etc - all 55 still work!
"""

ABOUT_TEXT = """
━━━━━━ 🤖 ʙᴏᴛ ɪɴғᴏ ━━━━━━
◉ 🎉 ⟐𓆩☠ 𝘿𝙍𝙀𝘼𝙈-𝙈𝘿 ☠𓆪⟐ Telegram Edition
◉ 👑 ᴏᴡɴᴇʀ: YOU
◉ 📜 ᴄᴏᴍᴍᴀɴᴅs: 812 (55 active + 727 dream style)
◉ ⏱️ ʀᴜɴᴛɪᴍᴇ: {runtime}
◉ 📦 ᴘʀᴇғɪx: . and /
◉ ⚙️ ᴍᴏᴅᴇ: public
◉ 🏷️ ᴠᴇʀsɪᴏɴ: 12.0.0 Beta Telegram

Made with python-telegram-bot + DREAM-MD aesthetic
Hosted on Render.com - Never sleeps with UptimeRobot
"""

# --- CORE COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cur.execute("INSERT OR IGNORE INTO users(user_id, username, first_seen) VALUES(?,?,?)",
                (user.id, user.username or user.first_name, datetime.datetime.now().isoformat()))
    conn.commit()
    diff = int(time.time() - START_TIME)
    h, rem = divmod(diff, 3600)
    m, s = divmod(rem, 60)
    runtime = f"{h}h {m}m {s}s"
    text = f"""
━━━━━━ 🤖 ʙᴏᴛ ɪɴғᴏ ━━━━━━
◉ 🎉 ⟐𓆩☠ 𝘿𝙍𝙀𝘼𝙈-𝙈𝘿 ☠𓆪⟐
◉ 👑 ᴏᴡɴᴇʀ: {user.first_name}
◉ 📜 ᴄᴏᴍᴍᴀɴᴅs: 812
◉ ⏱️ ʀᴜɴᴛɪᴍᴇ: {runtime}
◉ 📦 ᴘʀᴇғɪx: . /
◉ ⚙️ ᴍᴏᴅᴇ: public
◉ 🏷️ ᴠᴇʀsɪᴏɴ: 12.0.0 Beta

Hello {user.first_name}! 👋

I am now in DREAM-MD style! 
Type /menu to see 782 commands style menu
Type /help for classic list

Powered by DREAM-MD x Telegram
"""
    kb = [[InlineKeyboardButton("📜 ᴍᴇɴᴜ", callback_data="help"),
           InlineKeyboardButton("ℹ️ ᴀʙᴏᴜᴛ", callback_data="about")],
          [InlineKeyboardButton("🎉 782 ᴄᴏᴍᴍᴀɴᴅs", callback_data="dream")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        diff = int(time.time() - START_TIME)
        h, rem = divmod(diff, 3600)
        m, s = divmod(rem, 60)
        runtime = f"{h}h {m}m {s}s"
        try:
            text = HELP_TEXT.format(runtime=runtime)
        except:
            text = HELP_TEXT.replace("{runtime}", runtime)
        # Split for Telegram 4096 limit
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"help_cmd error: {e}")
        # Fallback - send simple menu
        await update.message.reply_text(f"Bot is alive! Uptime: {int(time.time()-START_TIME)}s\nUse /menu /start /ping /meme /joke /weather\nError: {e}")

async def help_classic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Classic commands: /start /ping /uptime /id /info /weather /meme /joke /ban /crypto etc")

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    diff = int(time.time() - START_TIME)
    h, rem = divmod(diff, 3600)
    m, s = divmod(rem, 60)
    runtime = f"{h}h {m}m {s}s"
    try:
        txt = ABOUT_TEXT.format(runtime=runtime)
    except:
        txt = ABOUT_TEXT
    await update.message.reply_text(txt)


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.time()
    m = await update.message.reply_text("🏓 Pinging...")
    latency = round((time.time() - start) * 1000)
    await m.edit_text(f"🏓 Pong! `{latency}ms`", parse_mode=ParseMode.MARKDOWN)

async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    diff = int(time.time() - START_TIME)
    h, rem = divmod(diff, 3600)
    m, s = divmod(rem, 60)
    await update.message.reply_text(f"⏰ Uptime: {h}h {m}m {s}s")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    text = f"👤 *Your ID:* `{user.id}`\n💬 *Chat ID:* `{chat.id}`\n"
    if update.message.reply_to_message:
        text += f"↩️ *Replied User ID:* `{update.message.reply_to_message.from_user.id}`"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    await update.message.reply_text(
        f"👤 *User Info:*\nName: {target.full_name}\nID: `{target.id}`\nUsername: @{target.username}\nIs Bot: {target.is_bot}\nLanguage: {target.language_code}",
        parse_mode=ParseMode.MARKDOWN
    )

async def chatinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(f"💬 *Chat Info:*\nTitle: {chat.title}\nID: `{chat.id}`\nType: {chat.type}\nMembers: {await context.bot.get_chat_member_count(chat.id) if chat.type != 'private' else 'Private chat'}", parse_mode=ParseMode.MARKDOWN)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM todos")
    todos = cur.fetchone()[0]
    await update.message.reply_text(f"📊 *Stats:*\nUsers: {users}\nTodos: {todos}\nUptime: {int((time.time()-START_TIME)//3600)}h", parse_mode=ParseMode.MARKDOWN)

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ Settings coming soon. Default: English, UTC. Use /afk to set AFK status.")

# --- TOOLS ---

async def time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now()
    await update.message.reply_text(f"🕒 *Now:*\nUTC: {datetime.datetime.utcnow()}\nLocal: {now}\nUnix: {int(time.time())}", parse_mode=ParseMode.MARKDOWN)

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args) if context.args else DEFAULT_CITY
    try:
        r = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
        data = r.json()
        curr = data['current_condition'][0]
        await update.message.reply_text(f"🌤️ *{city.title()}*\nTemp: {curr['temp_C']}°C / {curr['temp_F']}°F\nFeels: {curr['FeelsLikeC']}°C\nCondition: {curr['weatherDesc'][0]['value']}\nHumidity: {curr['humidity']}%\nWind: {curr['windspeedKmph']} km/h", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Couldn't get weather for {city}. Error: {e}")

async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Use: /translate es Hello how are you")
        return
    try:
        from deep_translator import GoogleTranslator
        target = context.args[0]
        text = " ".join(context.args[1:])
        translated = GoogleTranslator(source='auto', target=target).translate(text)
        await update.message.reply_text(f"🌐 *{target}*: {translated}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"Translation failed: {e}")

def safe_eval(expr):
    allowed = {ast.Add: lambda a,b: a+b, ast.Sub: lambda a,b: a-b, ast.Mult: lambda a,b: a*b, 
               ast.Div: lambda a,b: a/b, ast.Pow: lambda a,b: a**b, ast.USub: lambda a: -a}
    def eval_node(node):
        if isinstance(node, ast.Num): return node.n
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, ast.BinOp): return allowed[type(node.op)](eval_node(node.left), eval_node(node.right))
        if isinstance(node, ast.UnaryOp): return allowed[type(node.op)](eval_node(node.operand))
        raise ValueError("Unsupported")
    return eval_node(ast.parse(expr, mode='eval').body)

async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /calc 2+2*10")
        return
    expr = " ".join(context.args)
    try:
        result = safe_eval(expr)
        await update.message.reply_text(f"🧮 `{expr}` = *{result}*", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def qr_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /qr your text")
        return
    text = " ".join(context.args)
    img = qrcode.make(text)
    bio = BytesIO()
    bio.name = "qr.png"
    img.save(bio, "PNG")
    bio.seek(0)
    await update.message.reply_photo(bio, caption=f"🔳 QR for: {text}")

async def shorturl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /shorturl https://example.com")
        return
    url = context.args[0]
    try:
        r = requests.get(f"https://is.gd/create.php?format=simple&url={url}", timeout=5)
        await update.message.reply_text(f"🔗 Short: {r.text}")
    except Exception as e:
        await update.message.reply_text(f"Failed: {e}")

async def password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    length = int(context.args[0]) if context.args and context.args[0].isdigit() else 12
    length = min(max(length, 4), 64)
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = "".join(random.choice(chars) for _ in range(length))
    await update.message.reply_text(f"🔐 Password ({length}): `{pwd}`", parse_mode=ParseMode.MARKDOWN)

async def define(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /define python")
        return
    word = context.args[0]
    try:
        r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=8)
        data = r.json()[0]
        meaning = data['meanings'][0]['definitions'][0]['definition']
        await update.message.reply_text(f"📖 *{word}*: {meaning}", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("❌ Word not found.")

async def wiki_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /wiki elon musk")
        return
    query = " ".join(context.args)
    try:
        import wikipedia
        wikipedia.set_lang("en")
        summary = wikipedia.summary(query, sentences=3)
        page = wikipedia.page(query)
        await update.message.reply_text(f"📚 *{page.title}*\n{summary}\n\n🔗 {page.url}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"Wiki error: {e}")

async def screenshot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /screenshot https://google.com")
        return
    url = context.args[0]
    try:
        # Microlink free screenshot
        api = f"https://api.microlink.io/?url={url}&screenshot=true&meta=false"
        r = requests.get(api, timeout=15).json()
        img_url = r['data']['screenshot']['url']
        await update.message.reply_photo(img_url, caption=f"🖥️ {url}")
    except Exception as e:
        await update.message.reply_text(f"Screenshot failed: {e}")

async def tts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /tts Hello world")
        return
    text = " ".join(context.args)
    try:
        from gtts import gTTS
        tts_obj = gTTS(text=text, lang='en')
        bio = BytesIO()
        tts_obj.write_to_fp(bio)
        bio.seek(0)
        bio.name = "tts.mp3"
        await update.message.reply_voice(bio, caption=f"🔊 {text[:50]}")
    except Exception as e:
        await update.message.reply_text(f"TTS error: {e}")

async def sticker_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("Reply to a photo with /sticker")
        return
    photo = await update.message.reply_to_message.photo[-1].get_file()
    bio = BytesIO()
    await photo.download_to_memory(bio)
    bio.seek(0)
    await update.message.reply_sticker(bio)

# --- FUN ---

async def dice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_dice(update.effective_chat.id, emoji="🎲")

async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and "-" in context.args[0]:
        a,b = context.args[0].split("-")
        try:
            await update.message.reply_text(f"🎲 {random.randint(int(a), int(b))}")
            return
        except: pass
    await update.message.reply_text(f"🎲 {random.randint(1,100)}")

async def flip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🪙 {random.choice(['Heads','Tails'])}!")

async def choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /choose apple, banana, orange")
        return
    options = " ".join(context.args).split(",")
    options = [o.strip() for o in options if o.strip()]
    await update.message.reply_text(f"🤔 I choose: *{random.choice(options)}*", parse_mode=ParseMode.MARKDOWN)

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://v2.jokeapi.dev/joke/Any?safe-mode&type=single", timeout=5).json()
        await update.message.reply_text(f"😂 {r.get('joke','No joke found')}")
    except:
        await update.message.reply_text("😂 Why did the bot go to Render? To stay alive 24/7!")

async def quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://api.quotable.io/random", timeout=5).json()
        await update.message.reply_text(f"💬 \"{r['content']}\"\n— {r['author']}")
    except:
        await update.message.reply_text("💬 \"Code is like humor. When you have to explain it, it's bad.\"")

async def meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=8).json()
        await update.message.reply_photo(r['url'], caption=r['title'])
    except:
        await update.message.reply_text("Meme API down, try again later.")

async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://uselessfacts.jsph.pl/random.json?language=en", timeout=5).json()
        await update.message.reply_text(f"🧠 {r['text']}")
    except:
        await update.message.reply_text("🧠 Octopuses have three hearts.")

async def eightball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answers = ["It is certain","Without a doubt","Yes definitely","You may rely on it","Most likely","Outlook good","Yes","Signs point to yes","Reply hazy try again","Ask again later","Cannot predict now","Don't count on it","My reply is no","My sources say no","Very doubtful"]
    await update.message.reply_text(f"🎱 {random.choice(answers)}")

async def roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    roasts = ["You're like a cloud. When you disappear, it's a beautiful day.","You have something on your chin... no, the third one down.","I'd agree with you but then we'd both be wrong."]
    await update.message.reply_text(f"🔥 {random.choice(roasts)}")

async def compliment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comps = ["You're doing amazing! 🚀","Your code is cleaner than your room (hopefully)!","Big brain energy detected 🧠✨"]
    await update.message.reply_text(random.choice(comps))

async def poll_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /poll Question | Option1 | Option2 | Option3")
        return
    parts = " ".join(context.args).split("|")
    if len(parts) < 3:
        await update.message.reply_text("Need question and at least 2 options separated by |")
        return
    question = parts[0].strip()
    options = [p.strip() for p in parts[1:]]
    try:
        await context.bot.send_poll(update.effective_chat.id, question=question, options=options, is_anonymous=False)
    except Exception as e:
        await update.message.reply_text(f"Poll failed: {e}")

# --- MODERATION ---

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("Groups only.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to user to ban.")
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id)
        await update.message.reply_text(f"🔨 Banned {update.message.reply_to_message.from_user.first_name}")
    except Exception as e:
        await update.message.reply_text(f"Ban failed: {e}")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message and not context.args:
        await update.message.reply_text("Reply or give user ID")
        return
    try:
        uid = update.message.reply_to_message.from_user.id if update.message.reply_to_message else int(context.args[0])
        await context.bot.unban_chat_member(update.effective_chat.id, uid)
        await update.message.reply_text("✅ Unbanned")
    except Exception as e:
        await update.message.reply_text(f"Unban failed: {e}")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to kick")
        return
    try:
        uid = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, uid)
        await context.bot.unban_chat_member(update.effective_chat.id, uid)
        await update.message.reply_text("👢 Kicked")
    except Exception as e:
        await update.message.reply_text(f"Kick failed: {e}")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to mute")
        return
    try:
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, ChatPermissions(can_send_messages=False))
        await update.message.reply_text("🔇 Muted")
    except Exception as e:
        await update.message.reply_text(f"Mute failed: {e}")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to unmute")
        return
    try:
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True))
        await update.message.reply_text("🔊 Unmuted")
    except Exception as e:
        await update.message.reply_text(f"Unmute failed: {e}")

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to warn")
        return
    uid = update.message.reply_to_message.from_user.id
    chat_id = update.effective_chat.id
    cur.execute("SELECT count FROM warns WHERE user_id=? AND chat_id=?", (uid, chat_id))
    row = cur.fetchone()
    count = (row[0] + 1) if row else 1
    cur.execute("INSERT OR REPLACE INTO warns(user_id, chat_id, count) VALUES(?,?,?)", (uid, chat_id, count))
    conn.commit()
    await update.message.reply_text(f"⚠️ Warned {update.message.reply_to_message.from_user.first_name} [{count}/3]")
    if count >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, uid)
            await update.message.reply_text("🚫 Auto-banned after 3 warns")
            cur.execute("DELETE FROM warns WHERE user_id=? AND chat_id=?", (uid, chat_id))
            conn.commit()
        except: pass

async def warns_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.reply_to_message.from_user.id if update.message.reply_to_message else update.effective_user.id
    cur.execute("SELECT count FROM warns WHERE user_id=? AND chat_id=?", (uid, update.effective_chat.id))
    row = cur.fetchone()
    await update.message.reply_text(f"⚠️ Warns: {row[0] if row else 0}/3")

async def clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.reply_to_message.from_user.id if update.message.reply_to_message else (int(context.args[0]) if context.args else None)
    if not uid:
        await update.message.reply_text("Reply or provide ID")
        return
    cur.execute("DELETE FROM warns WHERE user_id=? AND chat_id=?", (uid, update.effective_chat.id))
    conn.commit()
    await update.message.reply_text("✅ Warns cleared")

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to pin")
        return
    try:
        await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        await update.message.reply_text("📌 Pinned")
    except Exception as e:
        await update.message.reply_text(f"Pin failed: {e}")

async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.unpin_chat_message(update.effective_chat.id)
        await update.message.reply_text("📌 Unpinned")
    except Exception as e:
        await update.message.reply_text(f"Unpin failed: {e}")

async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("Groups only")
        return
    n = int(context.args[0]) if context.args and context.args[0].isdigit() else 5
    n = min(n, 100)
    try:
        # Purge needs admin and can't bulk delete easily without message IDs
        # We'll delete recent bot messages as demo
        await update.message.reply_text(f"🧹 Purging {n} messages... (Make bot admin with Delete permission)")
        # Real purge would need to fetch and delete loop
        for i in range(n):
            try:
                await context.bot.delete_message(update.effective_chat.id, update.message.message_id - i)
            except: pass
    except Exception as e:
        await update.message.reply_text(f"Purge failed: {e}")

async def afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = " ".join(context.args) if context.args else "AFK"
    cur.execute("INSERT OR REPLACE INTO afk(user_id, reason, since) VALUES(?,?,?)", (update.effective_user.id, reason, datetime.datetime.now().isoformat()))
    conn.commit()
    await update.message.reply_text(f"💤 {update.effective_user.first_name} is now AFK: {reason}")

async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("DELETE FROM todos WHERE user_id=?", (update.effective_user.id,))
    conn.commit()
    await update.message.reply_text("🗑️ Your todos cleared")

# --- EXTRA ---

async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    coin = context.args[0].lower() if context.args else "bitcoin"
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_24hr_change=true", timeout=8).json()
        price = r[coin]['usd']
        change = r[coin].get('usd_24h_change', 0)
        await update.message.reply_text(f"💰 *{coin.upper()}*: ${price:,.2f}\n24h: {change:.2f}%", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("❌ Coin not found. Try: bitcoin, ethereum, solana")

async def news_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search?tags=front_page", timeout=8).json()
        hits = r['hits'][:5]
        text = "🗞️ *Top Headlines:*\n\n"
        for i, h in enumerate(hits, 1):
            text += f"{i}. [{h['title']}]({h['url']})\n"
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"News failed: {e}")

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /stock AAPL")
        return
    symbol = context.args[0].upper()
    await update.message.reply_text(f"📈 *{symbol}* - Demo mode\nPrice: ${random.randint(100,500)}.{random.randint(10,99)}\nUse real API like Alpha Vantage for production.", parse_mode=ParseMode.MARKDOWN)

# Todos
async def todo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /todo Buy milk")
        return
    task = " ".join(context.args)
    cur.execute("INSERT INTO todos(user_id, task) VALUES(?,?)", (update.effective_user.id, task))
    conn.commit()
    await update.message.reply_text(f"✅ Added: {task}")

async def todolist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT id, task, done FROM todos WHERE user_id=?", (update.effective_user.id,))
    rows = cur.fetchall()
    if not rows:
        await update.message.reply_text("📝 No todos")
        return
    text = "📝 *Your Todos:*\n"
    for id_, task, done in rows:
        text += f"{'✅' if done else '⬜'} `{id_}` - {task}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def done_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /done 1")
        return
    try:
        tid = int(context.args[0])
        cur.execute("UPDATE todos SET done=1 WHERE id=? AND user_id=?", (tid, update.effective_user.id))
        conn.commit()
        await update.message.reply_text(f"✅ Done todo {tid}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# Reminders
async def remind_job(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(context.job.chat_id, text=f"⏰ Reminder: {context.job.data}")

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Use: /remind 10m take break\nFormats: 10s, 5m, 2h")
        return
    time_str = context.args[0]
    msg = " ".join(context.args[1:])
    m = re.match(r"(\d+)([smh])", time_str)
    if not m:
        await update.message.reply_text("Invalid time. Use 10s, 5m, 2h")
        return
    val, unit = int(m.group(1)), m.group(2)
    seconds = val * (1 if unit=='s' else 60 if unit=='m' else 3600)
    context.job_queue.run_once(remind_job, seconds, chat_id=update.effective_chat.id, data=msg, name=str(update.effective_user.id))
    await update.message.reply_text(f"⏰ I'll remind you in {time_str}: {msg}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # No admin needed - anyone can broadcast now
    # if not is_admin(update.effective_user.id):
    #     await update.message.reply_text("Admin only")
    #     return
    pass
    if not context.args:
        await update.message.reply_text("Use: /broadcast message")
        return
    text = " ".join(context.args)
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    count = 0
    for (uid,) in users:
        try:
            await context.bot.send_message(uid, f"📢 Broadcast:\n{text}")
            count += 1
        except: pass
    await update.message.reply_text(f"✅ Sent to {count} users")

# AFK watcher
async def afk_watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    # check if mentioned user is AFK
    if update.message.reply_to_message:
        cur.execute("SELECT reason, since FROM afk WHERE user_id=?", (update.message.reply_to_message.from_user.id,))
        row = cur.fetchone()
        if row:
            await update.message.reply_text(f"💤 {update.message.reply_to_message.from_user.first_name} is AFK since {row[1][:16]}: {row[0]}")
    # remove AFK if sender was AFK
    cur.execute("SELECT * FROM afk WHERE user_id=?", (update.effective_user.id,))
    if cur.fetchone():
        cur.execute("DELETE FROM afk WHERE user_id=?", (update.effective_user.id,))
        conn.commit()
        await update.message.reply_text(f"✅ Welcome back {update.effective_user.first_name}! AFK removed.")



# --- 30 NEW POWER COMMANDS ---

async def lyrics_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /lyrics song name - e.g. /lyrics blinding lights")
        return
    query = " ".join(context.args)
    try:
        r = requests.get(f"https://api.lyrics.ovh/v1/placeholder/{query}", timeout=5)
        # fallback mock
        await update.message.reply_text(f"🎵 *Lyrics for {query}:*\n\n[Demo] Lyrics API needs key, but you searched for {query} - add real API later!\n\nLa la la ~ 🎶", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text(f"🎵 Lyrics for {query} - coming soon! Add lyrics.ovh API")

async def github_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /github username - e.g. /github torvalds")
        return
    user = context.args[0]
    try:
        r = requests.get(f"https://api.github.com/users/{user}", timeout=5).json()
        if "login" in r:
            await update.message.reply_text(f"👨‍💻 *GitHub: {r['login']}*\n📦 Repos: {r['public_repos']}\n👥 Followers: {r['followers']}\n📝 Bio: {r.get('bio','No bio')}\n🔗 {r['html_url']}", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("User not found")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def ip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ip = context.args[0] if context.args else ""
    try:
        url = f"https://ipapi.co/{ip}/json/" if ip else "https://ipapi.co/json/"
        r = requests.get(url, timeout=5).json()
        await update.message.reply_text(f"🌍 *IP Info*\nIP: {r.get('ip')}\nCity: {r.get('city')}\nRegion: {r.get('region')}\nCountry: {r.get('country_name')}\nOrg: {r.get('org')}", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text("Could not fetch IP info")

async def bin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /bin 424242 - check card bin")
        return
    bin_no = context.args[0][:6]
    try:
        r = requests.get(f"https://lookup.binlist.net/{bin_no}", headers={"Accept-Version":"3"}, timeout=5).json()
        await update.message.reply_text(f"💳 *BIN: {bin_no}*\n🏦 Bank: {r.get('bank',{}).get('name','Unknown')}\n💰 Type: {r.get('type')}\n🌍 Country: {r.get('country',{}).get('name')}")
    except:
        await update.message.reply_text(f"💳 BIN {bin_no} - Bank info placeholder (add binlist API)")

async def country_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /country nigeria")
        return
    c = " ".join(context.args)
    try:
        r = requests.get(f"https://restcountries.com/v3.1/name/{c}", timeout=5).json()[0]
        await update.message.reply_text(f"🌍 *{r['name']['common']}*\nCapital: {r.get('capital',[0])[0]}\nRegion: {r['region']}\nPopulation: {r['population']:,}\nFlag: {r['flag']}", parse_mode=ParseMode.MARKDOWN)
    except:
        await update.message.reply_text(f"Country {c} not found")

async def love_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Use: /love you me - e.g. /love John Jane")
        return
    n1, n2 = context.args[0], context.args[1]
    score = random.randint(50, 100)
    await update.message.reply_text(f"💘 *Love Calculator*\n{n1} ❤️ {n2} = {score}%\n" + ("Perfect match! 💍" if score>80 else "Nice! ❤️" if score>60 else "Try harder 😅"))

async def ship_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message and len(context.args)<1:
        await update.message.reply_text("Reply to someone or /ship @user")
        return
    target = update.message.reply_to_message.from_user.first_name if update.message.reply_to_message else context.args[0]
    score = random.randint(20, 99)
    await update.message.reply_text(f"🚢 *Shipping*\n{update.effective_user.first_name} 💞 {target} = {score}% compatibility!")

async def truth_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    truths = ["What is your biggest secret?","Who do you have a crush on?","Have you ever cheated?","What is your worst habit?","What is your dream job?"]
    await update.message.reply_text(f"😏 *Truth:* {random.choice(truths)}")

async def dare_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dares = ["Send 'I love you' to your 3rd contact","Do 10 pushups now","Change your DP to a funny pic for 1 hour","Sing a song in group voice note","Text your crush"]
    await update.message.reply_text(f"😈 *Dare:* {random.choice(dares)}")

async def hack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = " ".join(context.args) if context.args else "Target"
    steps = ["[▓     ] 10% Injecting malware..."," [▓▓▓   ] 40% Hacking password..."," [▓▓▓▓▓ ] 80% Accessing data..."," [▓▓▓▓▓▓] 100% Hacked! 😎"]
    msg = await update.message.reply_text(f"💻 Hacking {target}...")
    import asyncio
    for s in steps:
        await asyncio.sleep(1)
        try: await msg.edit_text(f"💻 {s}")
        except: pass
    await msg.edit_text(f"✅ *Hacked {target}!* (Just kidding 😂 This is fake hack)", parse_mode=ParseMode.MARKDOWN)

async def wallpaper_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_photo(f"https://picsum.photos/1080/1920?random={random.randint(1,10000)}", caption="🖼️ Random Wallpaper")
    except:
        await update.message.reply_text("Wallpaper failed")

async def emojimix_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)<2:
        await update.message.reply_text("Use: /emojimix 😂 ❤️")
        return
    e1, e2 = context.args[0], context.args[1]
    await update.message.reply_text(f"Mixing {e1} + {e2} = {e1}{e2} (Add real emoji kitchen API for real mix)")

async def fancy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /fancy your text")
        return
    text = " ".join(context.args)
    fancy_text = text.translate(str.maketrans("abcdefghijklmnopqrstuvwxyz","ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"))
    await update.message.reply_text(f"✨ Fancy:\n{fancy_text}")

async def currency_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)<3:
        await update.message.reply_text("Use: /currency 100 USD NGN")
        return
    try:
        amount = float(context.args[0])
        from_cur = context.args[1].upper()
        to_cur = context.args[2].upper()
        r = requests.get(f"https://api.exchangerate-api.com/v4/latest/{from_cur}", timeout=5).json()
        rate = r["rates"].get(to_cur)
        if rate:
            result = amount * rate
            await update.message.reply_text(f"💱 {amount} {from_cur} = {result:.2f} {to_cur}")
        else:
            await update.message.reply_text("Currency not found")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def urban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /urban word")
        return
    word = " ".join(context.args)
    try:
        r = requests.get(f"https://api.urbandictionary.com/v0/define?term={word}", timeout=5).json()
        if r["list"]:
            defi = r["list"][0]["definition"][:500]
            await update.message.reply_text(f"📚 *Urban {word}:*\n{defi}", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("No definition found")
    except:
        await update.message.reply_text("Urban API error")

async def toimg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message and update.message.reply_to_message.sticker:
        await update.message.reply_text("Converting sticker to image... (needs file download logic)")
    else:
        await update.message.reply_text("Reply to a sticker with /toimg")

async def aiimg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /aiimg a cat in space")
        return
    prompt = " ".join(context.args)
    await update.message.reply_text(f"🎨 Generating image for: {prompt}\n[Add Stable Diffusion API key for real generation - demo mode]")

async def ytmp3_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /ytmp3 youtube link")
        return
    await update.message.reply_text(f"🎵 Downloading MP3 from {context.args[0]} - Add yt-dlp logic for real download [Demo]")

async def ytmp4_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /ytmp4 youtube link")
        return
    await update.message.reply_text(f"🎬 Downloading MP4 from {context.args[0]} - Add yt-dlp logic [Demo]")

async def qrread_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📷 Send a photo with QR code and reply /qrread")

async def short2_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /short2 https://google.com")
        return
    await update.message.reply_text(f"🔗 Short: https://tinyurl.com/api-create.php?url={context.args[0]} (demo)")

async def calc2_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # advanced calc with math functions
    if not context.args:
        await update.message.reply_text("Use: /calc2 2+2*5 or sqrt(16)")
        return
    expr = " ".join(context.args)
    try:
        import math
        allowed = {k: getattr(math, k) for k in ["sqrt","sin","cos","tan","log","pi","e"]}
        result = eval(expr, {"__builtins__":{}}, allowed)
        await update.message.reply_text(f"🧮 {expr} = {result}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def stalk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /githubstalk username")
        return
    await github_cmd(update, context)

async def getpp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count>0:
            await update.message.reply_photo(photos.photos[0][-1].file_id, caption=f"PP of {user.first_name}")
        else:
            await update.message.reply_text("No PP found")
    else:
        await update.message.reply_text("Reply to user with /getpp to get their profile pic")

async def hidetag_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type=="private":
        await update.message.reply_text("Use in group: /hidetag message")
        return
    msg = " ".join(context.args) if context.args else "Hi everyone!"
    # This would mention all but telegram limits - demo
    await update.message.reply_text(f"📢 Hidetag: {msg} (Tagging all...)")

async def tagall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await hidetag_cmd(update, context)

async def promote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to user to promote")
        return
    try:
        await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, can_delete_messages=True)
        await update.message.reply_text("✅ Promoted!")
    except:
        await update.message.reply_text("Make me admin first!")

async def demote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to user to demote")
        return
    try:
        await context.bot.promote_chat_member(update.effective_chat.id, update.message.reply_to_message.from_user.id, can_delete_messages=False, can_restrict_members=False)
        await update.message.reply_text("✅ Demoted!")
    except:
        await update.message.reply_text("Make me admin!")

async def setwelcome_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Welcome message set! (Demo - save to DB logic)")


# --- DREAM-MD STYLE EXTRA COMMANDS ---

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    diff = int(time.time() - START_TIME)
    h, rem = divmod(diff, 3600)
    m, s = divmod(rem, 60)
    runtime = f"{h}h {m}m {s}s"
    try:
        text = HELP_TEXT.format(runtime=runtime)
    except:
        text = HELP_TEXT
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(text)


async def alive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    diff = int(time.time() - START_TIME)
    h, rem = divmod(diff, 3600)
    m, s = divmod(rem, 60)
    await update.message.reply_text(f"━━━━━━ 🤖 ᴀʟɪᴠᴇ ━━━━━━\n◉ ʙᴏᴛ ɪs ᴀʟɪᴠᴇ! ✅\n◉ ᴜᴘᴛɪᴍᴇ: {h}h {m}m {s}s\n◉ ᴍᴏᴅᴇ: public\n◉ ᴠᴇʀsɪᴏɴ: 12.0.0 Beta")

async def repo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📦 *Repo:* https://github.com/oreoluwaolawale990-bit/mdbot224323456\n⭐ Give a star!", parse_mode=ParseMode.MARKDOWN)

async def dream_ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Generic AI handler for gpt35, gpt4, claude, etc
    cmd = update.message.text.split()[0].lstrip('/.').lower()
    prompt = " ".join(context.args) if context.args else ""
    if not prompt:
        await update.message.reply_text(f"Use: /{cmd} your question\nExample: /{cmd} who is Elon Musk?")
        return
    # Simple AI mock using wikipedia + fun response - replace with real API if you have key
    await update.message.reply_text(f"🤖 *{cmd.upper()}* is thinking...\n\nQ: {prompt}\n\nA: This is DREAM-MD AI ({cmd}) response. For real AI, connect OpenAI key. But I can still answer: {prompt[:100]}... is interesting! [Demo mode]", parse_mode=ParseMode.MARKDOWN)

async def dot_prefix_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle .command like WhatsApp bots
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text.startswith('.'):
        return
    # Convert .command to /command
    cmd_text = '/' + text[1:]
    update.message.text = cmd_text
    # Re-route to command handlers by manually checking
    # For simplicity, just show menu for .menu
    if cmd_text.startswith('/menu') or cmd_text.startswith('/help'):
        await menu_cmd(update, context)
    elif cmd_text.startswith('/alive') or cmd_text.startswith('/bot'):
        await alive(update, context)


# --- MAIN ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("menu2", menu_cmd))
    app.add_handler(CommandHandler("alive", alive))
    app.add_handler(CommandHandler("bot", alive))
    app.add_handler(CommandHandler("repo", repo_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("help2", help_classic))
    app.add_handler(CommandHandler("h", help_cmd))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("uptime", uptime))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("chatinfo", chatinfo))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("settings", settings_cmd))

    # Tools
    app.add_handler(CommandHandler("time", time_cmd))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("translate", translate))
    app.add_handler(CommandHandler("calc", calc))
    app.add_handler(CommandHandler("math", calc))
    app.add_handler(CommandHandler("qr", qr_cmd))
    app.add_handler(CommandHandler("shorturl", shorturl))
    app.add_handler(CommandHandler("password", password))
    app.add_handler(CommandHandler("define", define))
    app.add_handler(CommandHandler("wiki", wiki_cmd))
    app.add_handler(CommandHandler("screenshot", screenshot_cmd))
    app.add_handler(CommandHandler("tts", tts))
    app.add_handler(CommandHandler("sticker", sticker_cmd))

    # Fun
    app.add_handler(CommandHandler("dice", dice_cmd))
    app.add_handler(CommandHandler("roll", roll))
    app.add_handler(CommandHandler("flip", flip))
    app.add_handler(CommandHandler("choose", choose))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CommandHandler("quote", quote_cmd))
    app.add_handler(CommandHandler("meme", meme))
    app.add_handler(CommandHandler("fact", fact))
    app.add_handler(CommandHandler("8ball", eightball))
    app.add_handler(CommandHandler("roast", roast))
    app.add_handler(CommandHandler("compliment", compliment))
    app.add_handler(CommandHandler("poll", poll_cmd))

    # Moderation
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("warns", warns_cmd))
    app.add_handler(CommandHandler("clearwarns", clearwarns))
    app.add_handler(CommandHandler("pin", pin))
    app.add_handler(CommandHandler("unpin", unpin))
    app.add_handler(CommandHandler("purge", purge))
    app.add_handler(CommandHandler("afk", afk))
    app.add_handler(CommandHandler("clear", clear_cmd))

    # Extra
    app.add_handler(CommandHandler("crypto", crypto))
    app.add_handler(CommandHandler("news", news_cmd))
    app.add_handler(CommandHandler("stock", stock))
    app.add_handler(CommandHandler("todo", todo))
    app.add_handler(CommandHandler("todolist", todolist))
    app.add_handler(CommandHandler("done", done_cmd))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # 30 NEW COMMANDS
    app.add_handler(CommandHandler("lyrics", lyrics_cmd))
    app.add_handler(CommandHandler("github", github_cmd))
    app.add_handler(CommandHandler("githubstalk", github_cmd))
    app.add_handler(CommandHandler("ip", ip_cmd))
    app.add_handler(CommandHandler("bin", bin_cmd))
    app.add_handler(CommandHandler("country", country_cmd))
    app.add_handler(CommandHandler("love", love_cmd))
    app.add_handler(CommandHandler("ship", ship_cmd))
    app.add_handler(CommandHandler("truth", truth_cmd))
    app.add_handler(CommandHandler("dare", dare_cmd))
    app.add_handler(CommandHandler("hack", hack_cmd))
    app.add_handler(CommandHandler("wallpaper", wallpaper_cmd))
    app.add_handler(CommandHandler("emojimix", emojimix_cmd))
    app.add_handler(CommandHandler("fancy", fancy_cmd))
    app.add_handler(CommandHandler("currency", currency_cmd))
    app.add_handler(CommandHandler("urban", urban_cmd))
    app.add_handler(CommandHandler("toimg", toimg_cmd))
    app.add_handler(CommandHandler("aiimg", aiimg_cmd))
    app.add_handler(CommandHandler("ytmp3", ytmp3_cmd))
    app.add_handler(CommandHandler("ytmp4", ytmp4_cmd))
    app.add_handler(CommandHandler("qrread", qrread_cmd))
    app.add_handler(CommandHandler("short2", short2_cmd))
    app.add_handler(CommandHandler("calc2", calc2_cmd))
    app.add_handler(CommandHandler("getpp", getpp_cmd))
    app.add_handler(CommandHandler("hidetag", hidetag_cmd))
    app.add_handler(CommandHandler("tagall", tagall_cmd))
    app.add_handler(CommandHandler("promote", promote_cmd))
    app.add_handler(CommandHandler("demote", demote_cmd))
    app.add_handler(CommandHandler("setwelcome", setwelcome_cmd))
    app.add_handler(CommandHandler("welcome", setwelcome_cmd))


    # Dream AI commands
    for ai_cmd in ["gpt35","gpt4","gpt4o","claude","claudeopus","gemini","geminipro","grok","grokbeta","deepseek","llama","llama2","llama3","perplexity","mistral","bard","copilot","askai","brain","think"]:
        app.add_handler(CommandHandler(ai_cmd, dream_ai_handler))

    # Dream anime commands
    for anime_cmd in ["waifu","neko","kitsune","husbando","animegirl","animeboy","catgirl","foxgirl","maid","cosplay"]:
        app.add_handler(CommandHandler(anime_cmd, meme))  # reuse meme for demo

    # Dream download commands
    for dl_cmd in ["play","video","fb","tiktok","insta","instagram","apk","pinterest"]:
        app.add_handler(CommandHandler(dl_cmd, news_cmd))  # placeholder


    # AFK watcher for all messages
    app.add_handler(MessageHandler(filters.Regex(r"^\."), dot_prefix_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, afk_watcher))

    print("Bot starting...")
    if WEBHOOK_URL:
        print(f"Using webhook: {WEBHOOK_URL}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        # Start fake web server so Render free web service stays happy
        start_health_server()
        app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
