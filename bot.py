import os
import asyncio
import yt_dlp
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

TOKEN = os.getenv("BOT_TOKEN")

mode = {}
search_cache = {}

# ---------- START ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        ["⬇️ Скачать по ссылке"],
        ["🔎 Найти песню"],
        ["⬅ Назад"]
    ]

    await update.message.reply_text(
        "🎵 Выбери действие:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )

# ---------- ПОИСК ----------

def search_music(query, count=5):

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "js_runtimes": {"node": {}}
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(
            f"ytsearch{count}:{query}",
            download=False
        )

    results = []

    for video in info["entries"]:
        results.append({
            "title": video["title"],
            "url": video["webpage_url"]
        })

    return results

# ---------- СООБЩЕНИЯ ----------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    user_id = update.message.from_user.id

    if text == "⬅ Назад":

        mode[user_id] = None

        await update.message.reply_text(
            "🏠 Главное меню"
        )

        return

    if text == "⬇️ Скачать по ссылке":

        mode[user_id] = "link"

        await update.message.reply_text(
            "📎 Отправь ссылку YouTube или YouTube Music"
        )

        return

    if text == "🔎 Найти песню":

        mode[user_id] = "search"

        await update.message.reply_text(
            "🔎 Напиши название песни"
        )

        return

    if mode.get(user_id) == "link":

        if "youtube.com" not in text and "youtu.be" not in text and "music.youtube.com" not in text:
            await update.message.reply_text("❌ Это не ссылка YouTube")
            return

        key = f"{user_id}_link"
        search_cache[key] = text

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎵 Скачать MP3",
                    callback_data=f"mp3|{key}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚡ Скачать M4A (быстрее)",
                    callback_data=f"m4a|{key}"
                )
            ]
        ])

        await update.message.reply_text(
            "🎧 Выбери формат:",
            reply_markup=keyboard
        )

        return

    if mode.get(user_id) == "search":

        await update.message.reply_text("🔎 Ищу...")

        results = search_music(text, 5)

        buttons = []

        for i, video in enumerate(results):

            key = f"{user_id}_{i}"
            search_cache[key] = video["url"]

            buttons.append([
                InlineKeyboardButton(
                    video["title"][:60],
                    callback_data=f"select|{key}"
                )
            ])

        keyboard = InlineKeyboardMarkup(buttons)

        await update.message.reply_text(
            "🎧 Выбери версию:",
            reply_markup=keyboard
        )

# ---------- КНОПКИ ----------

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data.split("|")

    action = data[0]
    key = data[1]

    url = search_cache.get(key)

    if not url:
        await query.message.reply_text("❌ Ссылка не найдена")
        return

    if action == "select":

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎵 Скачать MP3",
                    callback_data=f"mp3|{key}"
                )
            ],
            [
                InlineKeyboardButton(
                    "⚡ Скачать M4A (быстрее)",
                    callback_data=f"m4a|{key}"
                )
            ]
        ])

        await query.message.reply_text(
            "🎧 Выбери формат:",
            reply_markup=keyboard
        )

        return

    await query.message.reply_text("⚡ Скачиваю...")

    url = url.replace("music.youtube.com", "youtube.com")

    if action == "m4a":

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "song.%(ext)s",
            "writethumbnail": True,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
            ],
            "quiet": True,
            "concurrent_fragment_downloads": 5,
            "js_runtimes": {"node": {}}
        }

    else:

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "song.%(ext)s",
            "writethumbnail": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320"
                }
            ],
            "quiet": True,
            "concurrent_fragment_downloads": 5,
            "js_runtimes": {"node": {}}
        }

    loop = asyncio.get_event_loop()

    def download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)

    info = await loop.run_in_executor(None, download)

    # ---------- УМНОЕ ОПРЕДЕЛЕНИЕ ARTIST / TITLE ----------

    track = info.get("track")
    artist = info.get("artist") or info.get("creator")

    if track and artist:
        title = track
    else:

        video_title = info.get("title", "Music")

        if " - " in video_title:

            parts = video_title.split(" - ", 1)

            artist = parts[0]
            title = parts[1]

        else:

            title = video_title
            artist = info.get("uploader", "Unknown")

    # ------------------------------------------------------

    thumbnail = info.get("thumbnail")

    if thumbnail:
        await query.message.reply_photo(
            photo=thumbnail,
            caption=f"🎵 {artist} — {title}"
        )

    file = "song.m4a" if action == "m4a" else "song.mp3"

    await query.message.reply_audio(
        audio=open(file, "rb"),
        title=title,
        performer=artist
    )

    try:
        os.remove(file)
    except:
        pass

# ---------- ЗАПУСК ----------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    )
)

app.add_handler(CallbackQueryHandler(button))

print("🚀 Бот запущен")

app.run_polling()