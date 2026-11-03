"""Every message the bot sends, in English and Arabic.

Words in {braces} are filled in by the code, so keep them as they are.
"""

LANGS = ("en", "ar")

CHOOSE_LANG = "🌐 <b>Please choose your language</b>\n🌐 <b>الرجاء اختيار لغتك</b>"

TEXTS = {
    "en": {
        "welcome": (
            "👋 Hey <b>{name}</b>!\n\n"
            "Send me a <b>YouTube</b> link, pick the quality you want, and I'll send you the video 🎬\n\n"
            "✅ Every quality from 144p up to 4K\n"
            "✅ MP3 to save just the sound 🎵\n"
            "✅ Videos and Shorts\n\n"
            "Just paste a link here 👇\n\n"
            "📣 News: @{channel}"
        ),
        "help": (
            "ℹ️ <b>Help</b>\n\n"
            "<b>Here:</b> paste a YouTube link, then tap the quality you want or 🎵 MP3.\n\n"
            "<b>In groups:</b> add me, then send <code>/dl</code> followed by the link:\n"
            "<code>/dl https://youtu.be/abc123</code>\n\n"
            "<b>Good to know</b>\n"
            "• Telegram allows files up to 2 GB, so very long videos only show the smaller qualities.\n"
            "• Live streams, private and age-restricted videos aren't supported."
        ),
        "send_link": "📎 Send me a YouTube link.",
        "no_video": "🤷 That link isn't a video. Send a link to a YouTube video or Short.",
        "looking": "🔎 Looking up the video…",
        "pick": (
            "🎬 <b>{title}</b>\n"
            "👤 {channel} · ⏱ {duration}\n\n"
            "Choose a quality 👇"
        ),
        "downloading": "⏳ Downloading…",
        "uploading": "📤 Sending…",
        "progress": "{bar}  {percent}%",
        "busy": "⏳ Wait a moment, I'm still sending your last download.",
        "unavailable": "🔒 This video is private, deleted, or not available.",
        "age_restricted": "🔞 YouTube only shows this video to signed-in adults, so I can't download it.",
        "live": "🔴 Live streams and premieres can't be downloaded. Try again after it ends.",
        "blocked": "🚧 YouTube is blocking me right now. Please try again in a while.",
        "too_big": "📦 This video is bigger than Telegram's 2 GB limit in every quality.",
        "failed": "😕 Something went wrong with this video. Please try again later.",
        "lang_set": "✅ Language set to English",
        "btn_group": "➕ Add me to a group",
        "btn_help": "❓ Help",
        "btn_lang": "🌐 Language",
        "btn_channel": "📣 Channel",
        "btn_back": "⬅️ Back",
        "btn_mp3": "🎵 MP3",
        "cmd_start": "Main menu",
        "cmd_help": "How to use the bot",
        "cmd_lang": "Change your language",
        "must_join": (
            "📣 <b>Join our channel first</b>\n\n"
            "To use this bot, please join @{channel}, then tap <b>✅ I joined</b>."
        ),
        "btn_join": "📣 Join the channel",
        "btn_joined": "✅ I joined",
        "not_joined": "You haven't joined @{channel} yet.",
        "joined_ok": "✅ Thanks for joining!",
        "cmd_stats": "Bot stats (only you see this)",
        "stats": (
            "📊 <b>{bot} stats</b>\n\n"
            "👥 Users: <b>{users:,}</b> (+{new_day:,} today · +{new_week:,} this week)\n"
            "🔥 Active: <b>{active_day:,}</b> today · <b>{active_week:,}</b> this week\n"
            "🌐 Arabic {ar:,} · English {en:,}\n"
            "💬 Groups {groups:,} · Channels {channels:,}\n\n"
            "{activity}\n\n"
            "<i>Counting since {since}. \"Today\" means the last 24 hours.</i>"
        ),
        "stats_activity": (
            "📥 Downloads: <b>{total:,}</b> (+{day:,} today · +{week:,} this week)\n"
            "Videos {video:,} · MP3 {mp3:,}"
        ),
        "cmd_dl": "Download a YouTube link",
        "bot_about": "Download YouTube videos in any quality up to 4K, or as MP3. By @{channel}",
        "bot_description": (
            "🎬 Download YouTube videos in the quality you choose.\n\n"
            "✅ From 144p up to 4K\n"
            "✅ MP3 to save just the sound\n"
            "✅ Videos and Shorts\n\n"
            "Just send a link.\n\n"
            "📣 News: @{channel}"
        ),
    },
    "ar": {
        "welcome": (
            "👋 أهلاً <b>{name}</b>!\n\n"
            "أرسل لي رابط <b>يوتيوب</b>، اختر الجودة اللي تريدها، وأرسل لك الفيديو 🎬\n\n"
            "✅ كل الجودات من 144p إلى 4K\n"
            "✅ MP3 لحفظ الصوت فقط 🎵\n"
            "✅ الفيديوهات والشورتس\n\n"
            "فقط الصق الرابط هنا 👇\n\n"
            "📣 الأخبار: @{channel}"
        ),
        "help": (
            "ℹ️ <b>المساعدة</b>\n\n"
            "<b>هنا:</b> الصق رابط يوتيوب، ثم اضغط على الجودة اللي تريدها أو 🎵 MP3.\n\n"
            "<b>في المجموعات:</b> أضفني، ثم أرسل <code>/dl</code> وبعده الرابط:\n"
            "<code>/dl https://youtu.be/abc123</code>\n\n"
            "<b>معلومات مفيدة</b>\n"
            "• تيليجرام يسمح بملفات حتى 2 جيجابايت، لذلك الفيديوهات الطويلة جداً تظهر بالجودات الأصغر فقط.\n"
            "• البث المباشر والفيديوهات الخاصة والمقيدة بالعمر غير مدعومة."
        ),
        "send_link": "📎 أرسل لي رابط يوتيوب.",
        "no_video": "🤷 هذا الرابط ليس فيديو. أرسل رابط فيديو أو شورت من يوتيوب.",
        "looking": "🔎 جارٍ البحث عن الفيديو…",
        "pick": (
            "🎬 <b>{title}</b>\n"
            "👤 {channel} · ⏱ {duration}\n\n"
            "اختر الجودة 👇"
        ),
        "downloading": "⏳ جارٍ التحميل…",
        "uploading": "📤 جارٍ الإرسال…",
        "progress": "{bar}  {percent}%",
        "busy": "⏳ لحظة، ما زلت أرسل تحميلك السابق.",
        "unavailable": "🔒 هذا الفيديو خاص أو محذوف أو غير متاح.",
        "age_restricted": "🔞 يوتيوب يعرض هذا الفيديو للبالغين المسجلين فقط، لذلك لا أستطيع تحميله.",
        "live": "🔴 لا يمكن تحميل البث المباشر أو العرض الأول. حاول بعد انتهائه.",
        "blocked": "🚧 يوتيوب يحظرني حالياً. حاول مرة أخرى بعد قليل.",
        "too_big": "📦 هذا الفيديو أكبر من حد تيليجرام (2 جيجابايت) بكل الجودات.",
        "failed": "😕 حدث خطأ مع هذا الفيديو. حاول مرة أخرى لاحقاً.",
        "lang_set": "✅ تم اختيار اللغة العربية",
        "btn_group": "➕ أضفني إلى مجموعة",
        "btn_help": "❓ المساعدة",
        "btn_lang": "🌐 اللغة",
        "btn_channel": "📣 القناة",
        "btn_back": "⬅️ رجوع",
        "btn_mp3": "🎵 MP3",
        "cmd_start": "القائمة الرئيسية",
        "cmd_help": "طريقة استخدام البوت",
        "cmd_lang": "تغيير اللغة",
        "must_join": (
            "📣 <b>اشترك بالقناة أولاً</b>\n\n"
            "حتى تستخدم البوت، اشترك في @{channel} ثم اضغط <b>✅ اشتركت</b>."
        ),
        "btn_join": "📣 اشترك بالقناة",
        "btn_joined": "✅ اشتركت",
        "not_joined": "لم تشترك في @{channel} بعد.",
        "joined_ok": "✅ شكراً لاشتراكك!",
        "cmd_stats": "إحصائيات البوت (تظهر لك فقط)",
        "stats": (
            "📊 <b>إحصائيات {bot}</b>\n\n"
            "👥 المستخدمون: <b>{users:,}</b> (+{new_day:,} اليوم · +{new_week:,} هذا الأسبوع)\n"
            "🔥 النشطون: <b>{active_day:,}</b> اليوم · <b>{active_week:,}</b> هذا الأسبوع\n"
            "🌐 العربية {ar:,} · الإنجليزية {en:,}\n"
            "💬 المجموعات {groups:,} · القنوات {channels:,}\n\n"
            "{activity}\n\n"
            "<i>العدّ بدأ في {since}. \"اليوم\" يعني آخر 24 ساعة.</i>"
        ),
        "stats_activity": (
            "📥 التحميلات: <b>{total:,}</b> (+{day:,} اليوم · +{week:,} هذا الأسبوع)\n"
            "فيديو {video:,} · MP3 {mp3:,}"
        ),
        "cmd_dl": "تحميل رابط يوتيوب",
        "bot_about": "حمّل فيديوهات يوتيوب بأي جودة حتى 4K، أو كـ MP3. من @{channel}",
        "bot_description": (
            "🎬 حمّل فيديوهات يوتيوب بالجودة اللي تختارها.\n\n"
            "✅ من 144p إلى 4K\n"
            "✅ MP3 لحفظ الصوت فقط\n"
            "✅ الفيديوهات والشورتس\n\n"
            "فقط أرسل الرابط.\n\n"
            "📣 الأخبار: @{channel}"
        ),
    },
}

RLM = "‏"  # invisible right-to-left mark


def t(lang, key, **values):
    text = TEXTS.get(lang, TEXTS["en"])[key]
    text = text.format(**values) if values else text
    if lang == "ar":
        # Telegram decides each line's direction from its first letter, so a line that
        # starts with an emoji or @username can jump to the left. This keeps it right.
        text = "\n".join(RLM + line if line else line for line in text.split("\n"))
    return text
