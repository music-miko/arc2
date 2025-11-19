from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

class Config(object):
    # required config variables
    API_HASH = getenv("API_HASH", None)                # get from my.telegram.org
    API_ID = int(getenv("API_ID", 0))                  # get from my.telegram.org
    BOT_TOKEN = getenv("BOT_TOKEN", None)              # get from @BotFather
    DATABASE_URL = getenv("DATABASE_URL", None)        # from https://cloud.mongodb.com/
    LOGGER_ID = int(getenv("LOGGER_ID", ""))            # make a channel and get its ID
    OWNER_ID = getenv("OWNER_ID", "6848223695")                  # enter your id here
    API_URL = getenv("API_URL", 'https://api.thequickearn.xyz') #youtube song url
    VIDEO_API_URL = getenv("VIDEO_API_URL", 'https://api.video.thequickearn.xyz')
    API_KEY = getenv("API_KEY", None) # youtube song api key, generate free key or buy paid plan from panel.thequickearn.xyz

    
    # optional config variables
    BLACK_IMG = getenv("BLACK_IMG", "https://files.catbox.moe/jwc4b6.jpg")        # black image for progress
    BOT_NAME = getenv("BOT_NAME", "Arc Music")   # dont put fancy texts here.
    BOT_PIC = getenv("BOT_PIC", "https://files.catbox.moe/b64xz8.jpg")           # put direct link to image here
    LEADERBOARD_TIME = getenv("LEADERBOARD_TIME", "8:00")   # time in 24hr format for leaderboard broadcast
    LYRICS_API = getenv("LYRICS_API", "gIgMyTXuwJoY9VCPNwKdb_RUOA_9mCMmRlbrrdODmNvcpslww_2RIbbWOB8YdBW9")             # from https://docs.genius.com/
    MAX_FAVORITES = int(getenv("MAX_FAVORITES", 30))    # max number of favorite tracks
    PLAY_LIMIT = int(getenv("PLAY_LIMIT", 0))           # time in minutes. 0 for no limit
    PRIVATE_MODE = getenv("PRIVATE_MODE", "off")        # "on" or "off" to enable/disable private mode
    SONG_LIMIT = int(getenv("SONG_LIMIT", 0))           # time in minutes. 0 for no limit
    TELEGRAM_IMG = getenv("TELEGRAM_IMG", "https://files.catbox.moe/20hvch.jpg")         # put direct link to image here
    TG_AUDIO_SIZE_LIMIT = int(getenv("TG_AUDIO_SIZE_LIMIT", 104857600))     # size in bytes. 0 for no limit
    TG_VIDEO_SIZE_LIMIT = int(getenv("TG_VIDEO_SIZE_LIMIT", 1073741824))    # size in bytes. 0 for no limit
    TZ = getenv("TZ", "Asia/Kolkata")   # https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

    # String Sessions
    HELLBOT_SESSION = getenv("HELLBOT_SESSION", None)
    HELLBOT_SESSION2 = getenv("HELLBOT_SESSION2", None)
    HELLBOT_SESSION3 = getenv("HELLBOT_SESSION3", None)
    HELLBOT_SESSION4 = getenv("HELLBOT_SESSION4", None)
    
    # do not edit these variables
    BANNED_USERS = filters.user()
    CACHE = {}
    CACHE_DIR = "./cache/"
    DELETE_DICT = {}
    DWL_DIR = "./downloads/"
    GOD_USERS = filters.user()
    PLAYER_CACHE = {}
    QUEUE_CACHE =  {}
    SONG_CACHE = {}
    SUDO_USERS = filters.user()


# get all config variables in a list
all_vars = [i for i in Config.__dict__.keys() if not i.startswith("__")]
