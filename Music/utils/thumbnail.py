import os
import requests
from io import BytesIO
from PIL import Image
from youtubesearchpython import VideosSearch


def _extract_video_id(link: str) -> str:
    link = str(link).strip()

    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    if "youtu.be/" in link:
        return link.split("youtu.be/")[-1].split("?")[0]

    return link  # raw ID fallback


def _get_best_thumbnail_url(video_id: str) -> str:
    """Try multiple resolutions until a valid thumbnail is found."""

    # Order of YouTube thumbnail fallbacks
    candidates = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hq720.jpg",
        f"https://i.ytimg.com/vi/{video_id}/sddefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/default.jpg",
    ]

    for url in candidates:
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            return url

    raise Exception("No valid thumbnail found")


def _download_thumbnail(video: str) -> str:
    video = str(video).strip()

    # Search query support
    if (
        "youtube.com" not in video
        and "youtu.be" not in video
        and len(video) != 11
        and not video.isnumeric()
    ):
        data = VideosSearch(video, limit=1).result().get("result", [])
        if not data:
            raise Exception("No search results found.")
        video_id = data[0]["id"]
    else:
        video_id = _extract_video_id(video)

    # Get working thumbnail
    url = _get_best_thumbnail_url(video_id)
    r = requests.get(url, stream=True)

    img = Image.open(BytesIO(r.content)).convert("RGB")

    # Save output
    os.makedirs("cache", exist_ok=True)
    path = f"cache/thumb-{video_id}.jpg"
    img.save(path, "JPEG")

    return path


class thumb:
    @staticmethod
    def generate(video: str, *args, **kwargs) -> str:
        """Compatible wrapper"""
        try:
            return _download_thumbnail(video)
        except Exception as e:
            print("Thumbnail Error:", e)
            return None
    # Fallback → HQ thumbnail
    if r.status_code != 200:
        url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        r = requests.get(url, stream=True)

    img = Image.open(BytesIO(r.content)).convert("RGB")

    os.makedirs("cache", exist_ok=True)
    path = f"cache/thumb-{video_id}.jpg"
    img.save(path, "JPEG")

    return path


class thumb:
    @staticmethod
    def generate(video: str, *args, **kwargs) -> str:
        """Bot-compatible wrapper: thumb.generate(video_id)"""
        try:
            return _download_thumbnail(video)
        except Exception as e:
            print("Thumbnail Error:", e)
            return None
