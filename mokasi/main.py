# Mokasi — a modular personal Telegram bot framework
# Boot sequence, ported from Hikka (https://github.com/hikariatama/Hikka)
# and adapted for aiogram 3: single Bot, single Router with 4 catch-alls
import asyncio
import contextlib
import json
import logging
import os
import sys
import time
import typing
from pathlib import Path

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from aiogram.types import (
    CallbackQuery,
    ChosenInlineResult,
    InlineQuery,
    Message,
)

from . import utils
from .database import Database
from .dispatcher import CommandDispatcher
from .loader import Modules
from .translations import Translator

BASE_PATH = os.path.normpath(os.path.join(utils.get_base_dir(), ".."))

logger = logging.getLogger(__name__)


def get_config_key(key: str) -> typing.Any:
    """Read a key from the static config.json"""
    try:
        return json.loads((Path(BASE_PATH) / "config.json").read_text()).get(key)
    except Exception:
        return None


def save_config_key(key: str, value: typing.Any):
    """Write a key to the static config.json"""
    path = Path(BASE_PATH) / "config.json"
    try:
        config = json.loads(path.read_text())
    except Exception:
        config = {}

    config[key] = value
    path.write_text(json.dumps(config, indent=4))


class Mokasi:
    def __init__(self):
        self.start_time = time.time()

        # The token is read from the environment or config.json.
        # It is never written back to disk automatically — if you passed
        # it via MOKASI_TOKEN, it stays in the environment only.
        self.token = os.environ.get("MOKASI_TOKEN") or get_config_key("token")

        self.owner: typing.Optional[int] = None
        raw_owner = os.environ.get("MOKASI_OWNER") or get_config_key("owner")
        if raw_owner is not None:
            with contextlib.suppress(Exception):
                self.owner = int(str(raw_owner).strip())

    async def _main(self):
        if not self.token:
            print(
                "🚫 Bot token is not set!\n\n"
                "Set the MOKASI_TOKEN environment variable or add "
                '"token": "123456:ABC-DEF..." to config.json\n'
                "You can get the token from @BotFather",
                file=sys.stderr,
            )
            sys.exit(2)

        try:
            bot = Bot(
                token=self.token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
        except Exception:
            logger.critical("Bot token is invalid, exiting")
            sys.exit(2)

        self.bot = bot

        try:
            await bot.get_me()
        except TelegramUnauthorizedError:
            logger.critical("Bot token is invalid, exiting")
            with contextlib.suppress(Exception):
                await bot.session.close()
            sys.exit(2)

        db = Database(bot, Path(BASE_PATH))
        await db.init()

        translator = Translator(bot, db)
        await translator.init()

        modules = Modules(bot, db, translator)

        if self.owner:
            modules.security.seed_owner(self.owner)

        dispatcher = CommandDispatcher(modules, bot, db)
        await dispatcher.init()

        await modules.inline.init()

        router = Router()

        @router.message()
        async def handle_message(message: Message):
            await dispatcher.handle_message(message)

        @router.callback_query()
        async def handle_callback(call: CallbackQuery):
            await modules.inline._callback_query_handler(call)

        @router.inline_query()
        async def handle_inline_query(query: InlineQuery):
            await modules.inline._inline_handler(query)

        @router.chosen_inline_result()
        async def handle_chosen_inline_result(chosen: ChosenInlineResult):
            await modules.inline._chosen_inline_handler(chosen)

        await modules.register_all()
        modules.send_config()
        await modules.send_ready()

        logger.info(
            "Mokasi is ready! Loaded %s modules, %s commands",
            len(modules.modules),
            len(modules.commands),
        )

        dp = Dispatcher()
        dp.include_router(router)

        try:
            await dp.start_polling(bot, handle_signals=True)
        except TelegramConflictError:
            logger.critical(
                "Another instance of the bot is polling! "
                "Terminate it and restart mokasi."
            )
        finally:
            # Graceful shutdown: unload modules and save the database
            for mod in modules.modules:
                with contextlib.suppress(Exception):
                    await mod.on_unload()

            db.save()
            await bot.session.close()


mokasi = Mokasi()
