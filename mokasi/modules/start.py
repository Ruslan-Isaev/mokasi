# Mokasi core module — owner claim and greeting
import asyncio

from aiogram.types import Message

from .. import loader, main, utils

_claim_lock = asyncio.Lock()


@loader.tds
class StartMod(loader.Module):
    """Bot greeting and one-time owner claim"""

    strings = {
        "name": "Start",
        "claimed": (
            "🔐 <b>You have claimed this bot!</b>\n\n"
            "⚠️ <b>Important:</b> this is a <b>one-time claim</b>. "
            "From now on only you and the users you add via <code>/owneradd</code> "
            "can control this bot. This cannot be undone from Telegram.\n\n"
            "Type <code>/help</code> to see available commands."
        ),
        "greeting": (
            "👋 <b>Hello!</b>\n\n"
            "This is <b>Mokasi</b> — your personal modular bot.\n"
            "Type <code>/help</code> to see available commands."
        ),
        "not_owner": (
            "🚫 <b>You are not an owner of this bot.</b>\n\n"
            "If this is your bot and you lost access, set the owner in "
            "<code>config.json</code> or via <code>MOKASI_OWNER</code> "
            "environment variable."
        ),
    }

    strings_ru = {
        "name": "Старт",
        "claimed": (
            "🔐 <b>Вы завладели этим ботом!</b>\n\n"
            "⚠️ <b>Важно:</b> это <b>одноразовое действие</b>. "
            "Теперь только вы и пользователи, добавленные через "
            "<code>/owneradd</code>, могут управлять этим ботом. "
            "Отменить это через Telegram нельзя.\n\n"
            "Введите <code>/help</code>, чтобы увидеть доступные команды."
        ),
        "greeting": (
            "👋 <b>Привет!</b>\n\n"
            "Это <b>Mokasi</b> — ваш личный модульный бот.\n"
            "Введите <code>/help</code>, чтобы увидеть доступные команды."
        ),
        "not_owner": (
            "🚫 <b>Вы не являетесь владельцем этого бота.</b>\n\n"
            "Если это ваш бот и вы потеряли доступ, задайте владельца в "
            "<code>config.json</code> или через переменную окружения "
            "<code>MOKASI_OWNER</code>."
        ),
    }

    @loader.unrestricted
    @loader.command()
    async def startcmd(self, message: Message):
        """Greet the user or claim the bot (one-time)"""
        user_id = getattr(message.from_user, "id", None)

        if user_id is None:
            return

        owners = self._db.pointer("mokasi.security", "owner", [])

        def human_owners() -> list:
            return [owner for owner in owners if owner != self.bot_id]

        if not human_owners():
            async with _claim_lock:
                if not human_owners():
                    owners.append(user_id)
                    main.save_config_key("owner", user_id)
                    await utils.answer(message, self.strings("claimed"))
                    return

        if user_id not in owners:
            await utils.answer(message, self.strings("not_owner"))
            return

        await utils.answer(message, self.strings("greeting"))
