from pyrogram import filters
from Music.core.clients import hellbot
from Music.utils.youtube import format_download_stats
from config import Config  # or your sudo system

@hellbot.app.on_message(filters.command("dlstats") & Config.SUDO_USERS)
async def download_stats_cmd(_, message):
    """
    Show audio/video download success & failure counts.
    """
    text = format_download_stats()
    await message.reply_text(text)
