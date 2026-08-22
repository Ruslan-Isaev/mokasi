# Mokasi core module — interactive config UI
import contextlib

from aiogram.types import Message

from .. import loader, utils, validators
from ..inline.types import InlineCall


@loader.tds
class ConfigMod(loader.Module):
    """Configure modules interactively"""

    strings = {
        "name": "Config",
        "config_header": "🧩 <b>Config</b>\n\n<i>Choose a module to configure</i>",
        "no_configs": "🚫 <b>No configurable modules</b>",
        "options_header": "⚙️ <b>Config of {}:</b>\n\n{}\n\n<i>Tap an option to change it</i>",
        "option_header": "⚙️ <b>Option {}:</b>\n\n<b>Value:</b> <code>{}</code>\n\n<i>{}</i>",
        "set_success": "✅ <b>{} =</b> <code>{}</code>",
        "set_failed": "🚫 <b>Invalid value:</b> <code>{}</code>\n\n<i>{}</i>",
        "reset": "✅ <b>{} reset to default:</b> <code>{}</code>",
        "input_value": "Enter new value",
        "input_add_item": "Enter item to add",
        "back": "🔙 Back",
        "close": "🔻 Close",
        "edit": "✍️ Edit",
        "add": "➕ Add",
        "show": "👁 Show",
        "hidden_value": "🚫 <b>Value is hidden</b>",
        "remove_item": "🗑 {}",
    }

    strings_ru = {
        "name": "Конфиг",
        "config_header": "🧩 <b>Конфиг</b>\n\n<i>Выберите модуль для настройки</i>",
        "no_configs": "🚫 <b>Нет настраиваемых модулей</b>",
        "options_header": "⚙️ <b>Конфиг {}:</b>\n\n{}\n\n<i>Нажмите на опцию, чтобы изменить её</i>",
        "option_header": "⚙️ <b>Опция {}:</b>\n\n<b>Значение:</b> <code>{}</code>\n\n<i>{}</i>",
        "set_success": "✅ <b>{} =</b> <code>{}</code>",
        "set_failed": "🚫 <b>Некорректное значение:</b> <code>{}</code>\n\n<i>{}</i>",
        "reset": "✅ <b>{} сброшено к значению по умолчанию:</b> <code>{}</code>",
        "input_value": "Введите новое значение",
        "input_add_item": "Введите элемент для добавления",
        "back": "🔙 Назад",
        "close": "🔻 Закрыть",
        "edit": "✍️ Изменить",
        "add": "➕ Добавить",
        "show": "👁 Показать",
        "hidden_value": "🚫 <b>Значение скрыто</b>",
        "remove_item": "🗑 {}",
    }

    @loader.command()
    async def configcmd(self, message: Message):
        """Open the config menu"""
        mods = [mod for mod in self.allmodules.modules if hasattr(mod, "config") and mod.config]

        if not mods:
            await utils.answer(message, self.strings("no_configs"))
            return

        await self.inline.form(
            self.strings("config_header"),
            message,
            reply_markup=[
                [
                    {
                        "text": f"🧩 {mod.__class__.__name__}",
                        "callback": self.inline__choose_config,
                        "args": (mod.__class__.__name__,),
                    }
                    for mod in chunk
                ]
                for chunk in utils.chunks(mods, 2)
            ]
            + [[{"text": self.strings("close"), "action": "close"}]],
        )

    async def inline__choose_config(self, call: InlineCall, module_name: str):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer("Module not found", show_alert=True)
            return

        text = "\n".join(
            f"▫️ <b>{utils.escape_html(option)}:</b> <code>{self._fmt_value(mod, option)}</code>"
            for option in mod.config
        )

        await call.edit(
            self.strings("options_header").format(
                utils.escape_html(mod.__class__.__name__),
                text,
            ),
            reply_markup=[
                [
                    {
                        "text": f"⚙️ {option}",
                        "callback": self.inline__configure_option,
                        "args": (module_name, option),
                    }
                    for option in chunk
                ]
                for chunk in utils.chunks(list(mod.config), 2)
            ]
            + [
                [{"text": self.strings("back"), "callback": self.inline__back_to_config}],
                [{"text": self.strings("close"), "action": "close"}],
            ],
        )

    def _fmt_value(self, mod, option: str) -> str:
        value = mod.config[option]
        validator = mod.config._config[option].validator

        if isinstance(validator, validators.Hidden):
            return self.strings("hidden_value")

        if isinstance(value, list):
            return utils.escape_html(", ".join(map(str, value)))

        return utils.escape_html(str(value))

    async def inline__back_to_config(self, call: InlineCall):
        mods = [mod for mod in self.allmodules.modules if hasattr(mod, "config") and mod.config]

        await call.edit(
            self.strings("config_header"),
            reply_markup=[
                [
                    {
                        "text": f"🧩 {mod.__class__.__name__}",
                        "callback": self.inline__choose_config,
                        "args": (mod.__class__.__name__,),
                    }
                    for mod in chunk
                ]
                for chunk in utils.chunks(mods, 2)
            ]
            + [[{"text": self.strings("close"), "action": "close"}]],
        )

    async def inline__configure_option(
        self,
        call: InlineCall,
        module_name: str,
        option: str,
    ):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer("Module not found", show_alert=True)
            return

        validator = mod.config._config[option].validator
        value = mod.config[option]

        reply_markup = []

        if isinstance(validator, validators.Boolean):
            reply_markup = [
                [
                    {
                        "text": "✅ True" if value else "☑️ True",
                        "callback": self.inline__set,
                        "args": (module_name, option, "True"),
                    },
                    {
                        "text": "❌ False" if not value else "☑️ False",
                        "callback": self.inline__set,
                        "args": (module_name, option, "False"),
                    },
                ]
            ]
        elif isinstance(validator, validators.Series):
            reply_markup = [
                [
                    {
                        "text": self.strings("remove_item").format(
                            utils.escape_html(str(item))
                        ),
                        "callback": self.inline__remove_item,
                        "args": (module_name, option, item),
                    }
                    for item in value
                ]
            ] + [
                [
                    {
                        "text": self.strings("add"),
                        "input": self.strings("input_add_item"),
                        "handler": self.inline__add_item,
                        "args": (module_name, option),
                    }
                ]
            ]
        elif isinstance(validator, validators.Choice):
            reply_markup = [
                [
                    {
                        "text": f"{'✅' if choice == value else '☑️'} {choice}",
                        "callback": self.inline__set,
                        "args": (module_name, option, choice),
                    }
                    for choice in validator._validate.keywords.get(
                        "possible_values", []
                    )
                ]
            ]
        elif isinstance(validator, validators.MultiChoice):
            possible = validator._validate.keywords.get("possible_values", [])
            reply_markup = [
                [
                    {
                        "text": f"{'✅' if choice in value else '☑️'} {choice}",
                        "callback": self.inline__toggle_item,
                        "args": (module_name, option, choice),
                    }
                    for choice in possible
                ]
            ]
        elif isinstance(validator, validators.Hidden):
            reply_markup = [
                [
                    {
                        "text": self.strings("show"),
                        "callback": self.inline__show_hidden,
                        "args": (module_name, option),
                    },
                    {
                        "text": self.strings("edit"),
                        "input": self.strings("input_value"),
                        "handler": self.inline__set_config,
                        "args": (module_name, option),
                    },
                ]
            ]
        else:
            reply_markup = [
                [
                    {
                        "text": self.strings("edit"),
                        "input": self.strings("input_value"),
                        "handler": self.inline__set_config,
                        "args": (module_name, option),
                    }
                ]
            ]

        reply_markup += [
            [
                {
                    "text": "↩️ Reset",
                    "callback": self.inline__reset,
                    "args": (module_name, option),
                }
            ],
            [
                {
                    "text": self.strings("back"),
                    "callback": self.inline__choose_config,
                    "args": (module_name,),
                }
            ],
            [{"text": self.strings("close"), "action": "close"}],
        ]

        await call.edit(
            self.strings("option_header").format(
                utils.escape_html(option),
                self._fmt_value(mod, option),
                utils.escape_html(mod.config.getdoc(option)),
            ),
            reply_markup=reply_markup,
        )

    async def inline__set_config(self, call: InlineCall, query: str, module_name: str, option: str):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer("Module not found", show_alert=True)
            return

        try:
            mod.config[option] = query
        except validators.ValidationError as e:
            await call.edit(
                self.strings("set_failed").format(
                    utils.escape_html(option),
                    utils.escape_html(query),
                    utils.escape_html(str(e)),
                ),
                reply_markup=[
                    [
                        {
                            "text": self.strings("back"),
                            "callback": self.inline__configure_option,
                            "args": (module_name, option),
                        }
                    ],
                    [{"text": self.strings("close"), "action": "close"}],
                ],
            )
            return

        await call.edit(
            self.strings("set_success").format(
                utils.escape_html(option),
                utils.escape_html(str(mod.config[option])),
            ),
            reply_markup=[
                [
                    {
                        "text": self.strings("back"),
                        "callback": self.inline__configure_option,
                        "args": (module_name, option),
                    }
                ],
                [{"text": self.strings("close"), "action": "close"}],
            ],
        )

    async def inline__set(self, call: InlineCall, module_name: str, option: str, value: str):
        await self.inline__set_config(call, value, module_name, option)

    async def inline__reset(self, call: InlineCall, module_name: str, option: str):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer("Module not found", show_alert=True)
            return

        mod.config[option] = mod.config.getdef(option)

        await self.inline__configure_option(call, module_name, option)

    async def inline__remove_item(self, call: InlineCall, module_name: str, option: str, item):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer("Module not found", show_alert=True)
            return

        value = mod.config[option]
        with contextlib.suppress(ValueError):
            value.remove(item)
        mod.config[option] = value

        await self.inline__configure_option(call, module_name, option)

    async def inline__add_item(self, call: InlineCall, query: str, module_name: str, option: str):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer("Module not found", show_alert=True)
            return

        value = list(mod.config[option])
        value.append(query)
        mod.config[option] = value

        await self.inline__configure_option(call, module_name, option)

    async def inline__toggle_item(self, call: InlineCall, module_name: str, option: str, item):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer("Module not found", show_alert=True)
            return

        value = list(mod.config[option])
        if item in value:
            value.remove(item)
        else:
            value.append(item)

        mod.config[option] = value

        await self.inline__configure_option(call, module_name, option)

    async def inline__show_hidden(self, call: InlineCall, module_name: str, option: str):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer("Module not found", show_alert=True)
            return

        await call.answer(
            f"{option}: {mod.config[option]}",
            show_alert=True,
        )
