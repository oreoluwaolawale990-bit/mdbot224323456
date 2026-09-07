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
🚀 *POWER BOT - 55 COMMANDS*

*CORE:*
/start - Start bot
/help - This menu
/about - About bot
/ping - Check latency
/uptime - Bot uptime
/id - Get IDs
/info - Your info
/chatinfo - Chat info
/stats - Bot stats
/settings - Settings

*TOOLS:*
/time - Current time
/weather [city] - Weather
/translate [lang] text - Translate
/calc 2+2*5 - Calculator
/qr text - Generate QR
/shorturl https://... - Shorten URL
/password [len] - Generate password
/define word - Dictionary
/wiki query - Wikipedia
/screenshot url - Website screenshot
/tts text - Text to voice
/sticker - Reply to photo to make sticker

*FUN:*
/dice - Roll dice
/roll 1-100 - Random number
/flip - Coin flip
/choose a,b,c - Choose random
/joke - Random joke
/quote - Inspirational quote
/meme - Random meme
/fact - Random fact
/8ball question - Magic 8ball
/roast - Roast me
/compliment - Compliment
/poll question | opt1 | opt2 - Create poll

*MODERATION (Groups):*
/ban - Ban user (reply)
/unban - Unban
/kick - Kick user
/mute - Mute user
/unmute - Unmute
/warn - Warn user
/warns - Check warns
/clearwarns - Clear warns
/pin - Pin message (reply)
/unpin - Unpin
/purge [n] - Delete last n messages
/afk [reason] - Set AFK
/clear - Clear bot messages

*UTILITY:*
/crypto btc - Crypto price
/news - Top headlines
/stock AAPL - Stock (demo)
/todo task - Add todo
/todolist - List todos
/done [id] - Complete todo
/remind 10m take break - Reminder
/broadcast - Admin broadcast

Just type any command!
"""

ABOUT_TEXT = """
🤖 *Power Telegram Bot v2.0*

Built with:
• python-telegram-bot v20.7
• Async + SQLite
• 55 powerful commands
• Ready for Render.com

Features: moderation, fun, tools, crypto, todos, AFK, reminders.

Dev: You | Hosted on Render
"""

# --- CORE COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cur.execute("INSERT OR IGNORE INTO users(user_id, username, first_seen) VALUES(?,?,?)",
                (user.id, user.username or user.first_name, datetime.datetime.now().isoformat()))
    conn.commit()
    kb = [[InlineKeyboardButton("📜 Commands", callback_data="help"),
           InlineKeyboardButton("ℹ️ About", callback_data="about")]]
    await update.message.reply_text(
        f"Hey {user.first_name}! 👋\n\nI'm your *Power Bot* with 55 commands.\nFast, powerful, ready for groups.\n\nType /help to see everything.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(ABOUT_TEXT, parse_mode=ParseMode.MARKDOWN)

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

# --- MAIN ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
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

    # AFK watcher for all messages
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
