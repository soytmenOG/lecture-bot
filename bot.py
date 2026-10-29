"""Бот-конспектор лекций и вебинаров: аудио/голосовое/видео → конспект, термины, выводы, черновик статьи.

Бесплатный. Всё считается на нашем сервере: Whisper (расшифровка) + Ollama (текст).
Приватность: запись и тексты удаляются сразу после отправки, в базе только Telegram ID и счётчики.
"""
import asyncio
import html
import logging
import os
import sqlite3
import tempfile
import time
from dataclasses import dataclass, field

BASE = os.path.dirname(os.path.abspath(__file__))


def load_env(path: str) -> None:
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


load_env(os.path.join(BASE, ".env"))

from aiogram import Bot, Dispatcher, F  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.client.session.aiohttp import AiohttpSession  # noqa: E402
from aiogram.client.telegram import TelegramAPIServer  # noqa: E402
from aiogram.filters import Command, CommandObject, CommandStart  # noqa: E402
from aiogram.types import (BufferedInputFile, CallbackQuery, InlineKeyboardButton,  # noqa: E402
                           InlineKeyboardMarkup, Message)
from urllib.parse import quote  # noqa: E402

import notes  # noqa: E402
import render  # noqa: E402
import transcribe  # noqa: E402
from i18n import T, WARN, ui_lang  # noqa: E402

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CODE = os.getenv("ADMIN_CODE", "")
BOT_API_URL = os.getenv("BOT_API_URL", "")            # свой сервер Bot API (файлы до 2 ГБ); пусто — обычный (20 МБ)
MAX_MINUTES = int(os.getenv("MAX_MINUTES", "240"))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE, "data", "bot.db"))
MAX_MB = 2000 if BOT_API_URL else 20

MEDIA_EXT = {".mp3", ".m4a", ".ogg", ".oga", ".opus", ".wav", ".flac", ".aac", ".wma", ".amr", ".webm",
             ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".m4v", ".3gp", ".mpeg", ".mpg"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for noisy in ("aiogram", "httpx", "httpcore", "faster_whisper"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("lecture-bot")

dp = Dispatcher()


# ---------- база: только ID и счётчики ----------

def db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            jobs INTEGER DEFAULT 0, seconds INTEGER DEFAULT 0, is_admin INTEGER DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs (
            day TEXT, ok INTEGER, seconds INTEGER, work_seconds INTEGER, device TEXT)""")
        # откуда приходят новые люди: ссылки t.me/бот?start=метка — только счётчики, без привязки к человеку
        c.execute("CREATE TABLE IF NOT EXISTS sources (src TEXT PRIMARY KEY, users INTEGER DEFAULT 0)")


def count_source(uid: int, src: str) -> None:
    src = "".join(ch for ch in src.lower() if ch.isalnum() or ch in "_-")[:32] or "direct"
    with db() as c:
        if c.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
            return                                   # считаем только новых
        c.execute("INSERT INTO sources(src, users) VALUES (?, 1) "
                  "ON CONFLICT(src) DO UPDATE SET users=users+1", (src,))


def touch_user(uid: int) -> None:
    with db() as c:
        c.execute("INSERT OR IGNORE INTO users(id) VALUES (?)", (uid,))


def is_admin(uid: int) -> bool:
    with db() as c:
        r = c.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    return bool(r and r[0])


def record(uid: int, ok: bool, seconds: float, work: float) -> None:
    with db() as c:
        c.execute("INSERT INTO jobs VALUES (date('now','localtime'), ?, ?, ?, ?)",
                  (int(ok), int(seconds), int(work), transcribe.device()))
        if ok:
            c.execute("UPDATE users SET jobs=jobs+1, seconds=seconds+? WHERE id=?", (int(seconds), uid))


# ---------- очередь ----------

@dataclass
class Job:
    uid: int
    chat_id: int
    file_id: str
    name: str
    seconds: float
    status: Message
    lang: str = "ru"                  # язык интерфейса пользователя
    mode: str = "notes"               # notes — конспект и статья, text — только дословная расшифровка
    cancelled: bool = False
    started: float = field(default_factory=time.time)


queue: asyncio.Queue[Job] = asyncio.Queue()
pending: list[Job] = []          # порядок очереди (для «вы №N»)
active: dict[int, Job] = {}      # у каждого пользователя не больше одной записи сразу
# запись прислана, но режим ещё не выбран: uid → (file_id, имя, длительность, id сообщения с кнопками)
choices: dict[int, tuple[str, str, float, int]] = {}


BOT_USERNAME = ""


def lang_of(m: Message) -> str:
    return ui_lang(m.from_user.language_code if m.from_user else None)


def share_kb(lang: str) -> InlineKeyboardMarkup:
    t = T[lang]
    link = f"https://t.me/{BOT_USERNAME}?start=share"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=t["share_btn"], url=f"https://t.me/share/url?url={quote(link)}&text={quote(t['share_text'])}")]])


def fmt_min(seconds: float, lang: str = "ru") -> str:
    t = T[lang]
    m = max(1, round(seconds / 60))
    return f"{m} {t['min']}" if m < 60 else f"{m // 60} {t['h']} {m % 60:02d} {t['min']}"


def size_label(lang: str) -> str:
    t = T[lang]
    return f"{MAX_MB // 1000} {t['gb']}" if MAX_MB >= 1000 else f"{MAX_MB} {t['mb']}"


class Status:
    """Редактирует сообщение о ходе работы не чаще раза в 5 секунд."""

    def __init__(self, msg: Message):
        self.msg, self.last, self.text = msg, 0.0, ""

    async def set(self, text: str, force: bool = False) -> None:
        if text == self.text or (not force and time.time() - self.last < 5):
            return
        self.text, self.last = text, time.time()
        try:
            await self.msg.edit_text(text)
        except Exception:  # noqa: BLE001 — «message is not modified» и т.п.
            pass


async def fetch(bot: Bot, job: Job, tmp: str) -> tuple[str, bool]:
    """Путь к файлу; второй флаг — файл лежит в папке своего Bot API и его надо удалить."""
    f = await bot.get_file(job.file_id, request_timeout=3600)
    if BOT_API_URL and f.file_path and os.path.isabs(f.file_path) and os.path.exists(f.file_path):
        return f.file_path, True
    dest = os.path.join(tmp, "input")
    await bot.download_file(f.file_path, dest, timeout=3600)
    return dest, False


async def process(bot: Bot, job: Job) -> None:
    ui, t = job.lang, T[job.lang]
    st = Status(job.status)
    loop = asyncio.get_running_loop()
    src, own = None, False
    ok, seconds, t0 = False, job.seconds, time.time()
    with tempfile.TemporaryDirectory(prefix="lecture-") as tmp:
        try:
            await st.set(t["getting"], True)
            src, own = await fetch(bot, job, tmp)
            seconds = transcribe.media_seconds(src) or seconds
            if seconds > MAX_MINUTES * 60:
                await st.set(t["too_long_real"].format(max=MAX_MINUTES, len=fmt_min(seconds, ui)), True)
                return
            await st.set(t["preparing"].format(len=fmt_min(seconds, ui)), True)
            audio = await asyncio.to_thread(transcribe.decode, src)
            if own:                       # исходник больше не нужен — удаляем сразу
                os.remove(src)
                src = None
            if len(audio) < transcribe.SR * 3:
                await st.set(t["no_sound"], True)
                return
            seconds = len(audio) / transcribe.SR
            t_stt = time.time()

            def progress(frac: float) -> None:
                left = ""
                if frac > 0.03:
                    rest = (time.time() - t_stt) / frac * (1 - frac)
                    left = t["left"].format(t=fmt_min(rest, ui))
                asyncio.run_coroutine_threadsafe(st.set(t["progress"].format(p=int(frac * 100), left=left)), loop)

            await st.set(t["transcribing"].format(dev=t[transcribe.kind()]), True)
            text, doubt, spoken = await asyncio.to_thread(
                transcribe.transcribe, audio, progress, lambda: job.cancelled)
            del audio
            if job.mode == "text":
                if not text.strip():
                    await st.set(t["no_speech"], True)
                    return
                await send_transcript(bot, job, text, doubt)
                await st.set(t["text_done"].format(len=fmt_min(seconds, ui), work=fmt_min(time.time() - t0, ui)),
                             True)
                ok = True
                return
            if len(text) < 200:
                await st.set(t["little_text"], True)
                return
            lang = notes.lang_of(spoken)          # язык конспекта = язык записи

            async def step(key: str, **kw) -> None:
                if job.cancelled:
                    raise transcribe.Cancelled
                await st.set("🧠 " + t["steps"][key].format(**kw) + "…", True)

            summary, article = await notes.make(text, lang, step)
            title = render.title_of(summary)
            flagged = render.marked(summary, article)
            doubt = flagged + [w for w in doubt if w not in flagged]
            work = time.time() - t0
            await st.set(t["done"].format(len=fmt_min(seconds, ui), work=fmt_min(work, ui)), True)

            warn = WARN[lang]
            if doubt:
                warn += "\n\n" + T[lang]["doubt"] + ", ".join(doubt[:20])
            await bot.send_message(job.chat_id, warn)
            for part in render.split_html(render.to_html(summary)):
                await bot.send_message(job.chat_id, part)
            for i, part in enumerate(render.split_html(render.to_html(article))):
                await bot.send_message(job.chat_id, (f"<b>{T[lang]['article']}</b>\n\n" if i == 0 else "") + part)
            data = await asyncio.to_thread(render.make_docx, title, summary, article, text, doubt, BOT_USERNAME, lang)
            await bot.send_document(job.chat_id, BufferedInputFile(data, render.safe_filename(title) + ".docx"),
                                    caption=(T[lang]["docx_caption"] + "\n\n" + warn)[:1020])
            await bot.send_message(job.chat_id, t["share_ask"], reply_markup=share_kb(ui))
            ok = True
        except transcribe.Cancelled:
            await st.set(t["cancelled"], True)
        except Exception as e:  # noqa: BLE001
            log.exception("ошибка обработки у %s", job.uid)
            msg = str(e)
            if "file is too big" in msg.lower():
                msg = t["file_too_big"].format(max=MAX_MB)
            await st.set(t["failed"].format(err=msg[:200]), True)
        finally:
            if own and src and os.path.exists(src):
                os.remove(src)
            record(job.uid, ok, seconds, time.time() - t0)
            log.info("uid=%s ok=%s запись=%.0fс работа=%.0fс", job.uid, ok, seconds, time.time() - t0)


async def send_transcript(bot: Bot, job: Job, text: str, doubt: list[str]) -> None:
    """Режим «только расшифровка»: дословный текст в чат (если не слишком длинный) и файл Word."""
    t = T[job.lang]
    stem = os.path.splitext(job.name)[0]
    title = stem if stem not in ("voice", "video_note", "audio", "video", "file") else render.DOCX[job.lang]["transcript"]
    warn = t["text_warn"]
    if doubt:
        warn += "\n\n" + t["doubt"] + ", ".join(doubt[:20])
    await bot.send_message(job.chat_id, html.escape(warn))
    parts = render.split_html(html.escape(text))
    if len(parts) <= 3:
        for part in parts:
            await bot.send_message(job.chat_id, part)
    else:
        await bot.send_message(job.chat_id, t["text_long"])
    data = await asyncio.to_thread(render.make_transcript_docx, title, text, doubt, t["text_warn"],
                                   BOT_USERNAME, job.lang)
    await bot.send_document(job.chat_id, BufferedInputFile(data, render.safe_filename(title) + ".docx"),
                            caption=t["text_caption"])
    await bot.send_message(job.chat_id, t["share_ask"], reply_markup=share_kb(job.lang))


async def worker(bot: Bot) -> None:
    while True:
        job = await queue.get()
        if job in pending:
            pending.remove(job)
        try:
            if not job.cancelled:
                await process(bot, job)
        finally:
            active.pop(job.uid, None)
            queue.task_done()
            for i, other in enumerate(pending, 1):
                await Status(other.status).set(T[other.lang]["queued"].format(n=i), True)


# ---------- команды ----------

@dp.message(CommandStart())
async def cmd_start(m: Message, command: CommandObject) -> None:
    t = T[lang_of(m)]
    arg = command.args or ""
    if not arg.startswith("admin_"):
        count_source(m.from_user.id, arg)
    touch_user(m.from_user.id)
    if ADMIN_CODE and arg == f"admin_{ADMIN_CODE}":
        with db() as c:
            used = c.execute("SELECT 1 FROM users WHERE is_admin=1").fetchone()
            if not used:
                c.execute("UPDATE users SET is_admin=1 WHERE id=?", (m.from_user.id,))
                await m.answer(t["owner"])
                return
    await m.answer(t["hello"].format(max_min=MAX_MINUTES, max_mb=size_label(lang_of(m))))


@dp.message(Command("help"))
async def cmd_help(m: Message) -> None:
    await cmd_start(m, CommandObject(prefix="/", command="start"))


@dp.message(Command("privacy"))
async def cmd_privacy(m: Message) -> None:
    await m.answer(T[lang_of(m)]["privacy"])


@dp.message(Command("cancel"))
async def cmd_cancel(m: Message) -> None:
    t = T[lang_of(m)]
    job = active.get(m.from_user.id)
    if not job:
        await m.answer(t["nothing"])
        return
    job.cancelled = True
    await m.answer(t["stopping"])


@dp.message(Command("stats"))
async def cmd_stats(m: Message) -> None:
    if not is_admin(m.from_user.id):
        return
    with db() as c:
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        tot = c.execute("SELECT COUNT(*), COALESCE(SUM(seconds),0), COALESCE(SUM(1-ok),0) FROM jobs").fetchone()
        today = c.execute("SELECT COUNT(*), COALESCE(SUM(seconds),0) FROM jobs "
                          "WHERE day=date('now','localtime') AND ok=1").fetchone()
        speed = c.execute("SELECT COALESCE(SUM(work_seconds)*1.0/NULLIF(SUM(seconds),0),0) FROM jobs "
                          "WHERE ok=1 AND day>=date('now','-7 day')").fetchone()[0]
        src = c.execute("SELECT src, users FROM sources ORDER BY users DESC LIMIT 10").fetchall()
    src_text = "\n".join(f"  {s}: {n}" for s, n in src) or "  пока нет"
    await m.answer(f"📊 Пользователей: {users}\n"
                   f"Откуда пришли:\n{src_text}\n"
                   f"Записей всего: {tot[0]} ({fmt_min(tot[1])}), ошибок/отмен: {tot[2]}\n"
                   f"Сегодня: {today[0]} ({fmt_min(today[1])})\n"
                   f"Скорость за неделю: {speed:.2f} мин работы на 1 мин записи\n"
                   f"Расшифровка сейчас: {transcribe.device()}\nВ очереди: {len(pending)}")


def media_of(m: Message):
    """(file_id, имя, размер, длительность) или None."""
    if m.voice:
        return m.voice.file_id, "voice", m.voice.file_size, m.voice.duration
    if m.video_note:
        return m.video_note.file_id, "video_note", m.video_note.file_size, m.video_note.duration
    if m.audio:
        return m.audio.file_id, m.audio.file_name or "audio", m.audio.file_size, m.audio.duration
    if m.video:
        return m.video.file_id, m.video.file_name or "video", m.video.file_size, m.video.duration
    if m.document:
        d = m.document
        ext = os.path.splitext(d.file_name or "")[1].lower()
        mime = d.mime_type or ""
        if mime.startswith(("audio/", "video/")) or ext in MEDIA_EXT:
            return d.file_id, d.file_name or "file", d.file_size, 0
    return None


@dp.message(F.voice | F.audio | F.video | F.video_note | F.document)
async def on_media(m: Message) -> None:
    ui = lang_of(m)
    t = T[ui]
    touch_user(m.from_user.id)
    media = media_of(m)
    if not media:
        await m.answer(t["not_media"])
        return
    file_id, name, size, duration = media
    uid = m.from_user.id
    if uid in active:
        await m.answer(t["busy"])
        return
    if size and size > MAX_MB * 1024 * 1024:
        await m.answer(t["too_big"].format(size=size // 1024 // 1024, max=MAX_MB))
        return
    if duration and duration > MAX_MINUTES * 60:
        await m.answer(t["too_long"].format(max=MAX_MINUTES))
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["btn_notes"], callback_data="notes")],
                                               [InlineKeyboardButton(text=t["btn_text"], callback_data="text")]])
    ask = await m.reply(t["choose"], reply_markup=kb)
    choices[uid] = (file_id, name, duration or 0, ask.message_id)   # прежний невыбранный файл забываем


@dp.callback_query(F.data.in_({"notes", "text"}))
async def on_choice(q: CallbackQuery) -> None:
    ui = ui_lang(q.from_user.language_code)
    t = T[ui]
    uid = q.from_user.id
    ch = choices.get(uid)
    if not ch or not isinstance(q.message, Message) or ch[3] != q.message.message_id:
        await q.answer(t["expired"], show_alert=True)
        return
    if uid in active:
        await q.answer(t["busy"], show_alert=True)
        return
    del choices[uid]
    await q.answer()
    file_id, name, duration, _ = ch
    busy = len(active)          # у каждого не больше одной записи, так что это и работающая, и ждущие
    await q.message.edit_text(t["queued"].format(n=busy) if busy else t["accepted"])
    job = Job(uid, q.message.chat.id, file_id, name, duration, q.message, ui, q.data)
    active[uid] = job
    pending.append(job)
    await queue.put(job)


@dp.message()
async def other(m: Message) -> None:
    await m.answer(T[lang_of(m)]["other"])


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("Нет BOT_TOKEN в .env — запустите set_token.sh")
    init_db()
    await asyncio.to_thread(transcribe.load)
    session = AiohttpSession(api=TelegramAPIServer.from_base(BOT_API_URL, is_local=True)) if BOT_API_URL else None
    bot = Bot(BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    global BOT_USERNAME
    me = await bot.get_me()
    BOT_USERNAME = me.username
    log.info("бот @%s запущен; Bot API: %s; расшифровка: %s", me.username, BOT_API_URL or "облако (20 МБ)",
             transcribe.device())
    asyncio.create_task(worker(bot))
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
