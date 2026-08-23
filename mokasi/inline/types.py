# Mokasi — a modular personal Telegram bot
# Inline wrappers
# and reworked for aiogram 3: composition instead of subclassing
# (aiogram 3 types are pydantic models)
import logging
import typing

from aiogram.types import CallbackQuery
from aiogram.types import InlineQuery as AiogramInlineQuery
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

from .. import utils

logger = logging.getLogger(__name__)


class InlineMessage:
    """Wrapper around a bot message, sent with inline keyboard"""

    def __init__(
        self,
        inline_manager: "InlineManager",  # type: ignore  # noqa: F821
        unit_id: str,
        chat_id: typing.Optional[int] = None,
        message_id: typing.Optional[int] = None,
        inline_message_id: typing.Optional[str] = None,
    ):
        self.inline_message_id = inline_message_id
        self.chat_id = chat_id
        self.message_id = message_id
        self.unit_id = unit_id
        self.inline_manager = inline_manager
        self._units = inline_manager._units

    @property
    def form(self) -> dict:
        """Live view of the unit dict"""
        return (
            {"id": self.unit_id, **self._units[self.unit_id]}
            if self.unit_id in self._units
            else {}
        )

    async def edit(self, *args, **kwargs) -> "InlineMessage":
        if "unit_id" in kwargs:
            kwargs.pop("unit_id")

        if "inline_message_id" in kwargs:
            kwargs.pop("inline_message_id")

        if "chat_id" in kwargs:
            kwargs.pop("chat_id")

        if "message_id" in kwargs:
            kwargs.pop("message_id")

        return await self.inline_manager._edit_unit(
            *args,
            unit_id=self.unit_id,
            chat_id=self.chat_id,
            message_id=self.message_id,
            inline_message_id=self.inline_message_id,
            **kwargs,
        )

    async def delete(self) -> bool:
        return await self.inline_manager._delete_unit_message(
            unit_id=self.unit_id,
            chat_id=self.chat_id,
            message_id=self.message_id,
            inline_message_id=self.inline_message_id,
        )

    async def unload(self) -> bool:
        return await self.inline_manager._unload_unit(unit_id=self.unit_id)


class InlineCall:
    """Wrapper around aiogram CallbackQuery with unit edit/delete/unload methods"""

    def __init__(
        self,
        call: CallbackQuery,
        inline_manager: "InlineManager",  # type: ignore  # noqa: F821
        unit_id: typing.Optional[str] = None,
    ):
        self._call = call
        self.inline_manager = inline_manager
        self.unit_id = unit_id
        self._units = inline_manager._units

        if getattr(getattr(call, "message", None), "chat", None):
            self.chat_id = call.message.chat.id
            self.message_id = call.message.message_id
            self.inline_message_id = None
        else:
            self.chat_id = None
            self.message_id = None
            self.inline_message_id = call.inline_message_id

    def __getattr__(self, item: str) -> typing.Any:
        # Delegate unknown attributes to the wrapped CallbackQuery
        # (id, from_user, message, data, answer, bot, ...)
        return getattr(self._call, item)

    @property
    def form(self) -> dict:
        """Live view of the unit dict"""
        return (
            {"id": self.unit_id, **self._units[self.unit_id]}
            if self.unit_id and self.unit_id in self._units
            else {}
        )

    async def edit(self, *args, **kwargs) -> bool:
        if "unit_id" in kwargs:
            kwargs.pop("unit_id")

        if "inline_message_id" in kwargs:
            kwargs.pop("inline_message_id")

        if "chat_id" in kwargs:
            kwargs.pop("chat_id")

        if "message_id" in kwargs:
            kwargs.pop("message_id")

        return await self.inline_manager._edit_unit(
            *args,
            unit_id=self.unit_id,
            chat_id=self.chat_id,
            message_id=self.message_id,
            inline_message_id=self.inline_message_id,
            **kwargs,
        )

    async def delete(self) -> bool:
        return await self.inline_manager._delete_unit_message(
            unit_id=self.unit_id,
            chat_id=self.chat_id,
            message_id=self.message_id,
            inline_message_id=self.inline_message_id,
        )

    async def unload(self) -> bool:
        return await self.inline_manager._unload_unit(unit_id=self.unit_id)


class InlineUnit:
    """InlineManager extension type. For internal use only"""

    def __init__(self):
        """Made just for type specification"""


class InlineQuery:
    """Wrapper around aiogram InlineQuery with args and canned error answers"""

    def __init__(self, inline_query: AiogramInlineQuery):
        self._query = inline_query
        self.args = (
            inline_query.query.split(maxsplit=1)[1]
            if len(inline_query.query.split()) > 1
            else ""
        )

    def __getattr__(self, item: str) -> typing.Any:
        # Delegate unknown attributes to the wrapped InlineQuery
        # (id, from_user, answer, ...)
        return getattr(self._query, item)

    @staticmethod
    def _get_res(title: str, description: str, thumb_url: str) -> list:
        return [
            InlineQueryResultArticle(
                id=utils.rand(20),
                title=title,
                description=description,
                input_message_content=InputTextMessageContent(message_text=
                    "😶‍🌫️ <i>There is nothing here...</i>",
                    parse_mode="HTML",
                ),
                thumbnail_url=thumb_url,
                thumbnail_width=128,
                thumbnail_height=128,
            )
        ]

    async def e400(self):
        await self._query.answer(
            self._get_res(
                "🚫 400",
                (
                    "Bad request. You need to pass right arguments, follow module's"
                    " documentation"
                ),
                "https://img.icons8.com/color/344/swearing-male--v1.png",
            ),
            cache_time=0,
        )

    async def e403(self):
        await self._query.answer(
            self._get_res(
                "🚫 403",
                "You have no permissions to access this result",
                "https://img.icons8.com/external-wanicon-flat-wanicon/344/external-forbidden-new-normal-wanicon-flat-wanicon.png",
            ),
            cache_time=0,
        )

    async def e404(self):
        await self._query.answer(
            self._get_res(
                "🚫 404",
                "No results found",
                "https://img.icons8.com/external-justicon-flat-justicon/344/external-404-error-responsive-web-design-justicon-flat-justicon.png",
            ),
            cache_time=0,
        )

    async def e500(self):
        await self._query.answer(
            self._get_res(
                "🚫 500",
                "Internal bot error while processing request. More info in logs",
                "https://img.icons8.com/external-vitaliy-gorbachev-flat-vitaly-gorbachev/344/external-error-internet-security-vitaliy-gorbachev-flat-vitaly-gorbachev.png",
            ),
            cache_time=0,
        )
