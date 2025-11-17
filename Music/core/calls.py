import datetime
import os

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    UserAlreadyParticipant,
    UserNotParticipant,
    FloodWait,
)
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.exceptions import AlreadyJoinedError, NoActiveGroupCall
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import MediumQualityAudio, MediumQualityVideo

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


# ============================================================
#               MULTI–ASSISTANT PYTGCallS VERSION
# ============================================================

class HellMusic(PyTgCalls):
    def __init__(self):
        # all assistant accounts from updated clients.py
        self.assistants = getattr(hellbot, "users", None) or (
            [hellbot.user] if getattr(hellbot, "user", None) else []
        )

        # one PyTgCalls client per assistant
        self._music_clients = [PyTgCalls(client) for client in self.assistants]

        # backwards compatible primary client (assistant #1)
        self.music = self._music_clients[0] if self._music_clients else None

        # per chat mapping → assigned assistant index
        self._chat_assistant = {}
        self._rr_counter = 0

        self.audience = {}

    # ---------- internal round robin helper ----------
    def _assign_rr(self, chat_id):
        if chat_id not in self._chat_assistant:
            self._chat_assistant[chat_id] = self._rr_counter % len(self.assistants)
            self._rr_counter += 1

    def _get_assistant(self, chat_id):
        if not self.assistants:
            return hellbot.user
        self._assign_rr(chat_id)
        return self.assistants[self._chat_assistant[chat_id]]

    def _get_music(self, chat_id):
        if not self._music_clients:
            return self.music
        self._assign_rr(chat_id)
        return self._music_clients[self._chat_assistant[chat_id]]

    # --------------------------------------------------

    async def autoend(self, chat_id: int, users: list):
        autoend = await db.get_autoend()
        if not autoend:
            return

        assistant = self._get_assistant(chat_id)
        assistant_id = getattr(assistant, "id", None)

        if len(users) == 1 and users[0] == assistant_id:
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
        LOGS.info(">> Booting PyTgCalls Clients...")
        if not self._music_clients:
            LOGS.error(">> No assistant sessions detected!")
            quit(1)

        for idx, client in enumerate(self._music_clients, start=1):
            try:
                await client.start()
                LOGS.info(f">> PyTgCalls Client #{idx} is online!")
            except Exception as e:
                LOGS.error(f">> Failed to start PyTgCalls client #{idx}: {e}")

    async def ping(self):
        return await self.music.ping

    async def vc_participants(self, chat_id: int):
        music = self._get_music(chat_id)
        return await music.get_participants(chat_id)

    async def mute_vc(self, chat_id: int):
        music = self._get_music(chat_id)
        await music.mute_stream(chat_id)

    async def unmute_vc(self, chat_id: int):
        music = self._get_music(chat_id)
        await music.unmute_stream(chat_id)

    async def pause_vc(self, chat_id: int):
        music = self._get_music(chat_id)
        await music.pause_stream(chat_id)

    async def resume_vc(self, chat_id: int):
        music = self._get_music(chat_id)
        await music.resume_stream(chat_id)

    async def leave_vc(self, chat_id: int, force: bool = False):
        try:
            await __clean__(chat_id, force)
            music = self._get_music(chat_id)
            await music.leave_group_call(chat_id)
        except:
            pass
        previous = Config.PLAYER_CACHE.get(chat_id)
        if previous:
            try:
                await previous.delete()
            except:
                pass

    async def seek_vc(self, context: dict):
        chat_id, file_path, duration, to_seek, video = context.values()

        if video:
            stream = AudioVideoPiped(
                file_path,
                MediumQualityAudio(),
                MediumQualityVideo(),
                additional_ffmpeg_parameters=f"-ss {to_seek} -to {duration}",
            )
        else:
            stream = AudioPiped(
                file_path,
                MediumQualityAudio(),
                additional_ffmpeg_parameters=f"-ss {to_seek} -to {duration}",
            )

        music = self._get_music(chat_id)
        await music.change_stream(chat_id, stream)

    async def invited_vc(self, chat_id: int):
        try:
            await hellbot.app.send_message(
                chat_id, "The bot will join VC only when you play something!"
            )
        except:
            pass

    async def replay_vc(self, chat_id: int, file_path: str, video: bool = False):
        if video:
            stream = AudioVideoPiped(
                file_path, MediumQualityAudio(), MediumQualityVideo()
            )
        else:
            stream = AudioPiped(file_path, MediumQualityAudio())

        music = self._get_music(chat_id)
        await music.change_stream(chat_id, stream)

    # ====================== CHANGE VC ============================
    async def change_vc(self, chat_id: int):
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
            photo = thumb.generate(video_id)
            music = self._get_music(chat_id)
            await music.change_stream(int(chat_id), input_stream)

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

    # ====================== JOIN VC ============================
    async def join_vc(self, chat_id: int, file_path: str, video: bool = False):
        if video:
            stream = AudioVideoPiped(
                file_path, MediumQualityAudio(), MediumQualityVideo()
            )
        else:
            stream = AudioPiped(file_path, MediumQualityAudio())

        music = self._get_music(chat_id)

        try:
            await music.join_group_call(
                chat_id, stream, stream_type=StreamType().pulse_stream
            )
        except NoActiveGroupCall:
            try:
                await self.join_gc(chat_id)
            except Exception as e:
                await self.leave_vc(chat_id)
                raise JoinGCException(e)

            try:
                await music.join_group_call(
                    chat_id, stream, stream_type=StreamType().pulse_stream
                )
            except Exception as e:
                await self.leave_vc(chat_id)
                raise JoinVCException(f"[JoinVCException]: {e}")

        except AlreadyJoinedError:
            raise UserException(
                "[UserException]: Already joined. Restart VC if this is wrong."
            )
        except Exception as e:
            raise UserException(f"[UserException]: {e}")

        await db.add_active_vc(chat_id, "video" if video else "voice")
        self.audience[chat_id] = {}

        users = await self.vc_participants(chat_id)
        user_ids = [u.user_id for u in users]
        await self.autoend(chat_id, user_ids)

    # ====================== JOIN GC ============================
    async def join_gc(self, chat_id: int):
        """
        Make the correct assistant join the chat.
        - If assistant is already in chat: DO NOTHING (no join_chat() call)
        - If approvals are enabled: assistant sends request, bot tries to approve it
        """
        assistant = self._get_assistant(chat_id)

        # 1) Check if assistant is already in the chat
        try:
            member = await hellbot.app.get_chat_member(chat_id, assistant.id)
        except ChatAdminRequired:
            # main bot is not admin, can't inspect members
            raise UserException(
                "[UserException]: Bot is not admin in this chat, so it cannot manage the assistant."
            )
        except UserNotParticipant:
            # assistant not in chat → we will try to join below
            pass
        else:
            # No exception: assistant *is* in chat already
            if member.status in (ChatMemberStatus.RESTRICTED, ChatMemberStatus.BANNED):
                raise UserException(
                    "[UserException]: Assistant is restricted or banned in this chat."
                )
            # already a member and not restricted → nothing to do
            return

        # 2) Assistant is not participant → try to join
        chat = await hellbot.app.get_chat(chat_id)

        # Public chat with username
        if chat.username:
            try:
                await assistant.join_chat(chat.username)

                # If join-requests are enabled, this may have created a join request.
                # Try to approve it with the bot (if it has rights).
                try:
                    await hellbot.app.approve_chat_join_request(chat_id, assistant.id)
                except Exception:
                    # ignore if no pending request / no rights
                    pass

            except UserAlreadyParticipant:
                # rare race: joined between get_chat_member and here
                pass
            except FloodWait as fw:
                raise UserException(
                    f"[UserException]: Assistant is being rate-limited by Telegram. "
                    f"Please wait {fw.value} seconds or add @{assistant.username} manually."
                )
            except Exception as e:
                raise UserException(
                    "[UserException]: Failed to add assistant to chat. "
                    "Please add it manually and try again."
                )

        # Private / no-username chat → use invite link (may create join request)
        else:
            try:
                try:
                    link = chat.invite_link
                    if link is None:
                        link = await hellbot.app.export_chat_invite_link(chat_id)
                except ChatAdminRequired:
                    raise UserException(
                        "[UserException]: Bot is not admin and cannot export invite link. "
                        "Please add the assistant manually."
                    )

                invite_msg = await hellbot.app.send_message(
                    chat_id, "Inviting assistant to chat..."
                )

                if link.startswith("https://t.me/+"):
                    link = link.replace("https://t.me/+", "https://t.me/joinchat/")

                try:
                    await assistant.join_chat(link)

                    # Same as above: if approvals are enabled, this will be a join request.
                    try:
                        await hellbot.app.approve_chat_join_request(
                            chat_id, assistant.id
                        )
                    except Exception:
                        # ignore if no request / no rights
                        pass

                    await invite_msg.edit_text(
                        "Assistant joined the chat! Enjoy your music!"
                    )

                except UserAlreadyParticipant:
                    await invite_msg.edit_text(
                        "Assistant is already in this chat. Enjoy your music!"
                    )
                except FloodWait as fw:
                    await invite_msg.edit_text(
                        f"Assistant is being rate-limited by Telegram.\n\n"
                        f"• Please wait **{fw.value} seconds**, or\n"
                        f"• Manually add @{assistant.username} to this chat and promote it."
                    )
                    raise UserException(
                        "[UserException]: Assistant hit FloodWait while joining via invite link."
                    )
                except Exception:
                    await invite_msg.edit_text(
                        "Failed to auto-add assistant. "
                        f"Please add @{assistant.username} manually and try again."
                    )
                    raise UserException(
                        "[UserException]: Assistant could not join via invite link."
                    )

            except UserAlreadyParticipant:
                # safety fallback
                pass
            except FloodWait as fw:
                raise UserException(
                    f"[UserException]: Assistant is currently rate-limited by Telegram. "
                    f"Please wait {fw.value} seconds or add @{assistant.username} manually."
                )
            except Exception:
                raise UserException(
                    "[UserException]: Something went wrong while inviting the assistant. "
                    "Please add it manually and try again."
                )


# export instance
hellmusic = HellMusic()
