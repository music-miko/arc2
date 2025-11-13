import os
import requests
from io import BytesIO
from PIL import Image
from youtubesearchpython import VideosSearch


def get_video_id(link: str) -> str:
    """Extract YouTube video ID from any type of link."""
    link = link.strip()

    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    if "youtu.be/" in link:
        return link.split("youtu.be/")[-1].split("?")[0]

    # Direct ID fallback
    return link


def generate(video: str) -> str:
    """Download only YouTube thumbnail (no branding, no text, no editing)."""
    try:
        # If user passed keywords instead of URL
        if "www.youtube.com" not in video and "youtu.be" not in video:
            search = VideosSearch(video, limit=1).result()
            result = search.get("result", [])
            if not result:
                raise Exception("No results found.")
            video_id = result[0]["id"]
        else:
            video_id = get_video_id(video)

        # High-quality (maxres) thumbnail URL
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

        # Attempt downloading thumbnail
        response = requests.get(thumbnail_url, stream=True)

        # Some videos don't support maxresdefault → fallback to HQ thumbnail
        if response.status_code != 200:
            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            response = requests.get(thumbnail_url, stream=True)

        img = Image.open(BytesIO(response.content)).convert("RGB")

        # Save output
        os.makedirs("cache", exist_ok=True)
        output_path = f"cache/thumb-{video_id}.jpg"
        img.save(output_path, "JPEG")

        return output_path

    except Exception as e:
        print(f"Thumbnail error: {e}")
        return None
