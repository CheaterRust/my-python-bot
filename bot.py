#!/usr/bin/env python3
"""
Локальный Telegram-бот для управления ПК.

Функции:
 - Скриншот
 - Запуск Steam и диспетчера задач
 - Закрытие/переключение окон (Alt+F4, Alt+Tab)
 - Управление громкостью
 - Скачивание аудио с YouTube

Требуется:
    pip install python-telegram-bot==21.5 mss yt-dlp pyautogui keyboard

FFmpeg должен находиться в пути D:\\PythonTools\\DownloadYouTybe\\Bin
"""

import logging
import os
import re
import tempfile
import time
import subprocess
import pyautogui
import mss
import mss.tools
import keyboard
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ============================================================== 
# Настройки
# ============================================================== 
BOT_TOKEN = "7999288654:AAHurbfQPiiIoYXtynxmoL8I5Da8kaW1J5k"
ALLOWED_ID = 1679030860
STEAM_PATH = r"D:\Game\Steam\steam.exe"
FFMPEG_BIN = r"D:\PythonTools\DownloadYouTybe\Bin"
TASKMGR_PATH = r"C:\Windows\System32\Taskmgr.exe"

# ============================================================== 
# Логирование
# ============================================================== 
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# ============================================================== 
# Утилиты
# ============================================================== 
def is_authorized(user_id: int) -> bool:
    return user_id == ALLOWED_ID


def make_screenshot_file() -> str:
    timestamp = int(time.time())
    filename = f"screenshot_{timestamp}.png"
    out_path = os.path.join(tempfile.gettempdir(), filename)
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        sct_img = sct.grab(monitor)
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=out_path)
    return out_path


def try_open_executable(path: str) -> None:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл не найден: {path}")
    if os.name == "nt":
        os.startfile(path)
    else:
        subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def download_youtube_audio(url: str) -> str:
    import yt_dlp

    temp_dir = tempfile.gettempdir()
    out_template = os.path.join(temp_dir, "%(title)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "ffmpeg_location": FFMPEG_BIN,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "noplaylist": True,
        "nocheckcertificate": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "audio")
        return os.path.join(temp_dir, f"{title}.mp3")

# ============================================================== 
# Системные команды
# ============================================================== 
async def alt_tab_handler(update, context):
    user = update.effective_user
    if not (user and is_authorized(user.id)):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text("Переключаю окно (Alt+Tab)...")
    try:
        pyautogui.hotkey("alt", "tab")
        await update.message.reply_text("Alt+Tab выполнен.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def volume_up_handler(update, context):
    user = update.effective_user
    if not (user and is_authorized(user.id)):
        await update.message.reply_text("Нет доступа.")
        return
    try:
        pyautogui.press("volumeup")
        await update.message.reply_text("Громкость увеличена 🔊")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def volume_down_handler(update, context):
    user = update.effective_user
    if not (user and is_authorized(user.id)):
        await update.message.reply_text("Нет доступа.")
        return
    try:
        pyautogui.press("volumedown")
        await update.message.reply_text("Громкость уменьшена 🔉")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


# ============================================================== 
# Основные команды
# ============================================================== 
async def start_handler(update, context):
    user = update.effective_user
    if user and is_authorized(user.id):
        await update.message.reply_text(
            "🖥 Управление ПК через Telegram:\n\n"
            "/screenshot — скриншот\n"
            "/opensteam — запустить Steam\n"
            "/opentaskmgr — диспетчер задач\n"
            "/altf4 — закрыть окно\n"
            "/alttab — переключить окно\n"
            "/volume_up — громче\n"
            "/volume_down — тише\n"
            "/yt_audio <ссылка> — скачать аудио с YouTube\n"
            "/info — ID\n\n"
            "📎 Просто отправь ссылку на YouTube — бот скачает аудио автоматически."
        )
    else:
        await update.message.reply_text("Нет доступа.")


async def screenshot_handler(update, context):
    user = update.effective_user
    if not (user and is_authorized(user.id)):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text("Делаю скриншот...")
    try:
        out_path = make_screenshot_file()
        with open(out_path, "rb") as img:
            await update.message.reply_photo(photo=img, caption="Скриншот с ПК")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


async def open_steam_handler(update, context):
    user = update.effective_user
    if not (user and is_authorized(user.id)):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text("Запускаю Steam...")
    try:
        try_open_executable(STEAM_PATH)
        await update.message.reply_text("Steam запущен.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def open_taskmgr_handler(update, context):
    user = update.effective_user
    if not (user and is_authorized(user.id)):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text("Открываю диспетчер задач...")
    try:
        try_open_executable(TASKMGR_PATH)
        await update.message.reply_text("Диспетчер задач запущен.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def altf4_handler(update, context):
    user = update.effective_user
    if not (user and is_authorized(user.id)):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text("Закрываю активное окно...")
    try:
        # Используем keyboard, чтобы Alt точно отпускался
        keyboard.press_and_release("alt+f4")
        await update.message.reply_text("Alt+F4 выполнен.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def yt_audio_handler(update, context):
    user = update.effective_user
    if not (user and is_authorized(user.id)):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /yt_audio <ссылка>")
        return
    url = context.args[0]
    await update.message.reply_text("Скачиваю аудио...")
    try:
        mp3_path = download_youtube_audio(url)
        with open(mp3_path, "rb") as audio:
            await update.message.reply_audio(audio, caption="Ваше аудио 🎵")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)


async def auto_yt_handler(update, context):
    user = update.effective_user
    if not (user and is_authorized(user.id)):
        return
    text = update.message.text.strip()
    youtube_regex = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
    if not re.match(youtube_regex, text):
        return
    await update.message.reply_text("Обнаружена ссылка на YouTube, скачиваю аудио...")
    try:
        mp3_path = download_youtube_audio(text)
        with open(mp3_path, "rb") as audio:
            await update.message.reply_audio(audio, caption="Ваше аудио 🎧")
    except Exception:
        await update.message.reply_text("Ошибка при скачивании.")
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)


async def info_handler(update, context):
    user = update.effective_user
    if user:
        await update.message.reply_text(f"Ваш ID: {user.id}")
    else:
        await update.message.reply_text("Нет данных.")


async def unknown_handler(update, context):
    await update.message.reply_text("Неизвестная команда.")


# ============================================================== 
# Главная
# ============================================================== 
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("screenshot", screenshot_handler))
    app.add_handler(CommandHandler("opensteam", open_steam_handler))
    app.add_handler(CommandHandler("opentaskmgr", open_taskmgr_handler))
    app.add_handler(CommandHandler("altf4", altf4_handler))
    app.add_handler(CommandHandler("alttab", alt_tab_handler))
    app.add_handler(CommandHandler("volume_up", volume_up_handler))
    app.add_handler(CommandHandler("volume_down", volume_down_handler))
    app.add_handler(CommandHandler("yt_audio", yt_audio_handler))
    app.add_handler(CommandHandler("info", info_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_yt_handler))

    print("✅ Бот запущен. Ожидаю сообщений...")
    app.run_polling()


if __name__ == "__main__":
    main()
