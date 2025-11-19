import os
import re
import time
import asyncio

import requests
import yt_dlp
import aiohttp
from lyricsgenius import Genius
from pyrogram.types import CallbackQuery
from youtubesearchpython.__future__ import VideosSearch

from config import Config
from Music.core.clients import hellbot
from Music.core.logger import LOGS
from Music.helpers.strings import TEXTS


# ==========================================
#  GLOBAL DOWNLOAD STATS (IN-MEMORY ONLY)
#  - Counts are reset on bot restart
# ==========================================
DOWNLOAD_STATS = {
    "audio_total": 0,
    "video_total": 0,
    "audio_success": 0,
    "video_success": 0,
    "audio_failed_ytdlp": 0,
    "video_failed_ytdlp": 0,
}


def format_download_stats() -> str:
    """
    Return a pretty table of download stats.
    """
    a_total = DOWNLOAD_STATS["audio_total"]
    v_total = DOWNLOAD_STATS["video_total"]
    a_success = DOWNLOAD_STATS["audio_success"]
    v_success = DOWNLOAD_STATS["video_success"]
    a_failed_ytdlp = DOWNLOAD_STATS["audio_failed_ytdlp"]
    v_failed_ytdlp = DOWNLOAD_STATS["video_failed_ytdlp"]

    total_requests = a_total + v_total
    total_success = a_success + v_success
    total_failed_ytdlp = a_failed_ytdlp + v_failed_ytdlp

    return (
        "**📊 Download Stats**\n\n"
        f"**Total Requests:** `{total_requests}`\n"
        f"**Total Success:** `{total_success}`\n"
        f"**Total Failed (YT-DLP):** `{total_failed_ytdlp}`\n\n"
        "`Type   | Total | ✅ | Yt ❌`\n"
        "`-------|-------|---------|----------`\n"
        f"`Audio | {a_total:^5} | {a_success:^7} | {a_failed_ytdlp:^12}`\n"
        f"`Video | {v_total:^5} | {v_success:^7} | {v_failed_ytdlp:^12}`\n\n"
        "Note: These counters reset when the bot restarts."
    )


def _extract_video_id(link: str) -> str:
    """
    Extract a YouTube video ID from various URL formats or return the raw ID.
    """
    link = link.strip()
    if ("http://" not in link) and ("https://" not in link) and ("/" not in link):
        return link
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    if "youtu.be/" in link:
        return link.split("youtu.be/")[-1].split("?")[0]
    return link.rsplit("/", 1)[-1]


async def download_song_api(link: str):
    """
    SAFE external API audio download.
    Always returns a file path OR None.
    """
    if not (Config.API_URL and Config.API_KEY):
        return None

    video_id = _extract_video_id(link)
    download_folder = "downloads"

    # Cache
    for ext in ("mp3", "m4a", "webm"):
        file_path = os.path.join(download_folder, f"{video_id}.{ext}")
        if os.path.exists(file_path):
            return file_path

    song_url = f"{Config.API_URL}/song/{video_id}?api={Config.API_KEY}"

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        data = None

        for _ in range(5):
            try:
                async with session.get(song_url) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    status = (data.get("status") or "").lower()

                    if status == "done":
                        if not data.get("link"):
                            return None
                        break

                    elif status == "downloading":
                        await asyncio.sleep(4)

                    else:
                        return None

            except Exception:
                return None

        else:
            return None

        # Download final file
        try:
            fmt = (data.get("format") or "mp3").lower()
            os.makedirs(download_folder, exist_ok=True)
            file_path = os.path.join(download_folder, f"{video_id}.{fmt}")

            async with session.get(data["link"]) as file_resp:
                with open(file_path, "wb") as f:
                    while True:
                        chunk = await file_resp.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)

            return file_path

        except Exception:
            return None


async def download_video_api(link: str):
    """
    SAFE external API video download.
    """
    if not (Config.VIDEO_API_URL and Config.API_KEY):
        return None

    video_id = _extract_video_id(link)
    download_folder = "downloads"

    # Cache
    for ext in ("mp4", "webm", "mkv"):
        file_path = os.path.join(download_folder, f"{video_id}.{ext}")
        if os.path.exists(file_path):
            return file_path

    video_url = f"{Config.VIDEO_API_URL}/video/{video_id}?api={Config.API_KEY}"

    timeout = aiohttp.ClientTimeout(total=45)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        data = None

        for _ in range(5):
            try:
                async with session.get(video_url) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    status = (data.get("status") or "").lower()

                    if status == "done":
                        if not data.get("link"):
                            return None
                        break

                    elif status == "downloading":
                        await asyncio.sleep(8)

                    else:
                        return None

            except Exception:
                return None

        else:
            return None

        try:
            fmt = (data.get("format") or "mp4").lower()
            os.makedirs(download_folder, exist_ok=True)
            file_path = os.path.join(download_folder, f"{video_id}.{fmt}")

            async with session.get(data["link"]) as file_resp:
                with open(file_path, "wb") as f:
                    while True:
                        chunk = await file_resp.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)

            return file_path

        except Exception:
            return None


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="
        self.regex = (
            r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|"
            r"embed\/|v\/|shorts\/)|youtu\.be\/|youtube\.com\/playlist\?list=)"
        )

        # VC yt-dlp options
        self.yt_opts_audio = {
            "format": "bestaudio/best",
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "geo_bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
        }

        self.yt_opts_video = {
            "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "geo_bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
        }

        # /song fallback options  
        self.audio_opts = {"format": "bestaudio[ext=m4a]"}
        self.video_opts = {
            "format": "best",
            "addmetadata": True,
            "key": "FFmpegMetadata",
            "prefer_ffmpeg": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
            "outtmpl": "%(id)s.mp4",
            "quiet": True,
        }

        # -----------------------------------------------
        # 🔥 FORCE COOKIES SUPPORT (cookies/cookies.txt)
        # -----------------------------------------------
        cookies_file = "cookies/cookies.txt"

        if os.path.exists(cookies_file):
            self.audio_opts["cookiefile"] = cookies_file
            self.video_opts["cookiefile"] = cookies_file

            self.yt_opts_audio["cookiefile"] = cookies_file
            self.yt_opts_video["cookiefile"] = cookies_file

            LOGS.info(f"[YTDLP] Using cookies from: {cookies_file}")
        else:
            LOGS.warning("[YTDLP] cookies/cookies.txt not found. Running without cookies.")

        # Lyrics
        self.lyrics = Config.LYRICS_API
        try:
            if self.lyrics:
                self.client = Genius(self.lyrics, remove_section_headers=True)
            else:
                self.client = None
        except Exception as e:
            LOGS.warning(f"[Lyrics API] {e}")
            self.client = None

    def check(self, link: str):
        return bool(re.match(self.regex, link))

    async def format_link(self, link: str, video_id: bool):
        link = link.strip()
        if video_id:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        return link

    async def get_data(self, link: str, video_id: bool, limit: int = 1) -> list:
        yt_url = await self.format_link(link, video_id)
        collection = []
        results = VideosSearch(yt_url, limit=limit)

        for result in (await results.next())["result"]:
            vid = result["id"]
            duration = result["duration"]
            thumbnail = f"https://i.ytimg.com/vi/{result['id']}/hqdefault.jpg"

            context = {
                "id": vid,
                "channel": result["channel"]["name"],
                "link": result["link"],
                "duration": duration,
                "title": result["title"],
                "views": result["viewCount"]["short"],
                "thumbnail": thumbnail,
                "published": result["publishedTime"],
            }
            collection.append(context)

        return collection[:limit]

    async def get_playlist(self, link: str) -> list:
        yt_url = await self.format_link(link, False)
        with yt_dlp.YoutubeDL({"extract_flat": True}) as ydl:
            results = ydl.extract_info(yt_url, False)
            playlist = [video["id"] for video in results["entries"]]
        return playlist

    async def download(self, link: str, video_id: bool, video: bool = False) -> str:
        """
        VC Streaming downloader.
        SAFE MODE:
            - Counts requests properly
            - Never returns None
            - Uses API → fallback to yt-dlp
            - Tracks YT-DLP failures accurately
        """
        yt_url = await self.format_link(link, video_id)
        media = "video" if video else "audio"
        DOWNLOAD_STATS[f"{media}_total"] += 1

        # Try API first (if available)
        api_path = None
        try:
            if video:
                api_path = await download_video_api(yt_url)
            else:
                api_path = await download_song_api(yt_url)
        except:
            api_path = None

        if api_path and os.path.exists(api_path):
            DOWNLOAD_STATS[f"{media}_success"] += 1
            return api_path

        # Fallback: YT-DLP
        try:
            if video:
                dlp = yt_dlp.YoutubeDL(self.yt_opts_video)
            else:
                dlp = yt_dlp.YoutubeDL(self.yt_opts_audio)

            info = dlp.extract_info(yt_url, download=False)
            path = os.path.join("downloads", f"{info['id']}.{info['ext']}")

            if not os.path.exists(path):
                dlp.download([yt_url])

            if not os.path.exists(path):
                DOWNLOAD_STATS[f"{media}_failed_ytdlp"] += 1
                raise Exception("YT-DLP failed to download file.")

            DOWNLOAD_STATS[f"{media}_success"] += 1
            return path

        except Exception as e:
            DOWNLOAD_STATS[f"{media}_failed_ytdlp"] += 1
            LOGS.error(f"[YT-DLP {media}] {e}")
            raise

    async def send_song(
        self, message: CallbackQuery, rand_key: str, key: int, video: bool = False
    ) -> None:
        """
        /song downloader (safe)
        Counts totals, successes, failures.
        """
        track = Config.SONG_CACHE[rand_key][key]
        hell = await message.message.reply_text("Downloading...")

        media = "video" if video else "audio"
        DOWNLOAD_STATS[f"{media}_total"] += 1

        link = track["link"]
        success = False
        output = None

        try:
            thumb = f"{track['id']}{time.time()}.jpg"
            _thumb = requests.get(track["thumbnail"], allow_redirects=True)
            open(thumb, "wb").write(_thumb.content)

            # Try API
            if video:
                output = await download_video_api(link)
            else:
                output = await download_song_api(link)

            if output and os.path.exists(output):
                success = True
            else:
                # Fallback YT-DLP
                if video:
                    dlp = yt_dlp.YoutubeDL(self.video_opts)
                else:
                    dlp = yt_dlp.YoutubeDL(self.audio_opts)

                yt_file = dlp.extract_info(link, download=True)

                if video:
                    output = f"{yt_file['id']}.mp4"
                else:
                    output = dlp.prepare_filename(yt_file)

                success = True

            # Send file
            if video:
                await message.message.reply_video(
                    video=output,
                    caption=TEXTS.SONG_CAPTION.format(
                        track["title"],
                        track["link"],
                        track["views"],
                        track["duration"],
                        message.from_user.mention,
                        hellbot.app.mention,
                    ),
                    thumb=thumb,
                    supports_streaming=True,
                )
            else:
                await message.message.reply_audio(
                    audio=output,
                    caption=TEXTS.SONG_CAPTION.format(
                        track["title"],
                        track["link"],
                        track["views"],
                        track["duration"],
                        message.from_user.mention,
                        hellbot.app.mention,
                    ),
                    performer=TEXTS.PERFORMER,
                    title=track["title"],
                    thumb=thumb,
                )

            DOWNLOAD_STATS[f"{media}_success"] += 1

            await hell.delete()

        except Exception as e:
            DOWNLOAD_STATS[f"{media}_failed_ytdlp"] += 1
            LOGS.error(f"[send_song {media}] {e}")

            try:
                await hell.edit_text(
                    "**❌ Failed to fetch tracks.**\n"
                    "__Forward this message to @ArcChatz for help.__"
                )
            except:
                pass

        finally:
            Config.SONG_CACHE.pop(rand_key, None)

            try:
                if "thumb" in locals() and os.path.exists(thumb):
                    os.remove(thumb)
                if output and os.path.exists(output):
                    os.remove(output)
            except:
                pass

    async def get_lyrics(self, song: str, artist: str) -> dict:
        if not self.client:
            return {}
        try:
            results = self.client.search_song(song, artist)
            if results:
                results.to_dict()
                return {
                    "title": results["full_title"],
                    "image": results["song_art_image_url"],
                    "lyrics": results["lyrics"],
                }
        except:
            return {}
        return {}


ytube = YouTube()
