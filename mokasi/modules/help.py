# Mokasi core module — help
from aiogram.types import Message

from .. import loader, utils
from ..inline.types import InlineCall


@loader.tds
class HelpMod(loader.Module):
    """Show help"""

    strings = {
        "name": "Help",
        "help_header": "🤖 <b>Mokasi help</b>\n\n<i>{} modules, {} commands</i>",
        "mod_header": "📦 <b>Module {}:</b>\n\n{}",
        "mod_not_found": "🚫 <b>Module or command not found:</b> <code>{}</code>",
        "no_commands": "🚫 <b>No commands registered</b>",
        "hidden": "🙈 <b>Module {} is now hidden from help</b>",
        "unhidden": "👁 <b>Module {} is now visible in help</b>",
        "no_args": "🚫 <b>Specify the module to hide</b>",
    }

    strings_ru = {
        "name": "Помощь",
        "help_header": "🤖 <b>Помощь Mokasi</b>\n\n<i>{} модулей, {} команд</i>",
        "mod_header": "📦 <b>Модуль {}:</b>\n\n{}",
        "mod_not_found": "🚫 <b>Модуль или команда не найдены:</b> <code>{}</code>",
        "no_commands": "🚫 <b>Нет зарегистрированных команд</b>",
        "hidden": "🙈 <b>Модуль {} теперь скрыт из помощи</b>",
        "unhidden": "👁 <b>Модуль {} теперь виден в помощи</b>",
        "no_args": "🚫 <b>Укажите модуль для скрытия</b>",
    }

    def _get_hidden(self) -> list:
        return self.get("hide", [])

    @loader.command()
    async def helpcmd(self, message: Message):
        """Show help"""
        hidden = self._get_hidden()

        visible = [
            mod
            for mod in self.allmodules.modules
            if mod.__class__.__name__ not in hidden
            and (mod.commands or mod.inline_handlers)
        ]

        if not visible:
            await utils.answer(message, self.strings("no_commands"))
            return

        await self.inline.form(
            self.strings("help_header").format(
                len(visible),
                sum(len(mod.commands) for mod in visible),
            ),
            message,
            reply_markup=[
                [
                    {
                        "text": f"📦 {mod.__class__.__name__}",
                        "callback": self.inline__show_module,
                        "args": (mod.__class__.__name__,),
                    }
                    for mod in chunk
                ]
                for chunk in utils.chunks(visible, 2)
            ]
            + [[{"text": "🔻 Close", "action": "close"}]],
        )

    async def inline__show_module(self, call: InlineCall, module_name: str):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer(self.strings("mod_not_found").format(module_name), show_alert=True)
            return

        text = "\n\n".join(
            (
                f"▫️ <code>{self.get_prefix()}{cmd}</code>"
                + (f" — <i>{utils.escape_html(inspect_doc)}</i>" if (inspect_doc := (getattr(func, '__doc__', None) or '').strip()) else "")
            )
            for cmd, func in mod.commands.items()
        )

        inline_text = ""
        if mod.inline_handlers:
            inline_text = "\n\n<b>Inline:</b>\n" + "\n".join(
                f"▫️ <code>@{self.inline.bot_username} {name}</code>"
                for name in mod.inline_handlers
            )

        await call.edit(
            self.strings("mod_header").format(
                utils.escape_html(mod.__class__.__name__),
                text + inline_text,
            ),
            reply_markup=[
                [{"text": "🔙 Back", "callback": self.inline__back}],
                [{"text": "🔻 Close", "action": "close"}],
            ],
        )

    async def inline__back(self, call: InlineCall):
        hidden = self._get_hidden()

        visible = [
            mod
            for mod in self.allmodules.modules
            if mod.__class__.__name__ not in hidden
            and (mod.commands or mod.inline_handlers)
        ]

        await call.edit(
            self.strings("help_header").format(
                len(visible),
                sum(len(mod.commands) for mod in visible),
            ),
            reply_markup=[
                [
                    {
                        "text": f"📦 {mod.__class__.__name__}",
                        "callback": self.inline__show_module,
                        "args": (mod.__class__.__name__,),
                    }
                    for mod in chunk
                ]
                for chunk in utils.chunks(visible, 2)
            ]
            + [[{"text": "🔻 Close", "action": "close"}]],
        )

    @loader.command()
    async def modhelp(self, message: Message):
        """Show help for a module or a command"""
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings("no_args"))
            return

        # Try command first
        cmd, func = self.allmodules.dispatch(args)

        if func and cmd == args.lower():
            doc = (getattr(func, "__doc__", None) or "").strip()
            await utils.answer(
                message,
                self.strings("mod_header").format(
                    utils.escape_html(args),
                    (
                        f"▫️ <code>{self.get_prefix()}{cmd}</code> — "
                        f"<i>{utils.escape_html(doc)}</i>"
                    ),
                ),
            )
            return

        mod = self.lookup(args)

        if not mod:
            await utils.answer(
                message,
                self.strings("mod_not_found").format(utils.escape_html(args)),
            )
            return

        text = "\n\n".join(
            (
                f"▫️ <code>{self.get_prefix()}{cmd}</code>"
                + (
                    f" — <i>{utils.escape_html(doc)}</i>"
                    if (doc := (getattr(func, "__doc__", None) or "").strip())
                    else ""
                )
            )
            for cmd, func in mod.commands.items()
        )

        await utils.answer(
            message,
            self.strings("mod_header").format(
                utils.escape_html(mod.__class__.__name__),
                text,
            ),
        )

    @loader.command()
    async def helphide(self, message: Message):
        """Hide a module from help"""
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings("no_args"))
            return

        mod = self.lookup(args)

        if not mod:
            await utils.answer(
                message,
                self.strings("mod_not_found").format(utils.escape_html(args)),
            )
            return

        hidden = self._get_hidden()
        name = mod.__class__.__name__

        if name in hidden:
            hidden.remove(name)
            await utils.answer(
                message,
                self.strings("unhidden").format(utils.escape_html(name)),
            )
        else:
            hidden.append(name)
            await utils.answer(
                message,
                self.strings("hidden").format(utils.escape_html(name)),
            )

        self.set("hide", hidden)
