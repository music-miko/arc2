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

# Try to import external API config (optional)
try:
    from config import API_URL, VIDEO_API_URL, API_KEY
except ImportError:  # optional
    API_URL = "https://api.thequickearn.xyz"
    VIDEO_API_URL = "https://api.video.thequickearn.xyz"
    API_KEY = None

def _extract_video_id(link: str) -> str:
    """
    Extract a YouTube video ID from various URL formats or return the raw ID.
    Works with:
      - full URLs  -> https://www.youtube.com/watch?v=ID
      - short URLs -> https://youtu.be/ID
      - raw IDs    -> ID
    """
    link = link.strip()
    # If it's already a bare ID (no slash, no "?" and no scheme), just return
    if ("http://" not in link) and ("https://" not in link) and ("/" not in link):
        return link
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    if "youtu.be/" in link:
        return link.split("youtu.be/")[-1].split("?")[0]
    return link.rsplit("/", 1)[-1]


async def download_song_api(link: str):
    """
    Use the external SONG API (if configured) to download audio.
    Returns the local file path on success, or None on failure.
    """
    if not (API_URL and API_KEY):
        return None

    video_id = _extract_video_id(link)
    download_folder = "downloads"

    # Cache hit – reuse existing file
    for ext in ("mp3", "m4a", "webm"):
        file_path = os.path.join(download_folder, f"{video_id}.{ext}")
        if os.path.exists(file_path):
            return file_path

    song_url = f"{API_URL}/song/{video_id}?api={API_KEY}"

    async with aiohttp.ClientSession() as session:
        data = None
        for _ in range(10):
            try:
                async with session.get(song_url) as resp:
                    if resp.status != 200:
                        raise Exception(f"API request failed with status {resp.status}")
                    data = await resp.json()
                    status = (data.get("status") or "").lower()
                    if status == "done":
                        if not data.get("link"):
                            raise Exception("API did not return a download URL.")
                        break
                    elif status == "downloading":
                        await asyncio.sleep(4)
                    else:
                        err = data.get("error") or data.get("message") or status
                        raise Exception(f"API error: {err}")
            except Exception as e:
                LOGS.error(f"[Song API] {e}")
                return None
        else:
            LOGS.error("[Song API] Max retries reached.")
            return None

        try:
            file_format = (data.get("format") or "mp3").lower()
            os.makedirs(download_folder, exist_ok=True)
            file_path = os.path.join(download_folder, f"{video_id}.{file_format}")
            async with session.get(data["link"]) as file_resp:
                with open(file_path, "wb") as f:
                    while True:
                        chunk = await file_resp.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            return file_path
        except Exception as e:
            LOGS.error(f"[Song API Save] {e}")
            return None


async def download_video_api(link: str):
    """
    Use the external VIDEO API (if configured) to download video.
    Returns the local file path on success, or None on failure.
    """
    if not (VIDEO_API_URL and API_KEY):
        return None

    video_id = _extract_video_id(link)
    download_folder = "downloads"

    # Cache hit – reuse existing file
    for ext in ("mp4", "webm", "mkv"):
        file_path = os.path.join(download_folder, f"{video_id}.{ext}")
        if os.path.exists(file_path):
            return file_path

    video_url = f"{VIDEO_API_URL}/video/{video_id}?api={API_KEY}"

    async with aiohttp.ClientSession() as session:
        data = None
        for _ in range(10):
            try:
                async with session.get(video_url) as resp:
                    if resp.status != 200:
                        raise Exception(f"API request failed with status {resp.status}")
                    data = await resp.json()
                    status = (data.get("status") or "").lower()
                    if status == "done":
                        if not data.get("link"):
                            raise Exception("API did not return a download URL.")
                        break
                    elif status == "downloading":
                        await asyncio.sleep(8)
                    else:
                        err = data.get("error") or data.get("message") or status
                        raise Exception(f"API error: {err}")
            except Exception as e:
                LOGS.error(f"[Video API] {e}")
                return None
        else:
            LOGS.error("[Video API] Max retries reached.")
            return None

        try:
            file_format = (data.get("format") or "mp4").lower()
            os.makedirs(download_folder, exist_ok=True)
            file_path = os.path.join(download_folder, f"{video_id}.{file_format}")
            async with session.get(data["link"]) as file_resp:
                with open(file_path, "wb") as f:
                    while True:
                        chunk = await file_resp.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            return file_path
        except Exception as e:
            LOGS.error(f"[Video API Save] {e}")
            return None


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="
        self.regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|shorts\/)|youtu\.be\/|youtube\.com\/playlist\?list=)"
        self.audio_opts = {"format": "bestaudio[ext=m4a]"}
        self.video_opts = {
            "format": "best",
            "addmetadata": True,
            "key": "FFmpegMetadata",
            "prefer_ffmpeg": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "postprocessors": [
                {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
            ],
            "outtmpl": "%(id)s.mp4",
            "logtostderr": False,
            "quiet": True,
        }
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
        self.yt_playlist_opts = {
            "exctract_flat": True,
        }
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
            channel = result["channel"]["name"]
            channel_url = result["channel"]["link"]
            duration = result["duration"]
            published = result["publishedTime"]
            thumbnail = f"https://i.ytimg.com/vi/{result['id']}/hqdefault.jpg"
            title = result["title"]
            url = result["link"]
            views = result["viewCount"]["short"]
            context = {
                "id": vid,
                "ch_link": channel_url,
                "channel": channel,
                "duration": duration,
                "link": url,
                "published": published,
                "thumbnail": thumbnail,
                "title": title,
                "views": views,
            }
            collection.append(context)
        return collection[:limit]

    async def get_playlist(self, link: str) -> list:
        yt_url = await self.format_link(link, False)
        with yt_dlp.YoutubeDL(self.yt_playlist_opts) as ydl:
            results = ydl.extract_info(yt_url, False)
            playlist = [video["id"] for video in results["entries"]]
        return playlist

    async def download(self, link: str, video_id: bool, video: bool = False) -> str:
        """
        Used by the voice-chat player (Music.utils.play / Player.play).
        Tries the external API first; if that fails or is not configured,
        falls back to plain yt-dlp (old behaviour).
        """
        yt_url = await self.format_link(link, video_id)

        # 1) Try through external API (preferred: avoids YouTube anti-bot issues)
        api_path = None
        try:
            if video:
                api_path = await download_video_api(yt_url)
            else:
                api_path = await download_song_api(yt_url)
        except Exception as e:
            LOGS.error(f"[API download wrapper] {e}")
            api_path = None

        if api_path:
            return api_path

        # 2) Fallback: original yt-dlp logic (may hit "Sign in" if cookies not used)
        if video:
            dlp = yt_dlp.YoutubeDL(self.yt_opts_video)
        else:
            dlp = yt_dlp.YoutubeDL(self.yt_opts_audio)

        info = dlp.extract_info(yt_url, download=False)
        path = os.path.join("downloads", f"{info['id']}.{info['ext']}")
        if not os.path.exists(path):
            dlp.download([yt_url])
        return path

    async def send_song(
        self, message: CallbackQuery, rand_key: str, key: int, video: bool = False
    ) -> None:
        """
        Used by /song etc.
        Same idea: use API first, then yt-dlp as fallback.
        """
        track = Config.SONG_CACHE[rand_key][key]
        hell = await message.message.reply_text("Downloading...")
        await message.message.delete()
        output = None

        try:
            thumb = f"{track['id']}{time.time()}.jpg"
            _thumb = requests.get(track["thumbnail"], allow_redirects=True)
            open(thumb, "wb").write(_thumb.content)

            link = track["link"]

            if video:
                # API first
                output = await download_video_api(link)
                if output:
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
                    # fallback
                    with yt_dlp.YoutubeDL(self.video_opts) as ydl:
                        yt_file = ydl.extract_info(link, download=True)
                    output = f"{yt_file['id']}.mp4"
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
                        duration=int(yt_file["duration"]),
                        thumb=thumb,
                        supports_streaming=True,
                    )
            else:
                # AUDIO
                output = await download_song_api(link)
                if output:
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
                else:
                    with yt_dlp.YoutubeDL(self.audio_opts) as ydl:
                        yt_file = ydl.extract_info(link, download=False)
                        output = ydl.prepare_filename(yt_file)
                        ydl.process_info(yt_file)
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
                        duration=int(yt_file["duration"]),
                        performer=TEXTS.PERFORMER,
                        title=yt_file["title"],
                        thumb=thumb,
                    )

            chat = message.message.chat.title or message.message.chat.first_name
            await hellbot.logit(
                "Video" if video else "Audio",
                f"**⤷ User:** {message.from_user.mention} [`{message.from_user.id}`]\n"
                f"**⤷ Chat:** {chat} [`{message.message.chat.id}`]\n"
                f"**⤷ Link:** [{track['title']}]({track['link']})",
            )
            await hell.delete()
        except Exception as e:
            await hell.edit_text(f"**Error:**\n`{e}`")
        finally:
            try:
                Config.SONG_CACHE.pop(rand_key, None)
                if "thumb" in locals() and os.path.exists(thumb):
                    os.remove(thumb)
                if output and os.path.exists(output):
                    os.remove(output)
            except Exception:
                pass

    async def get_lyrics(self, song: str, artist: str) -> dict:
        context = {}
        if not self.client:
            return context
        results = self.client.search_song(song, artist)
        if results:
            results.to_dict()
            title = results["full_title"]
            image = results["song_art_image_url"]
            lyrics = results["lyrics"]
            context = {
                "title": title,
                "image": image,
                "lyrics": lyrics,
            }
        return context


ytube = YouTube()
