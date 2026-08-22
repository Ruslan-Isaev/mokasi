# Mokasi example module
#
# Install it with:
#   /loadmod <reply to this file>
#   /loadmod <url to this file>
#
# Every module is a class inheriting `loader.Module`.
# Method names ending with `cmd` become commands, `_inline_handler` —
# inline query handlers, `_callback_handler` — global callback handlers,
# `watcher` — watchers.
import asyncio

from aiogram.types import Message

from .. import loader, utils
from ..inline.types import InlineCall, InlineQuery


@loader.tds
class ExampleMod(loader.Module):
    """Example module to demonstrate the mokasi API"""

    # REQUIRED: display name of the module
    strings = {"name": "Example"}

    # Optional: Russian strings. Used when the language is set to "ru"
    strings_ru = {"name": "Пример"}

    def __init__(self):
        # Declare the config here — it is validated and auto-saved
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "enabled",
                True,
                lambda: self.strings("_cfg_enabled"),
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "whitelist",
                [123456789],
                lambda: self.strings("_cfg_whitelist"),
                validator=loader.validators.Series(
                    validator=loader.validators.TelegramID()
                ),
            ),
        )

    async def client_ready(self, client, db):
        # Called after the bot is fully ready (config is loaded by now)
        self.set("started_at", 0)

    async def on_unload(self):
        # Cleanup on module unload
        pass

    @loader.command(alias="ex")
    async def examplecmd(self, message: Message):
        """Show an example of an inline form"""
        # utils.answer replies/edits the message. If `reply_markup` is passed,
        # an inline form is sent instead
        await utils.answer(
            message,
            "<b>Hello from ExampleMod!</b>",
            reply_markup=[
                [
                    {
                        "text": "✅ Approve",
                        "callback": self._approve,
                        "args": (123,),
                    },
                    {
                        "text": "🔻 Close",
                        "action": "close",
                    },
                ],
                [
                    {
                        "text": "✍️ Say something",
                        "input": "Type your message",
                        "handler": self._typed,
                    }
                ],
                [
                    {
                        "text": "🌍 Open site",
                        "url": "https://example.com",
                    }
                ],
            ],
        )

    async def _approve(self, call: InlineCall, number: int):
        # Buttons may pass any serializable args
        await call.answer(f"Approved {number}!")
        await call.edit(
            f"<b>Approved {number}!</b>",
            reply_markup=[{"text": "🔻 Close", "action": "close"}],
        )

    async def _typed(self, call: InlineCall, value: str):
        # `value` is the text typed by the user in the inline input
        await call.edit(
            f"<b>You typed:</b> <code>{utils.escape_html(value)}</code>",
            reply_markup=[{"text": "🔻 Close", "action": "close"}],
        )

    @loader.command()
    async def examplelist(self, message: Message):
        """Show an example of a paginated list"""
        await self.inline.list(
            message,
            [f"<b>Page {i}</b>\n\nSome content here" for i in range(1, 31)],
        )

    @loader.command()
    async def examplegallery(self, message: Message):
        """Show an example of a gallery"""
        pics = [
            "https://img.icons8.com/fluency/452/moon-satellite.png",
            "https://img.icons8.com/fluency/452/cloud.png",
            "https://img.icons8.com/fluency/452/sun.png",
        ]
        await self.inline.gallery(
            message,
            pics,
            caption=["Moon", "Cloud", "Sun"],
        )

    @loader.command()
    async def exampledb(self, message: Message):
        """Show how to use the database"""
        # get/set/pointer are auto-namespaced by class name
        counter = self.get("counter", 0)
        self.set("counter", counter + 1)

        await utils.answer(
            message,
            f"<b>This command was called {counter + 1} time(s)</b>",
        )

    @loader.command()
    async def exampleconfig(self, message: Message):
        """Show the current config"""
        await utils.answer(
            message,
            f"<b>enabled:</b> <code>{self.config['enabled']}</code>\n"
            f"<b>whitelist:</b> <code>{self.config['whitelist']}</code>",
        )

    @loader.inline_handler(thumb_url="https://img.icons8.com/fluency/452/rocket.png")
    async def _inline_handler(self, query: InlineQuery) -> dict:
        """Example inline handler (owner-only by default)"""
        return {
            "title": "🚀 Example inline",
            "description": "Sends a demo message",
            "message": "<b>Hello from inline!</b>",
            "thumb": "https://img.icons8.com/fluency/452/rocket.png",
        }

    @loader.callback_handler()
    async def _callback_handler(self, call: InlineCall):
        # Global callback handler — reacts to buttons with raw `data`
        if call.data == "example_ping":
            await call.answer("Pong!")

    @loader.watcher("only_pm")
    async def watcher(self, message: Message):
        # Runs on every private message (after the command is processed)
        pass

    @loader.loop(interval=60)
    async def _loop(self):
        # Periodic task. Start with .start_loop, stop with .stop_loop
        # (or just remove this example module)
        pass
