# Mokasi — a modular personal Telegram bot
# Inline manager
# The manager uses the shared aiogram Bot — no polling of its own,
# handlers are registered in the single Router
"""Inline buttons, galleries and other Telegram-Bot-API stuff"""

import asyncio
import logging
import time
import typing

from ..database import Database
from ..translations import Translator
from .events import Events
from .form import Form
from .gallery import Gallery
from .list import List
from .utils import Utils

logger = logging.getLogger(__name__)


class InlineManager(
    Utils,
    Events,
    Form,
    Gallery,
    List,
):
    """
    Inline buttons, galleries and other Telegram-Bot-API stuff
    :param bot: aiogram Bot instance
    :param db: Database instance
    :param allmodules: All modules
    :param security: SecurityManager instance
    """

    def __init__(
        self,
        bot: "aiogram.Bot",  # type: ignore  # noqa: F821
        db: Database,
        allmodules: "Modules",  # type: ignore  # noqa: F821
        security: "SecurityManager",  # type: ignore  # noqa: F821
    ):
        """Initialize InlineManager to create forms"""
        self.bot = bot
        self._client = bot
        self._db = db
        self._allmodules = allmodules
        self.security = security
        self.translator: Translator = allmodules.translator

        self._units: typing.Dict[str, dict] = {}
        self._custom_map: typing.Dict[str, callable] = {}

        self._markup_ttl = 60 * 60 * 24
        self.init_complete = False

        self.bot_username: typing.Optional[str] = None
        self.bot_id: typing.Optional[int] = None

    async def init(self):
        """Resolve bot info (must be called after bot.get_me())"""
        self.bot_id = self.bot.id
        self.bot_username = (await self.bot.get_me()).username
        self.init_complete = True
        asyncio.ensure_future(self._cleaner())

    async def _cleaner(self):
        """Cleans outdated inline units"""
        while True:
            for unit_id, unit in self._units.copy().items():
                if (unit.get("ttl") or (time.time() + self._markup_ttl)) < time.time():
                    del self._units[unit_id]

            await asyncio.sleep(5)
