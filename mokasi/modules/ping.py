# Mokasi core module — basic bot info
import time

from aiogram.types import Message

from .. import loader, utils


@loader.tds
class PingMod(loader.Module):
    """Check bot latency"""

    strings = {
        "name": "Ping",
        "pong": "🏓 <b>Pong!</b>\n\n⏱ <b>Latency:</b> <code>{latency}</code>\n"
        "⏳ <b>Uptime:</b> <code>{uptime}</code>\n"
        "💾 <b>RAM:</b> <code>{ram} MB</code>",
    }

    strings_ru = {
        "name": "Пинг",
        "pong": "🏓 <b>Понг!</b>\n\n⏱ <b>Задержка:</b> <code>{latency}</code>\n"
        "⏳ <b>Аптайм:</b> <code>{uptime}</code>\n"
        "💾 <b>ОЗУ:</b> <code>{ram} МБ</code>",
    }

    @loader.command()
    async def pingcmd(self, message: Message):
        """Check bot latency, uptime and RAM usage"""
        start = time.time()
        msg = await utils.answer(message, "<b>🏓 Pong...</b>")

        latency = round((time.time() - start) * 1000, 2)

        await msg.edit_text(
            self.strings("pong").format(
                latency=f"{latency} ms",
                uptime=utils.formatted_uptime(),
                ram=utils.get_ram_usage(),
            )
        )
