# Mokasi — a modular personal Telegram bot framework
# Inline forms, ported from Hikka (https://github.com/hikariatama/Hikka)
# The form is sent directly through Bot API — no `_invoke_unit` trick needed
import contextlib
import copy
import logging
import os
import time
import traceback
import typing
from urllib.parse import urlparse

from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from aiogram.types import Message as AiogramMessage

from .. import utils
from ..types import ReplyMarkup
from .types import InlineMessage, InlineUnit

logger = logging.getLogger(__name__)


class Placeholder:
    """Placeholder"""


class Form(InlineUnit):
    async def form(
        self,
        text: str,
        message: typing.Union[AiogramMessage, int],
        reply_markup: typing.Optional[ReplyMarkup] = None,
        *,
        force_me: bool = False,
        always_allow: typing.Optional[typing.List[int]] = None,
        manual_security: bool = False,
        disable_security: bool = False,
        ttl: typing.Optional[int] = None,
        on_unload: typing.Optional[callable] = None,
        photo: typing.Optional[str] = None,
        gif: typing.Optional[str] = None,
        file: typing.Optional[str] = None,
        mime_type: typing.Optional[str] = None,
        video: typing.Optional[str] = None,
        location: typing.Optional[str] = None,
        audio: typing.Optional[typing.Union[dict, str]] = None,
        silent: bool = False,
    ) -> typing.Union[InlineMessage, bool]:
        """
        Send inline form to chat
        :param text: Content of inline form. HTML markdown supported
        :param message: Where to send inline. Can be either `Message` or `int`
        :param reply_markup: List of buttons to insert in markup.
                             List of dicts with keys: text, callback
        :param force_me: Either this form buttons must be pressed only by
                         owner scope or no
        :param always_allow: Users, that are allowed to press buttons in
                             addition to previous rules
        :param ttl: Time, when the form is going to be unloaded
        :param on_unload: Callback, called when form is unloaded and/or closed
        :param manual_security: By default, security of inline buttons is
                                inherited from the caller (command). If you
                                want to avoid this, pass `manual_security=True`
        :param disable_security: Disable all security checks on this form
        :param photo: Attach a photo to the form. URL must be supplied
        :param gif: Attach a gif to the form. URL must be supplied
        :param file: Attach a file to the form. URL must be supplied
        :param mime_type: Only needed, if `file` field is not empty
        :param video: Attach a video to the form. URL must be supplied
        :param location: Attach a map point to the form. List/tuple must be
                         supplied (latitude, longitude)
        :param audio: Attach a audio to the form. Dict or URL must be supplied
        :param silent: Whether the form must be sent silently
                       (w/o "Opening form..." message)
        :return: If form is sent, returns :obj:`InlineMessage`, otherwise
                 returns `False`
        """
        if reply_markup is None:
            reply_markup = []

        if always_allow is None:
            always_allow = []

        if not isinstance(text, str):
            logger.error(
                "Invalid type for `text`. Expected `str`, got `%s`",
                type(text),
            )
            return False

        text = self.sanitise_text(text)

        if not isinstance(silent, bool):
            logger.error(
                "Invalid type for `silent`. Expected `bool`, got `%s`",
                type(silent),
            )
            return False

        if not isinstance(manual_security, bool):
            logger.error(
                "Invalid type for `manual_security`. Expected `bool`, got `%s`",
                type(manual_security),
            )
            return False

        if not isinstance(disable_security, bool):
            logger.error(
                "Invalid type for `disable_security`. Expected `bool`, got `%s`",
                type(disable_security),
            )
            return False

        if not isinstance(message, (AiogramMessage, int)):
            logger.error(
                "Invalid type for `message`. Expected `Message` or `int`, got `%s`",
                type(message),
            )
            return False

        if not isinstance(reply_markup, (list, dict)):
            logger.error(
                "Invalid type for `reply_markup`. Expected `list` or `dict`, got `%s`",
                type(reply_markup),
            )
            return False

        if photo and (not isinstance(photo, str) or not utils.check_url(photo)):
            logger.error(
                "Invalid type for `photo`. Expected `str` with URL, got `%s`",
                type(photo),
            )
            return False

        try:
            path = urlparse(photo).path
            ext = os.path.splitext(path)[1]
        except Exception:
            ext = None

        if photo is not None and ext in {".gif", ".mp4"}:
            gif = copy.copy(photo)
            photo = None

        if gif and (not isinstance(gif, str) or not utils.check_url(gif)):
            logger.error(
                "Invalid type for `gif`. Expected `str` with URL, got `%s`",
                type(gif),
            )
            return False

        if file and (not isinstance(file, str) or not utils.check_url(file)):
            logger.error(
                "Invalid type for `file`. Expected `str` with URL, got `%s`",
                type(file),
            )
            return False

        if file and not mime_type:
            logger.error(
                "You must pass `mime_type` along with `file` field\n"
                "It may be either 'application/zip' or 'application/pdf'"
            )
            return False

        if video and (not isinstance(video, str) or not utils.check_url(video)):
            logger.error(
                "Invalid type for `video`. Expected `str` with URL, got `%s`",
                type(video),
            )
            return False

        if isinstance(audio, str):
            audio = {"url": audio}

        if audio and (
            not isinstance(audio, dict)
            or "url" not in audio
            or not utils.check_url(audio["url"])
        ):
            logger.error(
                "Invalid type for `audio`. Expected `dict` with `url` key, got `%s`",
                type(audio),
            )
            return False

        if location and (
            not isinstance(location, (list, tuple))
            or len(location) != 2
            or not all(isinstance(item, float) for item in location)
        ):
            logger.error(
                (
                    "Invalid type for `location`. Expected `list` or `tuple` with 2"
                    " `float` items, got `%s`"
                ),
                type(location),
            )
            return False

        if [
            photo is not None,
            gif is not None,
            file is not None,
            video is not None,
            audio is not None,
            location is not None,
        ].count(True) > 1:
            logger.error("You passed two or more exclusive parameters simultaneously")
            return False

        reply_markup = self._validate_markup(reply_markup) or []

        if not isinstance(force_me, bool):
            logger.error(
                "Invalid type for `force_me`. Expected `bool`, got `%s`",
                type(force_me),
            )
            return False

        if not isinstance(always_allow, list):
            logger.error(
                "Invalid type for `always_allow`. Expected `list`, got `%s`",
                type(always_allow),
            )
            return False

        if not isinstance(ttl, int) and ttl:
            logger.error("Invalid type for `ttl`. Expected `int`, got `%s`", type(ttl))
            return False

        if isinstance(message, AiogramMessage) and not silent:
            try:
                status_message = await message.answer(
                    "🌘 Opening form...",
                )
            except Exception:
                status_message = None
        else:
            status_message = None

        unit_id = utils.rand(16)

        perms_map = None if manual_security else self._find_caller_sec_map()

        if not reply_markup and not ttl:
            logger.debug("Patching form reply markup with empty data")
            base_reply_markup = copy.deepcopy(reply_markup) or None
            reply_markup = self._validate_markup({"text": "­", "data": "­"})
        else:
            base_reply_markup = Placeholder()

        if (
            not any(
                any("callback" in button or "input" in button for button in row)
                for row in reply_markup
            )
            and not ttl
        ):
            logger.debug(
                "Patching form ttl to 10 minutes, because it doesn't contain any"
                " buttons"
            )
            ttl = 10 * 60

        self._units[unit_id] = {
            "type": "form",
            "text": text,
            "buttons": reply_markup,
            "caller": message,
            "chat": None,
            "message_id": None,
            "top_msg_id": (
                message.message_id if isinstance(message, AiogramMessage) else None
            ),
            "uid": unit_id,
            "on_unload": on_unload,
            **({"photo": photo} if photo else {}),
            **({"video": video} if video else {}),
            **({"gif": gif} if gif else {}),
            **({"location": location} if location else {}),
            **({"audio": audio} if audio else {}),
            **({"perms_map": perms_map} if perms_map else {}),
            **({"message": message} if isinstance(message, AiogramMessage) else {}),
            **({"force_me": force_me} if force_me else {}),
            **({"disable_security": disable_security} if disable_security else {}),
            **({"ttl": round(time.time()) + ttl} if ttl else {}),
            **({"always_allow": always_allow} if always_allow else {}),
        }

        async def answer(msg: str):
            nonlocal message
            if isinstance(message, AiogramMessage):
                await message.answer(msg)
            else:
                await self.bot.send_message(message, msg)

        try:
            chat_id = (
                utils.get_chat_id(message)
                if isinstance(message, AiogramMessage)
                else message
            )

            reply_to = (
                message.message_id if isinstance(message, AiogramMessage) else None
            )

            send_kwargs = {
                "chat_id": chat_id,
                "reply_markup": self.generate_markup(unit_id),
                **({"reply_to_message_id": reply_to} if reply_to else {}),
            }

            if photo:
                m = await self.bot.send_photo(photo, caption=text, **send_kwargs)
            elif gif:
                m = await self.bot.send_animation(gif, caption=text, **send_kwargs)
            elif video:
                m = await self.bot.send_video(video, caption=text, **send_kwargs)
            elif file:
                m = await self.bot.send_document(
                    file,
                    caption=text,
                    **send_kwargs,
                )
            elif audio:
                m = await self.bot.send_audio(
                    audio["url"],
                    caption=text,
                    title=audio.get("title"),
                    performer=audio.get("performer"),
                    duration=audio.get("duration"),
                    **send_kwargs,
                )
            elif location:
                m = await self.bot.send_location(
                    location[0],
                    location[1],
                    **send_kwargs,
                )
            else:
                m = await self.bot.send_message(
                    text,
                    disable_web_page_preview=True,
                    **send_kwargs,
                )
        except Exception:
            logger.exception("Can't send form")

            del self._units[unit_id]
            await answer(
                "🚫 <b>Can't send form. Error in logs</b>"
                + (
                    "\n<i>"
                    + utils.escape_html(
                        "\n".join(traceback.format_exc().splitlines()[1:])
                    )
                    + "</i>"
                )
                if self._db.get("mokasi.main", "inlinelogs", True)
                else ""
            )

            return False

        self._units[unit_id]["chat"] = utils.get_chat_id(m)
        self._units[unit_id]["message_id"] = m.message_id

        if status_message:
            with contextlib.suppress(Exception):
                await status_message.delete()

        msg = InlineMessage(
            self,
            unit_id,
            chat_id=self._units[unit_id]["chat"],
            message_id=m.message_id,
        )

        if not isinstance(base_reply_markup, Placeholder):
            await msg.edit(text, reply_markup=base_reply_markup)

        return msg

    async def _form_inline_handler(self, inline_query: InlineQuery):
        """Answers placeholder article for `input` buttons"""
        try:
            query = inline_query.query.split()[0]
        except IndexError:
            return

        for unit in self._units.copy().values():
            for button in utils.array_sum(unit.get("buttons", [])):
                if (
                    "_switch_query" in button
                    and "input" in button
                    and button["_switch_query"] == query
                    and inline_query.from_user.id
                    in [self.bot.id]
                    + list(self.security._owner)
                    + unit.get("always_allow", [])
                ):
                    await inline_query.answer(
                        [
                            InlineQueryResultArticle(
                                id=utils.rand(20),
                                title=button["input"],
                                description="Tap to confirm input",
                                input_message_content=InputTextMessageContent(message_text=
                                    "🔄 <b>Transferring value to bot...</b>\n"
                                    "<i>This message will be deleted automatically</i>",
                                    parse_mode="HTML",
                                    disable_web_page_preview=True,
                                ),
                            )
                        ],
                        cache_time=60,
                    )
                    return
