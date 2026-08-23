# Mokasi — a modular personal Telegram bot
# Command dispatcher
# and adapted for aiogram 3
import asyncio
import collections
import contextlib
import copy
import inspect
import logging
import re
import sys
import traceback
import typing

from aiogram.types import Message

from . import security, utils
from .database import Database
from .loader import Modules

logger = logging.getLogger(__name__)

ALL_TAGS = [
    "no_commands",
    "only_commands",
    "no_media",
    "only_media",
    "only_photos",
    "only_videos",
    "only_audios",
    "only_stickers",
    "only_docs",
    "only_pm",
    "no_pm",
    "no_channels",
    "no_groups",
    "only_groups",
    "no_forwards",
    "only_forwards",
    "no_reply",
    "only_reply",
    "startswith",
    "endswith",
    "contains",
    "regex",
    "filter",
    "from_id",
    "chat_id",
]


def _decrement_ratelimit(delay, data, key, severity):
    def inner():
        data[key] = max(0, data[key] - severity)

    asyncio.get_running_loop().call_later(delay, inner)


class CommandDispatcher:
    def __init__(
        self,
        modules: Modules,
        client: "aiogram.Bot",  # type: ignore  # noqa: F821
        db: Database,
    ):
        self._modules = modules
        self._client = client
        self.client = client
        self._db = db

        self._ratelimit_storage_user = collections.defaultdict(int)
        self._ratelimit_storage_chat = collections.defaultdict(int)
        self._ratelimit_max_user = db.get(__name__, "ratelimit_max_user", 30)
        self._ratelimit_max_chat = db.get(__name__, "ratelimit_max_chat", 100)

        self.security = modules.security

        self.check_security = self.security.check
        self._cached_usernames = []
        self._me = client.id

    async def init(self):
        """Resolve bot username (must be called after bot.get_me())"""
        me = await self._client.get_me()
        self._cached_usernames = [me.username.lower()] if me.username else []

    async def _handle_ratelimit(self, message: Message, func: callable) -> bool:
        if await self.security.check(message, security.OWNER):
            return True

        func = getattr(func, "__func__", func)
        ret = True
        chat = self._ratelimit_storage_chat[message.chat.id]

        if message.from_user:
            user = self._ratelimit_storage_user[message.from_user.id]
            severity = (5 if getattr(func, "ratelimit", False) else 2) * (
                (user + chat) // 30 + 1
            )
            user += severity
            self._ratelimit_storage_user[message.from_user.id] = user
            if user > self._ratelimit_max_user:
                ret = False
            else:
                self._ratelimit_storage_chat[message.chat.id] = chat

            _decrement_ratelimit(
                self._ratelimit_max_user * severity,
                self._ratelimit_storage_user,
                message.from_user.id,
                severity,
            )
        else:
            severity = (5 if getattr(func, "ratelimit", False) else 2) * (
                chat // 15 + 1
            )

        chat += severity

        if chat > self._ratelimit_max_chat:
            ret = False

        _decrement_ratelimit(
            self._ratelimit_max_chat * severity,
            self._ratelimit_storage_chat,
            message.chat.id,
            severity,
        )

        return ret

    async def _handle_command(
        self,
        message: Message,
        watcher: bool = False,
    ) -> typing.Union[bool, typing.Tuple[Message, str, str, callable]]:
        text = message.text or message.caption or ""

        if not text:
            return False

        prefix = self._db.get("mokasi.main", "command_prefix", False) or "/"

        if not text.startswith(prefix) or len(text) == len(prefix):
            return False

        if (
            message.via_bot
            or getattr(message, "sticker", None)
            or getattr(message, "dice", None)
        ):
            return False

        blacklist_chats = self._db.get("mokasi.main", "blacklist_chats", [])
        whitelist_chats = self._db.get("mokasi.main", "whitelist_chats", [])
        whitelist_modules = self._db.get("mokasi.main", "whitelist_modules", [])

        if utils.get_chat_id(message) in blacklist_chats or (
            whitelist_chats and utils.get_chat_id(message) not in whitelist_chats
        ):
            return False

        initiator = getattr(getattr(message, "from_user", None), "id", 0)

        command = text[len(prefix) :].strip().split(maxsplit=1)[0]
        tag = command.split("@", maxsplit=1)

        if len(tag) == 2:
            if tag[1].lower() not in self._cached_usernames:
                # Command addressed to another bot
                return False

        txt, func = self._modules.dispatch(tag[0])

        if (
            not func
            or not await self._handle_ratelimit(message, func)
            or not await self.security.check(
                message,
                func,
            )
        ):
            return False

        if (
            f"{str(utils.get_chat_id(message))}.{func.__self__.__module__}"
            in blacklist_chats
            or whitelist_modules
            and f"{utils.get_chat_id(message)}.{func.__self__.__module__}"
            not in whitelist_modules
        ):
            return False

        if await self._handle_tags(message, func):
            return False

        return message, prefix, txt, func

    async def handle_message(self, message: Message):
        """Handle all incoming messages"""
        # Commands
        command = await self._handle_command(message)
        if command:
            message, _, _, func = command

            asyncio.ensure_future(
                self.future_dispatcher(
                    func,
                    message,
                    self.command_exc,
                )
            )

        # Watchers
        await self.handle_incoming(message)

    async def command_exc(self, _, message: Message):
        """Handle command exceptions."""
        exc = sys.exc_info()[1]
        logger.exception("Command failed", extra={"stack": inspect.stack()})
        cmd = utils.escape_html(message.text or message.caption or "")
        if not self._db.get("mokasi.main", "inlinelogs", True):
            txt = (
                "🚫 <b>Call</b>"
                f" <code>{cmd}</code><b>"
                " failed!</b>"
            )
        else:
            exc = "\n".join(traceback.format_exc().splitlines()[1:])
            txt = (
                "🚫 <b>Call</b>"
                f" <code>{cmd}</code><b>"
                " failed!</b>\n\n<b>🧾"
                f" Logs:</b>\n<code>{utils.escape_html(exc)}</code>"
            )

        with contextlib.suppress(Exception):
            await utils.answer(message, txt)

    async def watcher_exc(self, *_):
        logger.exception("Error running watcher", extra={"stack": inspect.stack()})

    async def _handle_tags(
        self,
        message: Message,
        func: callable,
    ) -> bool:
        return bool(await self._handle_tags_ext(message, func))

    async def _handle_tags_ext(
        self,
        message: Message,
        func: callable,
    ) -> str:
        """
        Handle tags.
        :param message: The message to handle.
        :param func: The function to handle.
        :return: The reason for the tag to fail.
        """
        m = message

        text = m.text or m.caption or ""
        chat_type = getattr(m.chat, "type", None)
        content_type = getattr(m, "content_type", None)

        reverse_mapping = {
            "no_media": lambda: content_type == "text",
            "only_media": lambda: content_type != "text",
            "only_photos": lambda: bool(getattr(m, "photo", None)),
            "only_videos": lambda: content_type in {"video", "video_note"},
            "only_audios": lambda: content_type in {"audio", "voice"},
            "only_stickers": lambda: bool(getattr(m, "sticker", None)),
            "only_docs": lambda: bool(getattr(m, "document", None)),
            "only_pm": lambda: chat_type == "private",
            "no_pm": lambda: chat_type != "private",
            "no_channels": lambda: chat_type != "channel",
            "no_groups": lambda: chat_type not in {"group", "supergroup"},
            "only_groups": lambda: chat_type in {"group", "supergroup"},
            "no_forwards": lambda: not m.forward_origin,
            "only_forwards": lambda: bool(m.forward_origin),
            "no_reply": lambda: not m.reply_to_message,
            "only_reply": lambda: bool(m.reply_to_message),
            "startswith": lambda: text.startswith(func.startswith),
            "endswith": lambda: text.endswith(func.endswith),
            "contains": lambda: func.contains in text,
            "filter": lambda: callable(func.filter) and func.filter(m),
            "from_id": lambda: getattr(m.from_user, "id", None) == func.from_id,
            "chat_id": lambda: utils.get_chat_id(m) == (
                func.chat_id
                if not str(func.chat_id).startswith("-100")
                else int(str(func.chat_id)[4:])
            ),
            "regex": lambda: re.search(func.regex, text),
        }

        return (
            "no_commands"
            if getattr(func, "no_commands", False)
            and await self._handle_command(m, watcher=True)
            else (
                "only_commands"
                if getattr(func, "only_commands", False)
                and not await self._handle_command(m, watcher=True)
                else next(
                    (
                        tag
                        for tag in ALL_TAGS
                        if getattr(func, tag, False)
                        and tag in reverse_mapping
                        and not reverse_mapping[tag]()
                    ),
                    None,
                )
            )
        )

    async def handle_incoming(self, message: Message):
        """Handle watchers"""
        blacklist_chats = self._db.get("mokasi.main", "blacklist_chats", [])
        whitelist_chats = self._db.get("mokasi.main", "whitelist_chats", [])
        whitelist_modules = self._db.get("mokasi.main", "whitelist_modules", [])

        if utils.get_chat_id(message) in blacklist_chats or (
            whitelist_chats and utils.get_chat_id(message) not in whitelist_chats
        ):
            logger.debug("Message is blacklisted")
            return

        for func in self._modules.watchers:
            bl = self._db.get("mokasi.main", "disabled_watchers", {})
            modname = str(func.__self__.__class__.strings["name"])

            if (
                modname in bl
                and (
                    "*" in bl[modname]
                    or utils.get_chat_id(message) in bl[modname]
                    or "only_chats" in bl[modname]
                    and message.chat.type == "private"
                    or "only_pm" in bl[modname]
                    and message.chat.type != "private"
                )
                or f"{str(utils.get_chat_id(message))}.{func.__self__.__module__}"
                in blacklist_chats
                or whitelist_modules
                and f"{str(utils.get_chat_id(message))}.{func.__self__.__module__}"
                not in whitelist_modules
                or await self._handle_tags(message, func)
            ):
                logger.debug(
                    "Ignored watcher of module %s because of %s",
                    modname,
                    await self._handle_tags_ext(message, func),
                )
                continue

            # Run watcher via ensure_future so in case user has a lot
            # of watchers with long actions, they can run simultaneously
            asyncio.ensure_future(
                self.future_dispatcher(
                    func,
                    message,
                    self.watcher_exc,
                )
            )

    async def future_dispatcher(
        self,
        func: callable,
        message: Message,
        exception_handler: callable,
        *args,
    ):
        try:
            await func(message)
        except Exception as e:
            await exception_handler(e, message, *args)
