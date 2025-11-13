import base64
import os
from io import BytesIO

import requests
from PIL import Image, ImageFont, ImageDraw, ImageEnhance, ImageFilter
from youtubesearchpython import VideosSearch


# -----------------------------
# Load Fonts (Your New Paths)
# -----------------------------
try:
    font = ImageFont.truetype("./resources/fonts/fmt.ttf", 40)
    bold_font = ImageFont.truetype("./resources/fonts/xcb.ttf", 50)
except IOError:
    raise RuntimeError(
        "Font loading failed — ensure files exist in ./resources/fonts/"
    )


def humanize(num: str) -> str:
    if num is None:
        return "Hidden"

    try:
        num = num.replace(",", "").split()[0]
        num = int(num)
    except:
        return num

    if num >= 1_000_000_000:
        return f"{round(num / 1_000_000_000, 1)}B"
    elif num >= 1_000_000:
        return f"{round(num / 1_000_000, 1)}M"
    elif num >= 1_000:
        return f"{round(num / 1_000, 1)}K"
    else:
        return str(num)


def generate(video_id: str, dark: bool = False) -> str:
    if "youtube.com" in video_id or "youtu.be" in video_id:
        # Extract clean ID
        if "v=" in video_id:
            video_id = video_id.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in video_id:
            video_id = video_id.split("youtu.be/")[-1].split("?")[0]

    # ----------------------
    # Fetch Video Metadata
    # ----------------------
    try:
        data = VideosSearch(video_id, limit=1).result()["result"][0]
        title = data["title"][:60]
        duration = data.get("duration", "Unknown")
        views_raw = data.get("viewCount", {}).get("short", "0")
        view_count = humanize(views_raw)
        published = data.get("publishedTime", "Unknown")
        thumbnail_url = f"https://i.ytimg.com/vi/{data['id']}/maxresdefault.jpg"
    except Exception:
        # Fallback
        title = "Unknown Title"
        duration = "Unknown"
        view_count = "0"
        published = "Unknown"
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

    # ----------------------
    # Load thumbnail image
    # ----------------------
    thumb_bytes = requests.get(thumbnail_url, allow_redirects=True).content
    thumb_img = Image.open(BytesIO(thumb_bytes)).convert("RGB")

    # Create base HD canvas
    base_image = thumb_img.resize((1280, 720))
    blurred_background = base_image.filter(ImageFilter.GaussianBlur(30))

    # Dark mode enhancement
    if dark:
        blurred_background = ImageEnhance.Brightness(blurred_background).enhance(0.4)

    # Place blurred BG
    base_image = blurred_background.copy()

    # --------------------------
    # FROSTED GLASS OVERLAY BOX
    --------------------------
    overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    glass = Image.new("RGBA", (700, 350), (255, 255, 255, 60))
    glass = glass.filter(ImageFilter.GaussianBlur(4))
    overlay.paste(glass, (700, 250), glass)

    base_image = Image.alpha_composite(base_image.convert("RGBA"), overlay)

    # --------------------------
    # Draw Text Information
    # --------------------------
    font_color = "white"
    draw = ImageDraw.Draw(base_image)

    draw.text((740, 300), f"Title: {title}", font=font, fill=font_color)
    draw.text((740, 370), f"Duration: {duration}", font=font, fill=font_color)
    draw.text((740, 440), f"Views: {view_count}", font=font, fill=font_color)
    draw.text((740, 510), f"Upload Date: {published}", font=font, fill=font_color)

    # --------------------------
    # TEAM ARC Watermark
    # --------------------------
    watermark_text = "Team Arc"
    watermark_font = ImageFont.truetype("./resources/fonts/xcb.ttf", 45)

    wm_w, wm_h = watermark_font.getsize(watermark_text)
    wm_x = base_image.width - wm_w - 50
    wm_y = base_image.height - wm_h - 50

    draw.text(
        (wm_x, wm_y),
        watermark_text,
        font=watermark_font,
        fill="white",
    )

    # --------------------------
    # Save Final Thumbnail
    # --------------------------
    output_path = f"cache/thumb-{video_id}.png"
    os.makedirs("cache", exist_ok=True)
    base_image.convert("RGB").save(output_path, "PNG")

    return output_path
