import asyncio
import contextlib
import html
import logging
import os
import re
import shutil
import signal
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus, ChatType, ParseMode
from pyrogram.errors import FloodWait, MessageNotModified, RPCError, UserNotParticipant
from pyrogram.raw.functions.bots import SetBotInfo
from pyrogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
)

import youtube
from db import DB
from texts import CHOOSE_LANG, LANGS, t
from youtube import DownloadError

CHANNEL = "aliahmedbots"
OWNER_ID = int(os.environ.get("OWNER_ID") or 0)  # your Telegram id: only you can use /stats
# People must join this channel to use the bot (the bot must be an admin there). Empty turns it off.
MUST_JOIN = os.environ.get("MUST_JOIN", CHANNEL).lstrip("@")
MAX_LINKS = 3  # per message
MAX_BYTES = 2000 * 1024 * 1024  # Telegram's limit for bots is 2 GB
PARALLEL_DOWNLOADS = 2
RESTART_HOUR = 4  # restart daily at 04:00 so Docker installs the newest yt-dlp
TZ = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Baghdad"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "."))
TMP_DIR = DATA_DIR / "tmp"
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
PROGRESS_EVERY = 2.5  # seconds between progress bar updates; Telegram limits message edits
SEARCH_RESULTS = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("pyrogram").setLevel(logging.WARNING)
log = logging.getLogger("bot")

bot = Client(
    "youtube-bot",
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"],
    bot_token=os.environ["BOT_TOKEN"],
    parse_mode=ParseMode.HTML,
    workdir=str(DATA_DIR),
)
db = DB(str(DATA_DIR / "bot.db"))
slots = asyncio.Semaphore(PARALLEL_DOWNLOADS)
busy: set[int] = set()  # users with a download in progress
videos: dict[str, youtube.Video] = {}  # recently looked-up videos, so buttons don't look them up again


# ---------- helpers ----------

def user_lang(user):
    if user is None:
        return "en"
    return db.get_lang(user.id) or ("ar" if (user.language_code or "").startswith("ar") else "en")


def welcome_text(lang, user):
    return t(lang, "welcome", name=html.escape(user.first_name or ""), channel=CHANNEL)


def main_menu(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_group"), url=f"https://t.me/{bot.me.username}?startgroup=true")],
        [InlineKeyboardButton(t(lang, "btn_help"), callback_data="help"),
         InlineKeyboardButton(t(lang, "btn_lang"), callback_data="lang")],
        [InlineKeyboardButton(t(lang, "btn_channel"), url=f"https://t.me/{CHANNEL}")],
    ])


def lang_menu():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
        InlineKeyboardButton("🇮🇶 العربية", callback_data="lang:ar"),
    ]])


def back_menu(lang):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="home")]])


def fmt_size(size):
    if not size:
        return ""
    if size >= 1024 ** 3:
        return f"{size / 1024 ** 3:.1f} GB"
    return f"{max(size / 1024 ** 2, 0.1):.1f} MB" if size < 10 * 1024 ** 2 else f"{size // 1024 ** 2} MB"


def fmt_duration(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def quality_name(quality):
    return {2160: "4K", 1440: "2K"}.get(quality, f"{quality}p")


def picker(lang, video):
    """Buttons for each quality the video comes in, plus MP3."""
    buttons = []
    for choice in video.choices:
        if choice.size > MAX_BYTES:
            continue
        data = f"v:{video.id}:{choice.quality}:{choice.format}"
        if len(data.encode()) > 64:  # Telegram's limit; the bot will pick the format itself
            data = f"v:{video.id}:{choice.quality}:"
        size = fmt_size(choice.size)
        label = f"🎬 {quality_name(choice.quality)}" + (f" · {size}" if size else "")
        buttons.append(InlineKeyboardButton(label, callback_data=data))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    if video.audio_format and video.mp3_size <= MAX_BYTES:
        size = fmt_size(video.mp3_size)
        label = t(lang, "btn_mp3") + (f" · {size}" if size else "")
        rows.append([InlineKeyboardButton(label, callback_data=f"a:{video.id}:{video.audio_format}")])
    return InlineKeyboardMarkup(rows) if rows else None


def caption_for(video):
    url = f"https://youtu.be/{video.id}"
    return (f"🎬 <b>{html.escape(video.title)}</b>\n"
            f"👤 {html.escape(video.channel)}\n\n"
            f'🔗 <a href="{url}">YouTube</a> · 📥 @{bot.me.username}')


def safe_name(title, ext):
    name = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", title).strip()[:80] or "video"
    return f"{name}.{ext}"


# ---------- progress ----------

class Progress:
    """What the status message should show: a stage and how far along it is (0..1)."""

    def __init__(self):
        self.stage = "downloading"
        self.fraction = None  # None until we know

    def set(self, fraction):
        # Called from the download thread too; never go backwards.
        self.fraction = max(fraction, self.fraction or 0.0)

    def next_stage(self, stage):
        self.stage, self.fraction = stage, None

    def upload(self, current, total):
        if total:
            self.set(current / total)

    def text(self, lang):
        text = t(lang, self.stage)
        if self.fraction is None:
            return text
        filled = round(self.fraction * 10)
        bar = "▰" * filled + "▱" * (10 - filled)
        return text + "\n\n" + t(lang, "progress", bar=bar, percent=int(self.fraction * 100))


async def stop(task):
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def show_progress(status, progress, lang):
    """Keep the status message up to date until cancelled."""
    shown = progress.text(lang)
    while True:
        await asyncio.sleep(PROGRESS_EVERY)
        text = progress.text(lang)
        if text == shown:
            continue
        try:
            await status.edit_text(text)
            shown = text
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except RPCError:
            pass


# ---------- looking up and sending ----------

async def get_video(video_id):
    if video_id not in videos:
        if len(videos) > 500:
            videos.pop(next(iter(videos)))
        videos[video_id] = await youtube.look_up(f"https://www.youtube.com/watch?v={video_id}")
    return videos[video_id]


async def show_choices(message, url, lang):
    """Reply to a link with the video's picture, title and a button per quality."""
    if not youtube.video_id(url):
        return await message.reply(t(lang, "no_video"))
    status = await message.reply(t(lang, "looking"))
    try:
        video = await youtube.look_up(url)
        videos[video.id] = video
    except DownloadError as e:
        log.info("Couldn't look up %s: %s", url, e.args[0])
        return await status.edit_text(t(lang, e.args[0]))
    except Exception:
        log.exception("Failed to look up %s", url)
        return await status.edit_text(t(lang, "failed"))

    markup = picker(lang, video)
    if markup is None:
        return await status.edit_text(t(lang, "too_big"))
    caption = t(lang, "pick", title=html.escape(video.title), channel=html.escape(video.channel),
                duration=fmt_duration(video.duration))
    try:
        await message.reply_photo(video.thumbnail, caption=caption, reply_markup=markup)
    except RPCError:  # Telegram couldn't fetch the picture
        await message.reply(caption, reply_markup=markup, link_preview_options=NO_PREVIEW)
    await status.delete()


NUMBERS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")


def isolate(text):
    """Keep Arabic and English names from swapping places with the text around them."""
    return f"\u2068{text}\u2069"


def clean_title(title, limit=60):
    """Make search results easy to scan: no hashtags, no "| extra" parts, not too long."""
    title = re.sub(r"#\S+", "", title).strip() or title.replace("#", " ")  # all hashtags: keep the words
    for separator in ("||", "|", "｜"):
        first = title.split(separator)[0].strip()
        if separator in title and len(first) >= 8:
            title = first
            break
    title = " ".join(title.split()).strip(" -–—·") or "…"
    return title if len(title) <= limit else title[:limit - 1].rstrip() + "…"


async def search_songs(message, query, lang):
    """Reply with the top YouTube results: 🎵 sends the MP3, 🎬 shows the qualities."""
    query = " ".join(query.split())[:100]
    status = await message.reply(t(lang, "searching"))
    try:
        results = await youtube.search(query, SEARCH_RESULTS)
    except Exception:
        log.exception("Search failed for %r", query)
        return await status.edit_text(t(lang, "failed"))
    if not results:
        return await status.edit_text(t(lang, "no_results"))
    lines = []
    for number, result in zip(NUMBERS, results):
        channel = clean_title(result.channel, 30)
        lines.append(f"{number} <b>{isolate(html.escape(clean_title(result.title)))}</b>\n"
                     f"⏱ {fmt_duration(result.duration)} · {isolate(html.escape(channel))}")
    rows = [
        [InlineKeyboardButton(f"🎵 {n}", callback_data=f"a:{r.id}") for n, r in enumerate(results, 1)],
        [InlineKeyboardButton(f"🎬 {n}", callback_data=f"p:{r.id}") for n, r in enumerate(results, 1)],
    ]
    await status.edit_text(t(lang, "results", query=isolate(html.escape(query)), results="\n\n".join(lines)),
                           reply_markup=InlineKeyboardMarkup(rows), link_preview_options=NO_PREVIEW)


async def send_file(reply_to, kind, file, caption, video, progress=None):
    """Upload a downloaded youtube.File as a song or a video."""
    thumb = str(file.thumb) if file.thumb else None
    if kind == "audio":
        return await reply_to.reply_audio(
            str(file.path), caption=caption, title=video.title, performer=video.channel,
            duration=file.duration, thumb=thumb, file_name=safe_name(video.title, "mp3"), progress=progress)
    return await reply_to.reply_video(
        str(file.path), caption=caption, width=file.width, height=file.height, duration=file.duration,
        thumb=thumb, file_name=safe_name(video.title, "mp4"), supports_streaming=True, progress=progress)


async def deliver(reply_to, user_id, video_id, mp3, quality, spec, lang):
    """Download the chosen quality (or MP3) and send it as a reply to the menu."""
    key = f"yt:{video_id}:{'mp3' if mp3 else quality}"
    kind = "audio" if mp3 else "video"
    if cached := db.get_sent(key):
        try:
            if kind == "audio":
                await reply_to.reply_audio(cached["file_id"], caption=cached["caption"])
            else:
                await reply_to.reply_video(cached["file_id"], caption=cached["caption"])
            db.add_event(user_id, "mp3" if mp3 else "video")
            return
        except RPCError as e:
            log.warning("Cached %s couldn't be re-sent, downloading again: %s", key, e)

    progress = Progress()
    status = await reply_to.reply(progress.text(lang))
    updater = asyncio.create_task(show_progress(status, progress, lang))
    try:
        video = await get_video(video_id)
        if mp3 and not spec:
            spec = video.audio_format
        expected = video.audio_size if mp3 else next((c.size for c in video.choices if c.quality == quality), 0)
        async with slots:
            with tempfile.TemporaryDirectory(dir=TMP_DIR) as folder:
                file = await youtube.download(video, Path(folder), quality=quality, spec=spec, mp3=mp3,
                                              on_progress=progress.set, expected=expected)
                if file.path.stat().st_size > MAX_BYTES:
                    raise DownloadError("too_big")
                progress.next_stage("uploading")
                caption = caption_for(video)
                sent = await send_file(reply_to, kind, file, caption, video, progress.upload)
        await stop(updater)
        media = sent.audio if mp3 else sent.video
        if media:
            db.save_sent(key, {"file_id": media.file_id, "caption": caption})
        db.add_event(user_id, "mp3" if mp3 else "video")
        log.info("Sent %s (%s)", key, fmt_size(file.path.stat().st_size) if file.path.exists() else "?")
        await status.delete()
    except DownloadError as e:
        await stop(updater)
        log.info("Couldn't download %s: %s", key, e.args[0])
        await status.edit_text(t(lang, e.args[0]))
    except Exception:
        await stop(updater)
        log.exception("Failed on %s", key)
        await status.edit_text(t(lang, "failed"))


# ---------- who uses the bot (for /stats) ----------

def track(user, chat):
    if user and not user.is_bot:
        db.seen_user(user.id)
    if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
        db.seen_chat(chat.id, chat.type.name.lower(), chat.title)


# group=-1 runs before the other handlers and doesn't stop them.
@bot.on_message(group=-1)
async def track_message(_, message):
    track(message.from_user, message.chat)


@bot.on_callback_query(group=-1)
async def track_button(_, query):
    track(query.from_user, query.message.chat if query.message else None)


def stats_text(lang):
    s = db.stats()
    events = s.pop("events")
    total, day, week = (sum(v[i] for v in events.values()) for i in range(3))
    activity = t(lang, "stats_activity", total=total, day=day, week=week,
                 video=events.get("video", (0,))[0], mp3=events.get("mp3", (0,))[0])
    since = datetime.fromtimestamp(s.pop("since"), TZ).strftime("%Y/%m/%d")
    return t(lang, "stats", bot=f"@{bot.me.username}", activity=activity, since=since, **s)


# ---------- people must join the channel ----------

MEMBER_CACHE = 600  # seconds to trust a "yes, they joined" before asking Telegram again
members: dict[int, float] = {}  # user id -> when we last saw them in the channel


async def has_joined(user):
    """True if `user` is in MUST_JOIN. Needs the bot to be an admin in that channel."""
    if not MUST_JOIN or user is None or user.id == OWNER_ID:
        return True
    if time.time() - members.get(user.id, 0) < MEMBER_CACHE:
        return True
    try:
        member = await bot.get_chat_member(MUST_JOIN, user.id)
    except UserNotParticipant:
        return False
    except RPCError as e:
        # Most likely the bot isn't an admin in the channel yet. Don't lock everyone out.
        log.warning("Couldn't check if %s joined @%s (is the bot an admin there?): %s", user.id, MUST_JOIN, e)
        return True
    if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
        return False
    if member.status == ChatMemberStatus.RESTRICTED and not member.is_member:
        return False
    members[user.id] = time.time()
    return True


def join_menu(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "btn_join"), url=f"https://t.me/{MUST_JOIN}")],
        [InlineKeyboardButton(t(lang, "btn_joined"), callback_data="joined")],
    ])


async def ask_to_join(message, lang):
    await message.reply(t(lang, "must_join", channel=MUST_JOIN), reply_markup=join_menu(lang),
                        link_preview_options=NO_PREVIEW)


async def joined_button(query, lang):
    """The "I joined" button: check again, then carry on with what they asked for."""
    if not await has_joined(query.from_user):
        return await query.answer(t(lang, "not_joined", channel=MUST_JOIN), show_alert=True)
    await query.answer(t(lang, "joined_ok"))
    prompt = query.message
    original = None
    if prompt and prompt.reply_to_message_id:
        try:
            original = await bot.get_messages(prompt.chat.id, prompt.reply_to_message_id)
        except RPCError:
            pass
    try:
        await prompt.delete()
    except RPCError:
        pass
    if original and not original.empty and original.from_user and original.from_user.id == query.from_user.id:
        await resume(original)


# ---------- commands ----------

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(_, message):
    lang = user_lang(message.from_user)
    if db.get_lang(message.from_user.id) is None:
        return await message.reply(CHOOSE_LANG, reply_markup=lang_menu())
    await message.reply(welcome_text(lang, message.from_user), reply_markup=main_menu(lang),
                        link_preview_options=NO_PREVIEW)


@bot.on_message(filters.command("help"))
async def help_cmd(_, message):
    lang = user_lang(message.from_user)
    markup = back_menu(lang) if message.chat.type == ChatType.PRIVATE else None
    await message.reply(t(lang, "help"), reply_markup=markup, link_preview_options=NO_PREVIEW)


@bot.on_message(filters.command("lang"))
async def lang_cmd(_, message):
    await message.reply(CHOOSE_LANG, reply_markup=lang_menu())


@bot.on_message(filters.command("stats") & filters.user(OWNER_ID))
async def stats_cmd(_, message):
    await message.reply(stats_text(user_lang(message.from_user)))


# Any message with a YouTube link: in private, with /dl in groups, or any
# group message if privacy mode is turned off in @BotFather.
has_link = filters.create(lambda _, __, m: bool(youtube.find_urls(m.text or m.caption)))


@bot.on_message(has_link & ~filters.via_bot)
async def link_message(_, message):
    lang = user_lang(message.from_user)
    if not await has_joined(message.from_user):
        return await ask_to_join(message, lang)
    for url in youtube.find_urls(message.text or message.caption)[:MAX_LINKS]:
        await show_choices(message, url, lang)


@bot.on_message(filters.command("song"))
async def song_cmd(_, message):
    lang = user_lang(message.from_user)
    args = (message.text or "").split(None, 1)
    if len(args) < 2:
        return await message.reply(t(lang, "song_usage"))
    if not await has_joined(message.from_user):
        return await ask_to_join(message, lang)
    await search_songs(message, args[1], lang)


# In private, any other text is a song (or video) to search for.
@bot.on_message(filters.private & filters.text & ~filters.via_bot & ~filters.regex(r"^/"))
async def private_search(_, message):
    lang = user_lang(message.from_user)
    if not await has_joined(message.from_user):
        return await ask_to_join(message, lang)
    await search_songs(message, message.text, lang)


async def resume(message):
    """Run a message again after its sender joined the channel."""
    text = message.text or message.caption or ""
    if youtube.find_urls(text):
        await link_message(bot, message)
    elif text.startswith("/"):
        await song_cmd(bot, message)
    else:
        await private_search(bot, message)


@bot.on_message(filters.command("dl"))
async def dl_without_link(_, message):
    await message.reply(t(user_lang(message.from_user), "send_link"))


@bot.on_message(filters.private & ~filters.via_bot & ~filters.service)
async def anything_else(_, message):
    await message.reply(t(user_lang(message.from_user), "send_link"))


# ---------- buttons ----------

async def choice_button(query, lang):
    """A quality or MP3 button under a video: v:<id>:<quality>:<formats> or a:<id>:<format>."""
    parts = query.data.split(":", 3)
    mp3 = parts[0] == "a"
    video_id = parts[1]
    quality = None if mp3 else int(parts[2])
    spec = (parts[2] if mp3 else parts[3]) if len(parts) > (2 if mp3 else 3) else ""
    if not await has_joined(query.from_user):
        return await query.answer(t(lang, "not_joined", channel=MUST_JOIN), show_alert=True)
    user = query.from_user.id
    if user in busy:
        return await query.answer(t(lang, "busy"), show_alert=True)
    await query.answer()
    busy.add(user)
    try:
        await deliver(query.message, user, video_id, mp3, quality, spec or None, lang)
    finally:
        busy.discard(user)


@bot.on_callback_query()
async def buttons(_, query):
    data = query.data or ""
    lang = user_lang(query.from_user)
    if data == "joined":
        return await joined_button(query, lang)
    if data.startswith(("v:", "a:")):
        return await choice_button(query, lang)
    if data.startswith("p:"):  # 🎬 on a search result: show its qualities
        if not await has_joined(query.from_user):
            return await query.answer(t(lang, "not_joined", channel=MUST_JOIN), show_alert=True)
        await query.answer()
        return await show_choices(query.message, f"https://youtu.be/{data[2:]}", lang)
    toast = None
    if data.startswith("lang:"):
        lang = data.split(":", 1)[1]
        if lang not in LANGS:
            return await query.answer()
        db.set_lang(query.from_user.id, lang)
        toast = t(lang, "lang_set")
        if query.message.chat.type == ChatType.PRIVATE:
            text, markup = welcome_text(lang, query.from_user), main_menu(lang)
        else:
            text, markup = toast, None
    elif data == "lang":
        text, markup = CHOOSE_LANG, lang_menu()
    elif data == "help":
        text, markup = t(lang, "help"), back_menu(lang)
    elif data == "home":
        text, markup = welcome_text(lang, query.from_user), main_menu(lang)
    else:
        return await query.answer()
    try:
        await query.edit_message_text(text, reply_markup=markup, link_preview_options=NO_PREVIEW)
    except MessageNotModified:
        pass
    await query.answer(toast)


# ---------- startup ----------

async def setup_profile():
    for lang in LANGS:
        code = "" if lang == "ar" else lang  # Arabic for everyone, English for English apps
        private = [BotCommand(c, t(lang, f"cmd_{c}")) for c in ("start", "song", "help", "lang")]
        groups = [BotCommand(c, t(lang, f"cmd_{c}")) for c in ("dl", "song", "help", "lang")]
        await bot.set_bot_commands(private, scope=BotCommandScopeAllPrivateChats(), language_code=code)
        await bot.set_bot_commands(groups, scope=BotCommandScopeAllGroupChats(), language_code=code)
        if OWNER_ID:
            try:  # your own menu also shows /stats
                await bot.set_bot_commands(private + [BotCommand("stats", t(lang, "cmd_stats"))],
                                           scope=BotCommandScopeChat(OWNER_ID), language_code=code)
            except RPCError as e:
                log.warning("Couldn't set your /stats menu (send /start to the bot first): %s", e)
        await bot.invoke(SetBotInfo(
            lang_code=code,
            about=t(lang, "bot_about", channel=CHANNEL),
            description=t(lang, "bot_description", channel=CHANNEL),
        ))


async def daily_restart():
    """Exit once a day when idle; Docker starts the bot again with the newest yt-dlp."""
    while True:
        now = datetime.now(TZ)
        target = now.replace(hour=RESTART_HOUR, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        while busy:
            await asyncio.sleep(30)
        log.info("Daily restart to update yt-dlp")
        os.kill(os.getpid(), signal.SIGINT)


async def main():
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    await bot.start()
    try:
        await setup_profile()
    except RPCError as e:
        log.warning("Couldn't set up the bot profile: %s", e)
    restart = asyncio.create_task(daily_restart()) if os.environ.get("DAILY_RESTART") else None
    log.info("@%s is running", bot.me.username)
    await idle()
    if restart:
        restart.cancel()
    await bot.stop()


bot.loop.run_until_complete(main())
