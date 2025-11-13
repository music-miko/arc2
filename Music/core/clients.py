from pyrogram import Client

from config import Config
from Music.utils.exceptions import HellBotException

from .logger import LOGS


class HellClient(Client):
    def __init__(self):
        # Main bot client
        self.app = Client(
            "HellMusic",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="Music.plugins"),
            workers=100,
        )

        # List to store all assistant userbots
        self.user_bots = []

        # Helper to create a userbot client
        def _make_user(session_name: str, session_string: str) -> Client:
            return Client(
                session_name,
                api_id=Config.API_ID,
                api_hash=Config.API_HASH,
                session_string=session_string,
                no_updates=True,
            )

        # Assistant 1 (original one)
        self.user = None
        if getattr(Config, "HELLBOT_SESSION", None):
            self.user = _make_user("HellClient", Config.HELLBOT_SESSION)
            self.user_bots.append(self.user)

        # Assistant 2
        self.user2 = None
        if getattr(Config, "HELLBOT_SESSION2", None):
            self.user2 = _make_user("HellClient2", Config.HELLBOT_SESSION2)
            self.user_bots.append(self.user2)

        # Assistant 3
        self.user3 = None
        if getattr(Config, "HELLBOT_SESSION3", None):
            self.user3 = _make_user("HellClient3", Config.HELLBOT_SESSION3)
            self.user_bots.append(self.user3)

        # Assistant 4
        self.user4 = None
        if getattr(Config, "HELLBOT_SESSION4", None):
            self.user4 = _make_user("HellClient4", Config.HELLBOT_SESSION4)
            self.user_bots.append(self.user4)

        # Optional: list of assistant info (id, name, etc.)
        self.assistants = []

    async def start(self):
        LOGS.info(">> Booting up HellMusic...")

        # Start bot
        if Config.BOT_TOKEN:
            await self.app.start()
            me = await self.app.get_me()
            self.app.id = me.id
            self.app.mention = me.mention
            self.app.name = me.first_name
            self.app.username = me.username
            LOGS.info(f">> {self.app.name} is online now!")

        # Start all assistant userbots (up to 4)
        if self.user_bots:
            for idx, userbot in enumerate(self.user_bots, start=1):
                try:
                    await userbot.start()
                    me = await userbot.get_me()
                    userbot.id = me.id
                    userbot.mention = me.mention
                    userbot.name = me.first_name
                    userbot.username = me.username

                    # Keep assistant info
                    self.assistants.append(
                        {
                            "index": idx,
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
                        pass

                    LOGS.info(f">> Assistant {idx}: {userbot.name} is online now!")
                except Exception as e:
                    LOGS.error(f">> Failed to start assistant {idx}: {e}")

        LOGS.info(">> Booted up HellMusic with assistants!")

    async def logit(self, hash: str, log: str, file: str = None):
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
        except Exception as e:
            raise HellBotException(f"[HellBotException]: {e}")


hellbot = HellClient()
