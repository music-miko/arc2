import datetime
import os

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.exceptions import AlreadyJoinedError, NoActiveGroupCall
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import (
    MediumQualityAudio,
    MediumQualityVideo,
)

from config import Config
from Music.helpers.buttons import Buttons
from Music.helpers.strings import TEXTS
from Music.utils.exceptions import (
    ChangeVCException,
    JoinGCException,
    JoinVCException,
    UserException,
)
from Music.utils.queue import Queue
from Music.utils.thumbnail import thumb
from Music.utils.youtube import ytube

from .clients import hellbot
from .database import db
from .logger import LOGS


async def __clean__(chat_id: int, force: bool):
    if force:
        Queue.rm_queue(chat_id, 0)
    else:
        Queue.clear_queue(chat_id)
    await db.remove_active_vc(chat_id)


class HellMusic:
    def __init__(self):
        """
        Voice client manager.

        - self.music: primary PyTgCalls instance (used in decorators like
          @hellmusic.music.on_kicked()).
        - self.clients: list[PyTgCalls] for each assistant userbot, used via
          round-robin to distribute chats.
        """
        self.clients = []

        # Build PyTgCalls per available assistant
        assistants = []
        if getattr(hellbot, "user", None):
            assistants.append(hellbot.user)
        if getattr(hellbot, "user2", None):
            assistants.append(hellbot.user2)
        if getattr(hellbot, "user3", None):
            assistants.append(hellbot.user3)
        if getattr(hellbot, "user4", None):
            assistants.append(hellbot.user4)

        # If no assistant at all, fall back to bot client (not ideal for music,
        # but avoids NoneType for decorators)
        if not assistants:
            LOGS.warning(
                ">> No assistant sessions found; using main bot for PyTgCalls (limited)."
            )
            self.music = PyTgCalls(hellbot.app)
            self.clients.append(self.music)
        else:
            # Primary client (for watcher.py decorators)
            self.music = PyTgCalls(assistants[0])
            self.clients.append(self.music)
            # Extra assistants
            for ub in assistants[1:]:
                self.clients.append(PyTgCalls(ub))

        LOGS.info(f">> Initialized PyTgCalls with {len(self.clients)} client(s).")

        self.audience = {}
        self.assistant_for_chat = {}  # chat_id -> index in self.clients
        self._rr_index = 0            # round-robin

    def _get_assistant(self, chat_id: int):
        """
        Return (pytgcalls_client, userbot_client) for this chat.
        If not assigned yet, assign in round-robin manner.
        """
        if not self.clients:
            raise UserException("[UserException]: No PyTgCalls clients configured.")

        idx = self.assistant_for_chat.get(chat_id)
        if idx is None:
            idx = self._rr_index % len(self.clients)
            self._rr_index += 1
            self.assistant_for_chat[chat_id] = idx

        # Map index back to underlying userbot:
        # First client uses hellbot.user (or hellbot.app fallback),
        # next ones use user2, user3, user4 (where available).
        userbots = []
        if getattr(hellbot, "user", None):
            userbots.append(hellbot.user)
        else:
            userbots.append(hellbot.app)  # fallback
        if getattr(hellbot, "user2", None):
            userbots.append(hellbot.user2)
        if getattr(hellbot, "user3", None):
            userbots.append(hellbot.user3)
        if getattr(hellbot, "user4", None):
            userbots.append(hellbot.user4)

        # In case less userbots than clients (shouldn't happen, but safe):
        if idx >= len(userbots):
            ub = userbots[0]
        else:
            ub = userbots[idx]

        return self.clients[idx], ub

    async def autoend(self, chat_id: int, users: list):
        autoend = await db.get_autoend()
        if autoend:
            try:
                _, userbot = self._get_assistant(chat_id)
                assistant_id = userbot.id
            except Exception:
                assistant_id = None

            if len(users) == 1 and assistant_id:
                get = await hellbot.app.get_users(users[0])
                if get.id == assistant_id:
                    db.inactive[chat_id] = datetime.datetime.now() + datetime.timedelta(
                        minutes=5
                    )
            else:
                db.inactive[chat_id] = {}

    async def autoclean(self, file: str):
        try:
            os.remove(file)
            os.remove(f"downloads/{file}.webm")
            os.remove(f"downloads/{file}.mp4")
        except:
            pass

    async def start(self):
        LOGS.info(">> Starting PyTgCalls client(s)...")
        if not self.clients:
            LOGS.error(">> PyTgCalls not booted: no clients.")
            quit(1)

        for i, client in enumerate(self.clients, start=1):
            try:
                await client.start()
                LOGS.info(f">> PyTgCalls client #{i} started.")
            except Exception as e:
                LOGS.error(f">> Failed to start PyTgCalls client #{i}: {e}")
        LOGS.info(">> All PyTgCalls client(s) started!")

    async def ping(self):
        # Use primary client
        pinged = await self.music.ping
        return pinged

    async def vc_participants(self, chat_id: int):
        client, _ = self._get_assistant(chat_id)
        users = await client.get_participants(chat_id)
        return users

    async def mute_vc(self, chat_id: int):
        client, _ = self._get_assistant(chat_id)
        await client.mute_stream(chat_id)

    async def unmute_vc(self, chat_id: int):
        client, _ = self._get_assistant(chat_id)
        await client.unmute_stream(chat_id)

    async def pause_vc(self, chat_id: int):
        client, _ = self._get_assistant(chat_id)
        await client.pause_stream(chat_id)

    async def resume_vc(self, chat_id: int):
        client, _ = self._get_assistant(chat_id)
        await client.resume_stream(chat_id)

    async def leave_vc(self, chat_id: int, force: bool = False):
        try:
            await __clean__(chat_id, force)
            client, _ = self._get_assistant(chat_id)
            await client.leave_group_call(chat_id)
        except Exception:
            pass
        finally:
            self.assistant_for_chat.pop(chat_id, None)

        previous = Config.PLAYER_CACHE.get(chat_id)
        if previous:
            try:
                await previous.delete()
            except:
                pass

    async def seek_vc(self, context: dict):
        chat_id, file_path, duration, to_seek, video = context.values()
        client, _ = self._get_assistant(chat_id)
        if video:
            input_stream = AudioVideoPiped(
                file_path,
                MediumQualityAudio(),
                MediumQualityVideo(),
                additional_ffmpeg_parameters=f"-ss {to_seek} -to {duration}",
            )
        else:
            input_stream = AudioPiped(
                file_path,
                MediumQualityAudio(),
                additional_ffmpeg_parameters=f"-ss {to_seek} -to {duration}",
            )
        await client.change_stream(chat_id, input_stream)

    async def invited_vc(self, chat_id: int):
        try:
            await hellbot.app.send_message(
                chat_id,
                "The bot will join voice chat only when you give something to play!",
            )
        except:
            return

    async def replay_vc(self, chat_id: int, file_path: str, video: bool = False):
        client, _ = self._get_assistant(chat_id)
        if video:
            input_stream = AudioVideoPiped(
                file_path, MediumQualityAudio(), MediumQualityVideo()
            )
        else:
            input_stream = AudioPiped(file_path, MediumQualityAudio())
        await client.change_stream(chat_id, input_stream)

    async def change_vc(self, chat_id: int):
        client, _ = self._get_assistant(chat_id)
        try:
            get = Queue.get_queue(chat_id)
            if get == []:
                return await self.leave_vc(chat_id)
            loop = await db.get_loop(chat_id)
            if loop == 0:
                file = Queue.rm_queue(chat_id, 0)
                await self.autoclean(file)
            else:
                await db.set_loop(chat_id, loop - 1)
        except Exception as e:
            LOGS.error(e)
            return await self.leave_vc(chat_id)
        get = Queue.get_queue(chat_id)
        if get == []:
            return await self.leave_vc(chat_id)
        chat_id = get[0]["chat_id"]
        duration = get[0]["duration"]
        queue = get[0]["file"]
        title = get[0]["title"]
        user_id = get[0]["user_id"]
        vc_type = get[0]["vc_type"]
        video_id = get[0]["video_id"]
        try:
            user = (await hellbot.app.get_users(user_id)).mention(style="md")
        except:
            user = get[0]["user"]
        if queue:
            tg = True if video_id == "telegram" else False
            if tg:
                to_stream = queue
            else:
                to_stream = await ytube.download(
                    video_id, True, True if vc_type == "video" else False
                )
            if vc_type == "video":
                input_stream = AudioVideoPiped(
                    to_stream, MediumQualityAudio(), MediumQualityVideo()
                )
            else:
                input_stream = AudioPiped(to_stream, MediumQualityAudio())
            try:
                # SIMPLE THUMBNAIL: only video_id
                photo = thumb.generate(video_id)
                await client.change_stream(int(chat_id), input_stream)
                btns = Buttons.player_markup(
                    chat_id,
                    "None" if video_id == "telegram" else video_id,
                    hellbot.app.username,
                )
                if photo:
                    sent = await hellbot.app.send_photo(
                        int(chat_id),
                        photo,
                        TEXTS.PLAYING.format(
                            hellbot.app.mention,
                            title,
                            duration,
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(btns),
                    )
                    os.remove(photo)
                else:
                    sent = await hellbot.app.send_message(
                        int(chat_id),
                        TEXTS.PLAYING.format(
                            hellbot.app.mention,
                            title,
                            duration,
                            user,
                        ),
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup(btns),
                    )
                previous = Config.PLAYER_CACHE.get(chat_id)
                if previous:
                    try:
                        await previous.delete()
                    except:
                        pass
                Config.PLAYER_CACHE[chat_id] = sent
                await db.update_songs_count(1)
                await db.update_user(user_id, "songs_played", 1)
                chat_name = (await hellbot.app.get_chat(chat_id)).title
                await hellbot.logit(
                    f"play {vc_type}",
                    f"**⤷ Song:** `{title}` \n**⤷ Chat:** {chat_name} [`{chat_id}`] \n**⤷ User:** {user}",
                )
            except Exception as e:
                raise ChangeVCException(f"[ChangeVCException]: {e}")

    async def join_vc(self, chat_id: int, file_path: str, video: bool = False):
        client, userbot = self._get_assistant(chat_id)

        if video:
            input_stream = AudioVideoPiped(
                file_path, MediumQualityAudio(), MediumQualityVideo()
            )
        else:
            input_stream = AudioPiped(file_path, MediumQualityAudio())

        try:
            await client.join_group_call(
                chat_id, input_stream, stream_type=StreamType().pulse_stream
            )
        except NoActiveGroupCall:
            try:
                await self.join_gc(chat_id, userbot)
            except Exception as e:
                await self.leave_vc(chat_id)
                raise JoinGCException(e)
            try:
                await client.join_group_call(
                    chat_id, input_stream, stream_type=StreamType().pulse_stream
                )
            except Exception as e:
                await self.leave_vc(chat_id)
                raise JoinVCException(f"[JoinVCException]: {e}")
        except AlreadyJoinedError:
            raise UserException(
                "[UserException]: Already joined in the voice chat. If this is a mistake then try to restart the voice chat."
            )
        except Exception as e:
            raise UserException(f"[UserException]: {e}")

        await db.add_active_vc(chat_id, "video" if video else "voice")
        self.audience[chat_id] = {}
        users = await self.vc_participants(chat_id)
        user_ids = [user.user_id for user in users]
        await self.autoend(chat_id, user_ids)

    async def join_gc(self, chat_id: int, userbot):
        try:
            try:
                get = await hellbot.app.get_chat_member(chat_id, userbot.id)
            except ChatAdminRequired:
                raise UserException(
                    f"[UserException]: Bot is not admin in chat {chat_id}"
                )
            if (
                get.status == ChatMemberStatus.RESTRICTED
                or get.status == ChatMemberStatus.BANNED
            ):
                raise UserException(
                    f"[UserException]: Assistant is restricted or banned in chat {chat_id}"
                )
        except UserNotParticipant:
            chat = await hellbot.app.get_chat(chat_id)
            if chat.username:
                try:
                    await userbot.join_chat(chat.username)
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    raise UserException(f"[UserException]: {e}")
            else:
                try:
                    try:
                        link = chat.invite_link
                        if link is None:
                            link = await hellbot.app.export_chat_invite_link(chat_id)
                    except ChatAdminRequired:
                        raise UserException(
                            f"[UserException]: Bot is not admin in chat {chat_id}"
                        )
                    except Exception as e:
                        raise UserException(f"[UserException]: {e}")
                    hell = await hellbot.app.send_message(
                        chat_id, "Inviting assistant to chat..."
                    )
                    if link.startswith("https://t.me/+"):
                        link = link.replace(
                            "https://t.me/+",
                            "https://t.me/joinchat/",
                        )
                    await userbot.join_chat(link)
                    await hell.edit_text(
                        "Assistant joined the chat! Enjoy your music!"
                    )
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    raise UserException(f"[UserException]: {e}")


hellmusic = HellMusic()
