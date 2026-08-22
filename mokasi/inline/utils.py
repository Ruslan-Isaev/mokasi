# Mokasi — a modular personal Telegram bot framework
# Inline markup generation and unit editing, ported from Hikka
# (https://github.com/hikariatama/Hikka) and adapted for aiogram 3
import asyncio
import contextlib
import functools
import io
import itertools
import logging
import os
import re
import typing
from copy import deepcopy
from urllib.parse import urlparse

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAnimation,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
)

from .. import utils
from ..types import ReplyMarkup
from .types import InlineCall, InlineUnit

logger = logging.getLogger(__name__)

_EDIT_FAIL_ALERT = "I should have edited some message, but it is deleted :("


class Utils(InlineUnit):
    def _generate_markup(
        self,
        markup_obj: typing.Optional[typing.Union[ReplyMarkup, str]],
    ) -> typing.Optional[InlineKeyboardMarkup]:
        """Generate markup for form or list of `dict`s"""
        if not markup_obj:
            return None

        if isinstance(markup_obj, InlineKeyboardMarkup):
            return markup_obj

        map_ = (
            self._units[markup_obj]["buttons"]
            if isinstance(markup_obj, str)
            else markup_obj
        )

        map_ = self._normalize_markup(map_)

        setup_callbacks = False

        for row in map_:
            for button in row:
                if not isinstance(button, dict):
                    logger.error(
                        "Button %s is not a `dict`, but `%s` in %s",
                        button,
                        type(button),
                        map_,
                    )
                    return None

                if "callback" not in button:
                    if button.get("action") == "close":
                        button["callback"] = self._close_unit_handler

                    if button.get("action") == "unload":
                        button["callback"] = self._unload_unit_handler

                    if button.get("action") == "answer":
                        if not button.get("message"):
                            logger.error(
                                "Button %s has no `message` to answer with", button
                            )
                            return None

                        button["callback"] = functools.partial(
                            self._answer_unit_handler,
                            show_alert=button.get("show_alert", False),
                            text=button["message"],
                        )

                if "callback" in button and "_callback_data" not in button:
                    button["_callback_data"] = utils.rand(30)
                    setup_callbacks = True

                if "input" in button and "_switch_query" not in button:
                    button["_switch_query"] = utils.rand(10)

        keyboard = []
        for row in map_:
            line = []
            for button in row:
                try:
                    if "url" in button:
                        if not utils.check_url(button["url"]):
                            logger.warning(
                                "Button have not been added to form, "
                                "because its url is invalid"
                            )
                            continue

                        line += [
                            InlineKeyboardButton(
                                text=button["text"],
                                url=button["url"],
                            )
                        ]
                    elif "callback" in button:
                        data = button["_callback_data"]

                        # Telegram API allows at most 64 bytes of callback data
                        if len(data.encode()) > 64:
                            logger.error(
                                "Callback data is too long (%s bytes), skipping button",
                                len(data.encode()),
                            )
                            continue

                        line += [
                            InlineKeyboardButton(
                                text=button["text"],
                                callback_data=data,
                            )
                        ]
                        if setup_callbacks:
                            self._custom_map[data] = {
                                "handler": button["callback"],
                                **(
                                    {"always_allow": button["always_allow"]}
                                    if button.get("always_allow", False)
                                    else {}
                                ),
                                **(
                                    {"args": button["args"]}
                                    if button.get("args", False)
                                    else {}
                                ),
                                **(
                                    {"kwargs": button["kwargs"]}
                                    if button.get("kwargs", False)
                                    else {}
                                ),
                                **(
                                    {"force_me": True}
                                    if button.get("force_me", False)
                                    else {}
                                ),
                                **(
                                    {"disable_security": True}
                                    if button.get("disable_security", False)
                                    else {}
                                ),
                            }
                    elif "input" in button:
                        line += [
                            InlineKeyboardButton(
                                text=button["text"],
                                switch_inline_query_current_chat=button["_switch_query"]
                                + " ",
                            )
                        ]
                    elif "data" in button:
                        if len(button["data"].encode()) > 64:
                            logger.error(
                                "Callback data is too long (%s bytes), skipping button",
                                len(button["data"].encode()),
                            )
                            continue

                        line += [
                            InlineKeyboardButton(
                                text=button["text"],
                                callback_data=button["data"],
                            )
                        ]
                    elif "switch_inline_query_current_chat" in button:
                        line += [
                            InlineKeyboardButton(
                                text=button["text"],
                                switch_inline_query_current_chat=button[
                                    "switch_inline_query_current_chat"
                                ],
                            )
                        ]
                    elif "switch_inline_query" in button:
                        line += [
                            InlineKeyboardButton(
                                text=button["text"],
                                switch_inline_query_current_chat=button[
                                    "switch_inline_query"
                                ],
                            )
                        ]
                    else:
                        logger.warning(
                            (
                                "Button have not been added to "
                                "form, because it is not structured "
                                "properly. %s"
                            ),
                            button,
                        )
                except KeyError:
                    logger.exception(
                        "Error while forming markup! Probably, you "
                        "passed wrong type combination for button. "
                        "Contact developer of module."
                    )
                    return False

            keyboard.append(line)

        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    generate_markup = _generate_markup

    async def _close_unit_handler(self, call: InlineCall):
        await call.delete()

    async def _unload_unit_handler(self, call: InlineCall):
        await call.unload()

    async def _answer_unit_handler(self, call: InlineCall, text: str, show_alert: bool):
        await call.answer(text, show_alert=show_alert)

    def _reverse_method_lookup(self, needle: callable, /) -> typing.Optional[str]:
        return next(
            (
                name
                for name, method in itertools.chain(
                    self._allmodules.inline_handlers.items(),
                    self._allmodules.callback_handlers.items(),
                )
                if method == needle
            ),
            None,
        )

    async def check_inline_security(self, *, func: typing.Callable, user: int) -> bool:
        """Checks if user with id `user` is allowed to run function `func`"""
        return await self.security.check(
            message=None,
            func=func,
            user_id=user,
            inline_cmd=self._reverse_method_lookup(func),
        )

    def _find_caller_sec_map(self) -> typing.Optional[typing.Callable[[], int]]:
        try:
            caller = utils.find_caller()
            if not caller:
                return None

            logger.debug("Found caller: %s", caller)

            return lambda: self.security.get_flags(
                getattr(caller, "__self__", caller),
            )
        except Exception:
            logger.debug("Can't parse security mask in form", exc_info=True)

        return None

    def _patch_unit_security(
        self,
        buttons: typing.List[typing.List[dict]],
        unit_id: str,
    ) -> typing.List[typing.List[dict]]:
        """
        Inherit unit security context into buttons, so pagination buttons
        registered in `_custom_map` respect `always_allow`, `force_me` and
        `disable_security` of the unit they belong to
        """
        unit = self._units.get(unit_id, {})

        for row in buttons:
            for button in row:
                if "callback" in button:
                    button.setdefault("force_me", unit.get("force_me", False))
                    button.setdefault(
                        "disable_security",
                        unit.get("disable_security", False),
                    )
                    button.setdefault(
                        "always_allow",
                        unit.get("always_allow", []),
                    )

        return buttons

    def _normalize_markup(
        self, reply_markup: ReplyMarkup
    ) -> typing.List[typing.List[typing.Dict[str, typing.Any]]]:
        if isinstance(reply_markup, dict):
            return [[reply_markup]]

        if isinstance(reply_markup, list) and any(
            isinstance(i, dict) for i in reply_markup
        ):
            return [reply_markup]

        return reply_markup

    def sanitise_text(self, text: str) -> str:
        """
        Replaces all animated emojis in text with normal ones,
        bc aiogram doesn't support them

        :param text: text to sanitise
        :return: sanitised text
        """
        return re.sub(r"</?emoji.*?>", "", text)

    def _edit_kwargs(
        self,
        *,
        call: typing.Optional[CallbackQuery] = None,
        unit: typing.Optional[dict] = None,
        inline_message_id: typing.Optional[str] = None,
        chat_id: typing.Optional[int] = None,
        message_id: typing.Optional[int] = None,
    ) -> dict:
        """Resolve message target kwargs for Bot API edit calls"""
        if chat_id and message_id:
            return {"chat_id": chat_id, "message_id": message_id}

        if inline_message_id:
            return {"inline_message_id": inline_message_id}

        if call is not None:
            if getattr(call, "inline_message_id", None):
                return {"inline_message_id": call.inline_message_id}

            if getattr(getattr(call, "message", None), "chat", None):
                return {
                    "chat_id": call.message.chat.id,
                    "message_id": call.message.message_id,
                }

        if unit is not None:
            if unit.get("inline_message_id"):
                return {"inline_message_id": unit["inline_message_id"]}

            if unit.get("chat") and unit.get("message_id"):
                return {
                    "chat_id": unit["chat"],
                    "message_id": unit["message_id"],
                }

        return {}

    async def _edit_unit(
        self,
        text: typing.Optional[str] = None,
        reply_markup: typing.Optional[ReplyMarkup] = None,
        *,
        photo: typing.Optional[str] = None,
        file: typing.Optional[str] = None,
        video: typing.Optional[str] = None,
        audio: typing.Optional[typing.Union[dict, str]] = None,
        gif: typing.Optional[str] = None,
        mime_type: typing.Optional[str] = None,
        force_me: typing.Optional[bool] = None,
        disable_security: typing.Optional[bool] = None,
        always_allow: typing.Optional[typing.List[int]] = None,
        disable_web_page_preview: bool = True,
        query: typing.Optional[CallbackQuery] = None,
        unit_id: typing.Optional[str] = None,
        inline_message_id: typing.Optional[str] = None,
        chat_id: typing.Optional[int] = None,
        message_id: typing.Optional[int] = None,
    ) -> bool:
        """
        Edits unit message
        :param text: Text of message
        :param reply_markup: Inline keyboard
        :param photo: Url to a valid photo to attach to message
        :param file: Url to a valid file to attach to message
        :param video: Url to a valid video to attach to message
        :param audio: Url to a valid audio to attach to message
        :param gif: Url to a valid gif to attach to message
        :param mime_type: Mime type of file
        :param force_me: Allow only owner to interact with buttons
        :param disable_security: Disable security check for buttons
        :param always_allow: List of user ids, which will always be allowed
        :param disable_web_page_preview: Disable web page preview
        :param query: Callback query
        :return: Status of edit
        """
        reply_markup = self._validate_markup(reply_markup) or []

        if text is not None and not isinstance(text, str):
            logger.error(
                "Invalid type for `text`. Expected `str`, got `%s`", type(text)
            )
            return False

        if file and not mime_type:
            logger.error(
                "You must pass `mime_type` along with `file` field\n"
                "It may be either 'application/zip' or 'application/pdf'"
            )
            return False

        if isinstance(audio, str):
            audio = {"url": audio}

        if isinstance(text, str):
            text = self.sanitise_text(text)

        media_params = [
            photo is None,
            gif is None,
            file is None,
            video is None,
            audio is None,
        ]

        if media_params.count(False) > 1:
            logger.error("You passed two or more exclusive parameters simultaneously")
            return False

        if unit_id is not None and unit_id in self._units:
            unit = self._units[unit_id]

            unit["buttons"] = reply_markup

            if isinstance(force_me, bool):
                unit["force_me"] = force_me

            if isinstance(disable_security, bool):
                unit["disable_security"] = disable_security

            if isinstance(always_allow, list):
                unit["always_allow"] = always_allow
        else:
            unit = {}

        kwargs = self._edit_kwargs(
            call=query,
            unit=unit,
            inline_message_id=inline_message_id,
            chat_id=chat_id,
            message_id=message_id,
        )

        if not kwargs:
            logger.warning(
                "Attempted to edit message with no `inline_message_id`. "
                "Possible reasons:\n"
                "- Form was sent without buttons and due to "
                "the limits of Telegram API can't be edited\n"
                "- There is an in-bot error, which you should report"
            )
            return False

        try:
            path = urlparse(photo).path
            ext = os.path.splitext(path)[1]
        except Exception:
            ext = None

        if photo is not None and ext in {".gif", ".mp4"}:
            gif = deepcopy(photo)
            photo = None

        media = next(
            (media for media in [photo, file, video, audio, gif] if media), None
        )

        if isinstance(media, bytes):
            media = io.BytesIO(media)
            media.name = "upload.mp4"

        if isinstance(media, io.BytesIO):
            media = BufferedInputFile(media.getvalue(), media.name)

        if file:
            media = InputMediaDocument(media=media, caption=text, parse_mode="HTML")
        elif photo:
            media = InputMediaPhoto(media=media, caption=text, parse_mode="HTML")
        elif audio:
            if isinstance(audio, dict):
                media = InputMediaAudio(
                    media=audio["url"],
                    title=audio.get("title"),
                    performer=audio.get("performer"),
                    duration=audio.get("duration"),
                    caption=text,
                    parse_mode="HTML",
                )
            else:
                media = InputMediaAudio(
                    media=audio,
                    caption=text,
                    parse_mode="HTML",
                )
        elif video:
            media = InputMediaVideo(media=media, caption=text, parse_mode="HTML")
        elif gif:
            media = InputMediaAnimation(media=media, caption=text, parse_mode="HTML")

        if media is None and text is None and reply_markup:
            try:
                await self.bot.edit_message_reply_markup(
                    **kwargs,
                    reply_markup=self.generate_markup(reply_markup),
                )
            except Exception:
                return False

            return True

        if media is None and text is None:
            logger.error("You must pass either `text` or `media` or `reply_markup`")
            return False

        if media is None:
            try:
                await self.bot.edit_message_text(
                    text,
                    **kwargs,
                    disable_web_page_preview=disable_web_page_preview,
                    reply_markup=self.generate_markup(
                        reply_markup
                        if isinstance(reply_markup, list)
                        else unit.get("buttons", [])
                    ),
                )
            except TelegramRetryAfter as e:
                logger.info("Sleeping %ss on aiogram FloodWait...", e.retry_after)
                await asyncio.sleep(e.retry_after)
                return await self._edit_unit(**utils.get_kwargs())
            except TelegramBadRequest as e:
                if "message is not modified" in str(e):
                    if query:
                        with contextlib.suppress(Exception):
                            await query.answer()

                    return False

                if "message to edit not found" in str(e) or (
                    "message can't be edited" in str(e)
                ):
                    with contextlib.suppress(Exception):
                        await query.answer(_EDIT_FAIL_ALERT)

                    return False

                if "There is no text in the message to edit" not in str(e):
                    raise

                try:
                    await self.bot.edit_message_caption(
                        caption=text,
                        **kwargs,
                        reply_markup=self.generate_markup(
                            reply_markup
                            if isinstance(reply_markup, list)
                            else unit.get("buttons", [])
                        ),
                    )
                except Exception:
                    return False
                else:
                    return True
            else:
                return True

        try:
            await self.bot.edit_message_media(
                **kwargs,
                media=media,
                reply_markup=self.generate_markup(
                    reply_markup
                    if isinstance(reply_markup, list)
                    else unit.get("buttons", [])
                ),
            )
        except TelegramRetryAfter as e:
            logger.info("Sleeping %ss on aiogram FloodWait...", e.retry_after)
            await asyncio.sleep(e.retry_after)
            return await self._edit_unit(**utils.get_kwargs())
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                if query:
                    with contextlib.suppress(Exception):
                        await query.answer()

                return False

            with contextlib.suppress(Exception):
                await query.answer(_EDIT_FAIL_ALERT)
            return False
        else:
            return True

    async def _delete_unit_message(
        self,
        call: typing.Optional[typing.Union[CallbackQuery, InlineCall]] = None,
        unit_id: typing.Optional[str] = None,
        chat_id: typing.Optional[int] = None,
        message_id: typing.Optional[int] = None,
        inline_message_id: typing.Optional[str] = None,
    ) -> bool:
        """Params `self`, `unit_id` are for internal use only, do not try to pass them"""
        if getattr(getattr(call, "message", None), "chat", None):
            try:
                await self.bot.delete_message(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                )
            except Exception:
                return False

            if unit_id:
                await self._unload_unit(unit_id)
            return True

        if chat_id and message_id:
            try:
                await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception:
                return False

            if unit_id:
                await self._unload_unit(unit_id)
            return True

        if not unit_id and getattr(call, "unit_id", None):
            unit_id = call.unit_id

        # Bot API can't delete messages sent via inline results —
        # edit them to a closed state instead
        unit = self._units.get(unit_id, {}) if unit_id else {}

        inline_message_id = (
            inline_message_id
            or getattr(call, "inline_message_id", None)
            or unit.get("inline_message_id")
        )

        if inline_message_id:
            try:
                await self.bot.edit_message_text(
                    "🔒 Closed",
                    inline_message_id=inline_message_id,
                )
            except Exception:
                return False

        if unit_id:
            await self._unload_unit(unit_id)
        return True

    async def _unload_unit(self, unit_id: str) -> bool:
        """Params `self`, `unit_id` are for internal use only, do not try to pass them"""
        try:
            if "on_unload" in self._units[unit_id] and callable(
                self._units[unit_id]["on_unload"]
            ):
                self._units[unit_id]["on_unload"]()

            if unit_id in self._units:
                del self._units[unit_id]
            else:
                return False
        except Exception:
            return False

        return True

    def build_pagination(
        self,
        callback: typing.Callable[[int], typing.Awaitable[typing.Any]],
        total_pages: int,
        unit_id: typing.Optional[str] = None,
        current_page: typing.Optional[int] = None,
    ) -> typing.List[typing.List[typing.Dict[str, typing.Any]]]:
        # Based on https://github.com/pystorage/pykeyboard/blob/master/pykeyboard/inline_pagination_keyboard.py#L4
        if current_page is None:
            current_page = self._units[unit_id]["current_index"] + 1

        if total_pages <= 5:
            return [
                [
                    (
                        {"text": str(number), "args": (number - 1,), "callback": callback}
                        if number != current_page
                        else {
                            "text": f"· {number} ·",
                            "args": (number - 1,),
                            "callback": callback,
                        }
                    )
                    for number in range(1, total_pages + 1)
                ]
            ]

        if current_page <= 3:
            return [
                [
                    (
                        {
                            "text": f"· {number} ·",
                            "args": (number - 1,),
                            "callback": callback,
                        }
                        if number == current_page
                        else (
                            {
                                "text": f"{number} ›",
                                "args": (number - 1,),
                                "callback": callback,
                            }
                            if number == 4
                            else (
                                {
                                    "text": f"{total_pages} »",
                                    "args": (total_pages - 1,),
                                    "callback": callback,
                                }
                                if number == 5
                                else {
                                    "text": str(number),
                                    "args": (number - 1,),
                                    "callback": callback,
                                }
                            )
                        )
                    )
                    for number in range(1, 6)
                ]
            ]

        if current_page > total_pages - 3:
            return [
                [
                    {"text": "« 1", "args": (0,), "callback": callback},
                    {
                        "text": f"‹ {total_pages - 3}",
                        "args": (total_pages - 4,),
                        "callback": callback,
                    },
                ]
                + [
                    (
                        {
                            "text": f"· {number} ·",
                            "args": (number - 1,),
                            "callback": callback,
                        }
                        if number == current_page
                        else {
                            "text": str(number),
                            "args": (number - 1,),
                            "callback": callback,
                        }
                    )
                    for number in range(total_pages - 2, total_pages + 1)
                ]
            ]

        return [
            [
                {"text": "« 1", "args": (0,), "callback": callback},
                {
                    "text": f"‹ {current_page - 1}",
                    "args": (current_page - 2,),
                    "callback": callback,
                },
                {
                    "text": f"· {current_page} ·",
                    "args": (current_page - 1,),
                    "callback": callback,
                },
                {
                    "text": f"{current_page + 1} ›",
                    "args": (current_page,),
                    "callback": callback,
                },
                {
                    "text": f"{total_pages} »",
                    "args": (total_pages - 1,),
                    "callback": callback,
                },
            ]
        ]

    def _validate_markup(
        self,
        buttons: typing.Optional[ReplyMarkup],
    ) -> typing.List[typing.List[typing.Dict[str, typing.Any]]]:
        if buttons is None:
            buttons = []

        if not isinstance(buttons, (list, dict)):
            logger.error(
                "Reply markup ommited because passed type is not valid (%s)",
                type(buttons),
            )
            return None

        buttons = self._normalize_markup(buttons)

        if not all(all(isinstance(button, dict) for button in row) for row in buttons):
            logger.error(
                "Reply markup ommited because passed invalid type for one of the"
                " buttons"
            )
            return None

        if not all(
            all(
                "url" in button
                or "callback" in button
                or "input" in button
                or "data" in button
                or "action" in button
                for button in row
            )
            for row in buttons
        ):
            logger.error(
                "Invalid button specified. "
                "Button must contain one of the following fields:\n"
                "  - `url`\n"
                "  - `callback`\n"
                "  - `input`\n"
                "  - `data`\n"
                "  - `action`"
            )
            return None

        return buttons
