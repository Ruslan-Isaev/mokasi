# Mokasi core module — bot settings
from aiogram.types import Message

from .. import loader, main, utils
from ..inline.types import InlineCall


@loader.tds
class SettingsMod(loader.Module):
    """Bot settings"""

    strings = {
        "name": "Settings",
        "settings_header": "⚙️ <b>Settings</b>",
        "prefix_title": "🎯 <b>Command prefix:</b> <code>{}</code>",
        "prefix_set": "✅ <b>Prefix set to</b> <code>{}</code>",
        "input_prefix": "Enter new prefix",
        "ratelimit_title": "⏱ <b>Ratelimit:</b> {} / {}",
        "input_ratelimit_user": "Enter max user ratelimit",
        "input_ratelimit_chat": "Enter max chat ratelimit",
        "set": "✅ <b>{}:</b> <code>{}</code>",
        "invalid": "🚫 <b>Invalid value:</b> <code>{}</code>",
    }

    strings_ru = {
        "name": "Настройки",
        "settings_header": "⚙️ <b>Настройки</b>",
        "prefix_title": "🎯 <b>Префикс команд:</b> <code>{}</code>",
        "prefix_set": "✅ <b>Префикс установлен:</b> <code>{}</code>",
        "input_prefix": "Введите новый префикс",
        "ratelimit_title": "⏱ <b>Ратлимит:</b> {} / {}",
        "input_ratelimit_user": "Введите максимальный ратлимит пользователя",
        "input_ratelimit_chat": "Введите максимальный ратлимит чата",
        "set": "✅ <b>{}:</b> <code>{}</code>",
        "invalid": "🚫 <b>Некорректное значение:</b> <code>{}</code>",
    }

    @loader.command()
    async def settingscmd(self, message: Message):
        """Open the settings menu"""
        await self.inline.form(
            self.strings("settings_header"),
            message,
            reply_markup=[
                [
                    {
                        "text": self.strings("prefix_title").format(
                            utils.escape_html(self.get_prefix())
                        ),
                        "callback": self.inline__prefix,
                    }
                ],
                [
                    {
                        "text": self.strings("ratelimit_title").format(
                            self._db.get(
                                "mokasi.dispatcher",
                                "ratelimit_max_user",
                                30,
                            ),
                            self._db.get(
                                "mokasi.dispatcher",
                                "ratelimit_max_chat",
                                100,
                            ),
                        ),
                        "callback": self.inline__ratelimit,
                    }
                ],
                [
                    {
                        "text": self._toggle_text(
                            "📜 Tracebacks in chat",
                            self._db.get(main.__name__, "inlinelogs", True),
                        ),
                        "callback": self.inline__toggle,
                        "args": (main.__name__, "inlinelogs", "📜 Tracebacks in chat"),
                    }
                ],
                [
                    {
                        "text": self._toggle_text(
                            "🛡 Core protection",
                            not self._db.get(
                                main.__name__,
                                "remove_core_protection",
                                False,
                            ),
                        ),
                        "callback": self.inline__toggle,
                        "args": (
                            main.__name__,
                            "remove_core_protection",
                            "🛡 Core protection",
                        ),
                    }
                ],
                [
                    {
                        "text": self._toggle_text(
                            "🔒 Secure boot",
                            self._db.get("mokasi.loader", "secure_boot", False),
                        ),
                        "callback": self.inline__toggle,
                        "args": (
                            "mokasi.loader",
                            "secure_boot",
                            "🔒 Secure boot",
                        ),
                    }
                ],
                [{"text": "🔻 Close", "action": "close"}],
            ],
        )

    @staticmethod
    def _toggle_text(title: str, state: bool) -> str:
        return f"{'✅' if state else '❌'} {title}"

    async def inline__prefix(self, call: InlineCall):
        await call.edit(
            self.strings("prefix_title").format(utils.escape_html(self.get_prefix())),
            reply_markup=[
                [
                    {
                        "text": "✍️ Edit",
                        "input": self.strings("input_prefix"),
                        "handler": self.inline__set_prefix,
                    }
                ],
                [{"text": "🔙 Back", "callback": self.inline__back}],
                [{"text": "🔻 Close", "action": "close"}],
            ],
        )

    async def inline__set_prefix(self, call: InlineCall, value: str):
        value = value.strip()

        if not value or len(value) > 3:
            await call.edit(
                self.strings("invalid").format(utils.escape_html(value)),
                reply_markup=[
                    [{"text": "🔙 Back", "callback": self.inline__back}],
                    [{"text": "🔻 Close", "action": "close"}],
                ],
            )
            return

        self._db.set(main.__name__, "command_prefix", value)
        await call.edit(self.strings("prefix_set").format(utils.escape_html(value)))

    async def inline__ratelimit(self, call: InlineCall):
        await call.edit(
            self.strings("ratelimit_title").format(
                self._db.get("mokasi.dispatcher", "ratelimit_max_user", 30),
                self._db.get("mokasi.dispatcher", "ratelimit_max_chat", 100),
            ),
            reply_markup=[
                [
                    {
                        "text": "✍️ User limit",
                        "input": self.strings("input_ratelimit_user"),
                        "handler": self.inline__set_ratelimit_user,
                    },
                    {
                        "text": "✍️ Chat limit",
                        "input": self.strings("input_ratelimit_chat"),
                        "handler": self.inline__set_ratelimit_chat,
                    },
                ],
                [{"text": "🔙 Back", "callback": self.inline__back}],
                [{"text": "🔻 Close", "action": "close"}],
            ],
        )

    async def inline__set_ratelimit_user(self, call: InlineCall, value: str):
        try:
            value = int(value.strip())
        except ValueError:
            await call.answer(self.strings("invalid").format(value), show_alert=True)
            return

        self._db.set("mokasi.dispatcher", "ratelimit_max_user", value)
        await self.inline__ratelimit(call)

    async def inline__set_ratelimit_chat(self, call: InlineCall, value: str):
        try:
            value = int(value.strip())
        except ValueError:
            await call.answer(self.strings("invalid").format(value), show_alert=True)
            return

        self._db.set("mokasi.dispatcher", "ratelimit_max_chat", value)
        await self.inline__ratelimit(call)

    async def inline__toggle(self, call: InlineCall, owner: str, key: str, title: str):
        state = not bool(self._db.get(owner, key, False))
        self._db.set(owner, key, state)

        if key == "inlinelogs":
            self._db.set(owner, key, state)

        await self.inline__back(call)

    async def inline__back(self, call: InlineCall):
        await call.edit(
            self.strings("settings_header"),
            reply_markup=[
                [
                    {
                        "text": self.strings("prefix_title").format(
                            utils.escape_html(self.get_prefix())
                        ),
                        "callback": self.inline__prefix,
                    }
                ],
                [
                    {
                        "text": self.strings("ratelimit_title").format(
                            self._db.get(
                                "mokasi.dispatcher",
                                "ratelimit_max_user",
                                30,
                            ),
                            self._db.get(
                                "mokasi.dispatcher",
                                "ratelimit_max_chat",
                                100,
                            ),
                        ),
                        "callback": self.inline__ratelimit,
                    }
                ],
                [
                    {
                        "text": self._toggle_text(
                            "📜 Tracebacks in chat",
                            self._db.get(main.__name__, "inlinelogs", True),
                        ),
                        "callback": self.inline__toggle,
                        "args": (main.__name__, "inlinelogs", "📜 Tracebacks in chat"),
                    }
                ],
                [
                    {
                        "text": self._toggle_text(
                            "🛡 Core protection",
                            not self._db.get(
                                main.__name__,
                                "remove_core_protection",
                                False,
                            ),
                        ),
                        "callback": self.inline__toggle,
                        "args": (
                            main.__name__,
                            "remove_core_protection",
                            "🛡 Core protection",
                        ),
                    }
                ],
                [
                    {
                        "text": self._toggle_text(
                            "🔒 Secure boot",
                            self._db.get("mokasi.loader", "secure_boot", False),
                        ),
                        "callback": self.inline__toggle,
                        "args": (
                            "mokasi.loader",
                            "secure_boot",
                            "🔒 Secure boot",
                        ),
                    }
                ],
                [{"text": "🔻 Close", "action": "close"}],
            ],
        )
