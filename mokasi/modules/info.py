# Mokasi core module — bot info (inline_everyone demo)
from aiogram.types import Message

from .. import loader, utils, version
from ..inline.types import InlineQuery


@loader.tds
class InfoMod(loader.Module):
    """Show bot info"""

    strings = {
        "name": "Info",
        "_cfg_cst_msg": "Custom message appended to the info",
        "_cfg_cst_btn": "Custom button (text and url)",
        "_cfg_banner": "Banner image url",
        "send_info": "🌘 Send bot info",
        "description": "Send info about the bot",
        "no_msg": "ℹ️ <b>No custom message set</b>",
    }

    strings_ru = {
        "name": "Инфо",
        "_cfg_cst_msg": "Пользовательское сообщение, добавляемое к инфо",
        "_cfg_cst_btn": "Пользовательская кнопка (текст и ссылка)",
        "_cfg_banner": "Ссылка на баннер",
        "send_info": "🌘 Отправить инфо о боте",
        "description": "Отправить информацию о боте",
        "no_msg": "ℹ️ <b>Пользовательское сообщение не задано</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "custom_message",
                doc=lambda: self.strings("_cfg_cst_msg"),
            ),
            loader.ConfigValue(
                "custom_button",
                ["🤖 Mokasi", "https://github.com"],
                lambda: self.strings("_cfg_cst_btn"),
                validator=loader.validators.Union(
                    loader.validators.Series(fixed_len=2),
                    loader.validators.NoneType(),
                ),
            ),
            loader.ConfigValue(
                "banner_url",
                "https://img.icons8.com/fluency/452/moon-satellite.png",
                lambda: self.strings("_cfg_banner"),
                validator=loader.validators.Link(),
            ),
        )

    def _render_info(self) -> str:
        ver = ".".join(map(str, version.__version__))
        return (
            "🌘 <b>Mokasi</b>\n\n"
            f"<b>Version:</b> <code>{ver}</code>\n"
            f"<b>Modules:</b> <code>{len(self.allmodules.modules)}</code>\n"
            f"<b>Commands:</b> <code>{len(self.allmodules.commands)}</code>\n"
            f"<b>Inline handlers:</b> <code>{len(self.allmodules.inline_handlers)}</code>\n"
            f"<b>Uptime:</b> <code>{utils.formatted_uptime()}</code>\n"
            f"<b>RAM:</b> <code>{utils.get_ram_usage()} MB</code>"
            + (
                "\n\n" + self.config["custom_message"]
                if self.config["custom_message"]
                else ""
            )
        )

    def _get_mark(self) -> list:
        if not self.config["custom_button"]:
            return []

        return [
            [
                {
                    "text": self.config["custom_button"][0],
                    "url": self.config["custom_button"][1],
                }
            ]
        ]

    @loader.inline_handler(
        thumb_url="https://img.icons8.com/external-others-inmotus-design/344/external-Moon-round-icons-others-inmotus-design-2.png"
    )
    @loader.inline_everyone
    async def info(self, _: InlineQuery) -> dict:
        """Send bot info (available for everyone — inline_everyone demo)"""
        return {
            "title": self.strings("send_info"),
            "description": self.strings("description"),
            "message": self._render_info(),
            "thumb": "https://img.icons8.com/external-others-inmotus-design/344/external-Moon-round-icons-others-inmotus-design-2.png",
            "reply_markup": self._get_mark(),
        }

    @loader.command()
    async def infocmd(self, message: Message):
        """Send bot info as an inline form"""
        await self.inline.form(
            text=self._render_info(),
            message=message,
            photo=self.config["banner_url"],
            reply_markup=self._get_mark(),
        )
