import asyncio
from pyrogram import Client
from pyrogram.errors import FloodWait

from config import Config
from Music.utils.exceptions import HellBotException

from .logger import LOGS


class HellClient(Client):
    def __init__(self):
        # We still inherit Client only to use .run(), we don't use it as a real TG client.
        # Main bot client (the actual bot)
        self.app = Client(
            "HellMusic",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="Music.plugins"),
            workers=100,
        )

        # List of *started* assistant userbots
        self.user_bots = []

        # Keep raw assistant configs (session name, session string) so we can
        # try starting them one by one and report errors.
        self._assistant_configs = []

        # Assistant 1 (original one)
        self.user = None
        if getattr(Config, "HELLBOT_SESSION", None):
            self._assistant_configs.append(("HellClient", Config.HELLBOT_SESSION))

        # Assistant 2
        self.user2 = None
        if getattr(Config, "HELLBOT_SESSION2", None):
            self._assistant_configs.append(("HellClient2", Config.HELLBOT_SESSION2))

        # Assistant 3
        self.user3 = None
        if getattr(Config, "HELLBOT_SESSION3", None):
            self._assistant_configs.append(("HellClient3", Config.HELLBOT_SESSION3))

        # Assistant 4
        self.user4 = None
        if getattr(Config, "HELLBOT_SESSION4", None):
            self._assistant_configs.append(("HellClient4", Config.HELLBOT_SESSION4))

        # Info + error reporting
        self.assistants = []         # successfully started assistants
        self.assistants_failed = []  # failures: {"index": i, "name": ..., "error": ...}

    async def _safe_notify_owner(self, text: str):
        """
        Try to send a message to LOGGER_ID, but *never* let FloodWait or other
        errors crash the bot.
        """
        if not getattr(Config, "LOGGER_ID", None):
            return
        try:
            await self.app.send_message(Config.LOGGER_ID, text)
        except FloodWait as e:
            LOGS.warning(
                f"[LOGGER FloodWait] Need to wait {e.value} seconds when notifying owner. Skipping this log."
            )
        except Exception as e:
            LOGS.error(f"[LOGGER Notify Error]: {e}")

    async def start(self):
        LOGS.info(">> Booting up HellMusic...")

        # ──────────────────────────────────────────
        # Start main bot client
        # ──────────────────────────────────────────
        if Config.BOT_TOKEN:
            await self.app.start()
            me = await self.app.get_me()
            self.app.id = me.id
            self.app.mention = me.mention
            self.app.name = me.first_name
            self.app.username = me.username
            LOGS.info(f">> {self.app.name} is online now!")

        # ──────────────────────────────────────────
        # Start assistant userbots (up to 4)
        # Only successfully started ones are added to self.user_bots
        # ──────────────────────────────────────────
        if self._assistant_configs:
            for idx, (session_name, session_string) in enumerate(
                self._assistant_configs, start=1
            ):
                try:
                    userbot = Client(
                        session_name,
                        api_id=Config.API_ID,
                        api_hash=Config.API_HASH,
                        session_string=session_string,
                        no_updates=True,
                    )
                    await userbot.start()
                    me = await userbot.get_me()
                    userbot.id = me.id
                    userbot.mention = me.mention
                    userbot.name = me.first_name
                    userbot.username = me.username

                    # Store on object
                    if idx == 1:
                        self.user = userbot
                    elif idx == 2:
                        self.user2 = userbot
                    elif idx == 3:
                        self.user3 = userbot
                    elif idx == 4:
                        self.user4 = userbot

                    self.user_bots.append(userbot)
                    self.assistants.append(
                        {
                            "index": idx,
                            "session_name": session_name,
                            "id": me.id,
                            "name": me.first_name,
                            "username": me.username,
                        }
                    )

                    # Auto-join your channels from each assistant
                    try:
                        await userbot.join_chat("ArcUpdates")
                        await userbot.join_chat("ArcChatz")
                    except Exception:
                        # Not critical, ignore
                        pass

                    LOGS.info(f">> Assistant {idx} ({session_name}): {userbot.name} is online now!")
                except Exception as e:
                    err_text = f">> Failed to start assistant {idx} ({session_name}): {e}"
                    LOGS.error(err_text)
                    self.assistants_failed.append(
                        {
                            "index": idx,
                            "session_name": session_name,
                            "error": str(e),
                        }
                    )
                    # Try to notify owner in LOGGER_ID (but don't crash on FloodWait)
                    await self._safe_notify_owner(err_text)

        if not self.user_bots:
            LOGS.warning(">> No assistant userbots started! Only main bot is running.")
        else:
            LOGS.info(f">> Booted up HellMusic with {len(self.user_bots)} assistant(s)!")

    async def logit(self, hash: str, log: str, file: str = None):
        """
        Send log messages/documents to LOGGER_ID using main bot.
        Never crash on FloodWait; just log a warning.
        """
        log_text = f"#{hash.upper()} \n\n{log}"
        try:
            if file:
                await self.app.send_document(
                    Config.LOGGER_ID, file, caption=log_text
                )
            else:
                await self.app.send_message(
                    Config.LOGGER_ID, log_text, disable_web_page_preview=True
                )
        except FloodWait as e:
            # Don't kill the bot on FloodWait; just warn and drop this log.
            LOGS.warning(
                f"[LOGGER FloodWait] Need to wait {e.value} seconds. Dropping this log message."
            )
        except Exception as e:
            # Other errors about logging should be wrapped as HellBotException
            raise HellBotException(f"[HellBotException]: {e}")


hellbot = HellClient()
