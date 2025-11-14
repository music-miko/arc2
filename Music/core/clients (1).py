from pyrogram import Client

from config import Config
from Music.utils.exceptions import HellBotException

from .logger import LOGS


class HellClient(Client):
    def __init__(self):
        # Bot client
        self.app = Client(
            "HellMusic",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="Music.plugins"),
            workers=100,
        )

        # --- MULTI ASSISTANT SUPPORT (UP TO 4) ---
        # Collect all session strings that exist in Config
        session_strings = []

        # Old / primary session (backwards compatible)
        if getattr(Config, "HELLBOT_SESSION", None):
            session_strings.append(Config.HELLBOT_SESSION)

        # Optional extra assistants
        for attr in ("HELLBOT_SESSION2", "HELLBOT_SESSION3", "HELLBOT_SESSION4"):
            if hasattr(Config, attr):
                value = getattr(Config, attr)
                if value:
                    session_strings.append(value)

        # Create assistant clients list
        self.users = []
        for idx, session in enumerate(session_strings, start=1):
            self.users.append(
                Client(
                    f"HellClient{idx}",
                    api_id=Config.API_ID,
                    api_hash=Config.API_HASH,
                    session_string=session,
                    no_updates=True,
                )
            )

        # Backwards compatibility: primary assistant
        self.user = self.users[0] if self.users else None

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

        # Start all assistants (up to 4)
        if self.users:
            for idx, user_client in enumerate(self.users, start=1):
                await user_client.start()
                me = await user_client.get_me()
                user_client.id = me.id
                user_client.mention = me.mention
                user_client.name = me.first_name
                user_client.username = me.username

                try:
                    await user_client.join_chat("ArcBotz")
                    await user_client.join_chat("ArcUpdates")
                except Exception:
                    # Ignore join errors silently
                    pass

                LOGS.info(f">> Assistant {idx} ({user_client.name}) is online now!")
        else:
            LOGS.info(">> No assistant sessions configured (HELLBOT_SESSION*).")

        LOGS.info(">> Booted up HellMusic!")

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
