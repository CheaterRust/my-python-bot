import telegram
from telegram.ext import Application, MessageHandler, filters, CommandHandler
import subprocess
from pathlib import Path
import os
import logging
import shutil
import asyncio
import json
import re
import tempfile
import psutil  # pip install psutil

# ----------------------------------------------------
# 1. КОНФИГ И ЛОГИ
# ----------------------------------------------------

CONFIG_PATH = Path("config.json")
if not CONFIG_PATH.exists():
    raise FileNotFoundError("Файл config.json не найден!")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

BOT_TOKEN = config.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в config.json")

FFMPEG_BIN_DIR = r"D:\PythonTools\py\DownloadYouTybe\Bin"
YTDLP_PATH = 'yt-dlp'
DOWNLOAD_TIMEOUT = 600
ACTIVE_DOWNLOAD_FLAG = False

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

YOUTUBE_URL_REGEX = re.compile(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$")

# ----------------------------------------------------
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ----------------------------------------------------

def get_video_name(url: str) -> str:
    try:
        clean_url = url.split('?')[0]
        result = subprocess.run(
            [YTDLP_PATH, "--no-check-certificate", "-j", clean_url],
            capture_output=True,
            text=True,
            check=True
        )
        info = json.loads(result.stdout)
        return f"{info['title']}.mp3"
    except Exception as e:
        logger.error(f"Ошибка при получении названия видео: {e}")
        return None

def limit_resources(proc_pid, memory_limit_mb=500):
    """Ограничение памяти процесса через psutil"""
    try:
        p = psutil.Process(proc_pid)
        p.rlimit(psutil.RLIMIT_AS, (memory_limit_mb * 1024 * 1024, memory_limit_mb * 1024 * 1024))
    except Exception as e:
        logger.warning(f"Не удалось ограничить ресурсы процесса: {e}")

def download_audio_from_youtube(url: str) -> tuple[Path, str]:
    logger.info(f"Скачивание для URL: {url}")
    
    tmpdir = Path(tempfile.mkdtemp(prefix="ytbot_"))
    out_template = "%(title)s.%(ext)s"
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

    proc = subprocess.Popen([
        YTDLP_PATH,
        "--no-check-certificate",
        "--no-playlist",
        "--no-warnings",
        "--format", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "mp3",
        "--ffmpeg-location", FFMPEG_BIN_DIR,
        "--output", out_template,
        url
    ], cwd=tmpdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
       creationflags=creation_flags)

    limit_resources(proc.pid, memory_limit_mb=500)

    try:
        stdout, stderr = proc.communicate(timeout=DOWNLOAD_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise TimeoutError("Превышен таймаут скачивания.")

    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp завершился с ошибкой: {stderr.strip()}")

    audio_file = next((f for f in tmpdir.iterdir() if f.is_file() and f.suffix.lower() == '.mp3'), None)
    if not audio_file:
        raise FileNotFoundError("Не найден MP3-файл после yt-dlp.")

    logger.info(f"Скачивание завершено: {audio_file.name}")
    return audio_file, audio_file.name

def read_file_sync(path: Path) -> bytes:
    with open(path, 'rb') as f:
        return f.read()

# ----------------------------------------------------
# 3. ФОНОВАЯ АСИНХРОННАЯ ЗАДАЧА
# ----------------------------------------------------

async def execute_long_task(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    global ACTIVE_DOWNLOAD_FLAG
    url = update.message.text
    message = await update.message.reply_text("Начинаю скачивание аудио...")

    try:
        audio_path, file_name = await asyncio.to_thread(download_audio_from_youtube, url)
        file_content = await asyncio.to_thread(read_file_sync, audio_path)
        
        await update.message.reply_audio(
            audio=file_content,
            caption=file_name,
            title=file_name.rsplit(".", 1)[0],
            read_timeout=180,
            write_timeout=180
        )
        await message.edit_text("Аудио успешно отправлено.")
    except Exception as e:
        logger.error(f"Ошибка при обработке: {e}")
        await message.edit_text(f"Произошла ошибка: {e}")
    finally:
        ACTIVE_DOWNLOAD_FLAG = False
        if 'tmpdir' in locals() and tmpdir.exists():
            shutil.rmtree(tmpdir, ignore_errors=True)

# ----------------------------------------------------
# 4. ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ
# ----------------------------------------------------

async def start_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь ссылку на YouTube. Один запрос одновременно.")

async def handle_url(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    global ACTIVE_DOWNLOAD_FLAG
    url = update.message.text

    if not YOUTUBE_URL_REGEX.match(url):
        await update.message.reply_text("Некорректная ссылка на YouTube.")
        return

    if ACTIVE_DOWNLOAD_FLAG:
        await update.message.reply_text("Бот занят. Попробуйте позже.")
        return

    ACTIVE_DOWNLOAD_FLAG = True
    asyncio.create_task(execute_long_task(update, context))

# ----------------------------------------------------
# 5. ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА
# ----------------------------------------------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    youtube_filter = filters.TEXT & (filters.Regex(r'youtube\.com/') | filters.Regex(r'youtu\.be/'))
    app.add_handler(MessageHandler(youtube_filter, handle_url))
    logger.info("Бот запущен. Ожидание ссылок...")
    app.run_polling(allowed_updates=telegram.Update.ALL_TYPES)

if __name__ == '__main__':
    main()
