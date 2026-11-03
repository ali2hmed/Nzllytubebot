"""Looking up YouTube videos and downloading them in the quality people pick, or as MP3."""

import asyncio
import json
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yt_dlp

URL_RE = re.compile(r"https?://(?:[\w-]+\.)*(?:youtube\.com|youtu\.be)/[^\s<>\"']+", re.I)
ID_RE = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/live/|/embed/)([\w-]{11})")
QUALITIES = (144, 240, 360, 480, 720, 1080, 1440, 2160)
MP3_KBPS = 192
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
BASE_OPTIONS = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "noplaylist": True,
    "socket_timeout": 30,
    "retries": 3,
}


class DownloadError(Exception):
    """args[0] is the texts.py key of the message to show the user."""


@dataclass
class Choice:
    quality: int  # 1080 for 1080p; the short side, so vertical Shorts get the same names
    format: str  # yt-dlp format ids, e.g. "137+140"
    size: int  # estimated bytes


@dataclass
class Video:
    id: str
    title: str
    channel: str
    duration: int
    thumbnail: str
    choices: list[Choice] = field(default_factory=list)
    audio_size: int = 0
    audio_format: str = ""  # the track used for MP3 and added to video-only formats

    @property
    def mp3_size(self):
        return self.duration * MP3_KBPS * 125 or self.audio_size


@dataclass
class Result:
    """One search result."""
    id: str
    title: str
    channel: str
    duration: int


@dataclass
class File:
    path: Path
    width: int = 0
    height: int = 0
    duration: int = 0
    thumb: Path | None = None


def find_urls(text):
    return [m.group(0).rstrip(".,!?)") for m in URL_RE.finditer(text or "")]


def video_id(url):
    m = ID_RE.search(url)
    return m[1] if m else None


def _error_key(error):
    text = str(error).lower()
    if "not a bot" in text or "sign in to confirm" in text:
        return "blocked"
    if "age" in text and ("confirm" in text or "restricted" in text):
        return "age_restricted"
    if "live event" in text or "is live" in text or "premiere" in text:
        return "live"
    if any(w in text for w in ("private", "unavailable", "not available", "members", "removed", "terminated")):
        return "unavailable"
    return "failed"


def _size(f, duration):
    if size := f.get("filesize") or f.get("filesize_approx"):
        return int(size)
    return int((f.get("tbr") or 0) * 125 * (duration or 0))  # kbit/s -> bytes


def _quality(f):
    width, height = f.get("width") or 0, f.get("height") or 0
    return min(width, height) if width and height else height


def _video_rank(f, quality):
    codec = (f.get("vcodec") or "").lower()
    # H.264 plays everywhere, so prefer it up to 1080p (YouTube has nothing above in H.264).
    compatible = 3 if codec.startswith("avc1") else 2 if codec.startswith("vp") else 1
    direct = f.get("protocol") in ("https", "http")  # faster than m3u8 fragments
    normal_colors = f.get("dynamic_range") in (None, "SDR")  # HDR looks washed out in Telegram
    return (normal_colors, compatible, direct, f.get("fps") or 0, f.get("tbr") or 0)


def _audio_rank(f):
    return (
        "drc" not in (f.get("format_id") or ""),  # the normal track, not the volume-flattened one
        f.get("protocol") in ("https", "http"),
        f.get("ext") == "m4a",  # AAC fits in .mp4 with no re-encoding
        f.get("abr") or 0,
    )


def _look_up(url):
    with yt_dlp.YoutubeDL(BASE_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            raise DownloadError(_error_key(e))
    if info.get("live_status") in ("is_live", "is_upcoming", "post_live"):
        raise DownloadError("live")

    duration = int(info.get("duration") or 0)
    formats = info.get("formats") or []
    audios = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
    videos = [f for f in formats if f.get("vcodec") not in (None, "none") and _quality(f)]
    audio = max(audios, key=_audio_rank, default=None)

    video = Video(
        id=info["id"],
        title=info.get("title") or "",
        channel=info.get("channel") or info.get("uploader") or "",
        duration=duration,
        thumbnail=info.get("thumbnail") or f"https://i.ytimg.com/vi/{info['id']}/hqdefault.jpg",
        audio_size=_size(audio, duration) if audio else 0,
        audio_format=audio["format_id"] if audio else "",
    )
    for quality in QUALITIES:
        # Allow a little slack: some videos are 1072 or 718 pixels tall.
        matches = [f for f in videos if quality * 0.9 < _quality(f) <= quality]
        if not matches:
            continue
        best = max(matches, key=lambda f: _video_rank(f, quality))
        if best.get("acodec") not in (None, "none") or not audio:
            video.choices.append(Choice(quality, best["format_id"], _size(best, duration)))
        else:
            video.choices.append(Choice(quality, f'{best["format_id"]}+{audio["format_id"]}',
                                        _size(best, duration) + video.audio_size))
    if not video.choices and not audio:
        raise DownloadError("unavailable")
    return video


def _search(query, count):
    # extract_flat only reads the result list, so searching takes a second or two.
    with yt_dlp.YoutubeDL(dict(BASE_OPTIONS, extract_flat="in_playlist")) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch{count + 5}:{query}", download=False)
        except yt_dlp.utils.DownloadError as e:
            raise DownloadError(_error_key(e))
    results = []
    for entry in info.get("entries") or []:
        # No length means a live stream or something that isn't a normal video.
        if not entry.get("id") or not entry.get("duration") or entry.get("live_status") in ("is_live", "is_upcoming"):
            continue
        results.append(Result(entry["id"], " ".join((entry.get("title") or "").split()),
                              (entry.get("channel") or entry.get("uploader") or "").strip(), int(entry["duration"])))
        if len(results) == count:
            break
    return results


async def search(query, count=5):
    """The top `count` YouTube videos for `query`."""
    return await asyncio.to_thread(_search, query, count)


async def look_up(url):
    """Find a video's title and which qualities it comes in."""
    return await asyncio.to_thread(_look_up, url)


def _download(video_id, folder, spec, quality, mp3, on_progress, expected):
    done = {}  # file name -> bytes downloaded so far

    def hook(d):
        if d.get("status") not in ("downloading", "finished") or not on_progress:
            return
        done[d.get("filename")] = d.get("downloaded_bytes") or d.get("total_bytes") or 0
        total = max(expected, sum(done.values()), 1)
        on_progress(min(sum(done.values()) / total, 1.0))

    options = dict(BASE_OPTIONS, outtmpl=str(folder / "%(id)s.%(ext)s"), progress_hooks=[hook],
                   concurrent_fragment_downloads=4)
    if mp3:
        options.update(
            format=f"{spec}/ba/b" if spec else "ba/b",
            postprocessors=[
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": str(MP3_KBPS)},
                {"key": "FFmpegMetadata"},
            ],
        )
    else:
        # The exact formats from the menu, or the closest thing if YouTube changed them since.
        options.update(
            format="/".join(([spec] if spec else []) + [f"bv*[height<={quality}]+ba", f"b[height<={quality}]", "b"]),
            merge_output_format="mp4",
            postprocessor_args={"merger": ["-movflags", "+faststart"]},
        )
    with yt_dlp.YoutubeDL(options) as ydl:
        try:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        except yt_dlp.utils.DownloadError as e:
            raise DownloadError(_error_key(e))
    wanted = ".mp3" if mp3 else ".mp4"
    files = [p for p in folder.iterdir() if p.suffix == wanted]
    if not files:
        files = [p for p in folder.iterdir() if p.suffix in (".mp4", ".mkv", ".webm", ".mp3", ".m4a")]
    if not files:
        raise DownloadError("failed")
    return max(files, key=lambda p: p.stat().st_size)


async def _run(*command):
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    out, _ = await process.communicate()
    return out


async def _thumbnail(source, target):
    """A 320px JPEG for Telegram from a video file or an image URL."""
    if isinstance(source, str):  # a URL: fetch it first
        image = target.with_suffix(".src")
        try:
            request = urllib.request.Request(source, headers={"User-Agent": UA})
            data = await asyncio.to_thread(lambda: urllib.request.urlopen(request, timeout=20).read())
        except OSError:
            return None
        image.write_bytes(data)
        source = image
    await _run("ffmpeg", "-v", "error", "-y", "-i", str(source), "-frames:v", "1",
               "-vf", "scale=320:320:force_original_aspect_ratio=decrease", str(target))
    return target if target.exists() else None


async def download(video, folder, *, quality=None, spec=None, mp3=False, on_progress=None, expected=0):
    """Download one video (or its sound as MP3) into `folder`."""
    path = await asyncio.to_thread(_download, video.id, folder, spec, quality, mp3, on_progress, expected)
    file = File(path)
    out = await _run("ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path))
    data = json.loads(out or b"{}")
    stream = (data.get("streams") or [{}])[0]
    file.width, file.height = stream.get("width") or 0, stream.get("height") or 0
    file.duration = int(float((data.get("format") or {}).get("duration") or video.duration or 0))
    if mp3:
        file.thumb = await _thumbnail(video.thumbnail, folder / "cover.jpg")
    else:
        file.thumb = await _thumbnail(path, folder / "thumb.jpg")
    return file
