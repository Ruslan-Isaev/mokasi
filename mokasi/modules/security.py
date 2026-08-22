# Mokasi core module — owners management and security masks UI
from aiogram.types import Message

from .. import loader, security, utils
from ..inline.types import InlineCall

DEFAULT_MASK_EMOJIES = {
    "OWNER": "👑",
    "EVERYONE": "🌍",
}


@loader.tds
class SecurityMod(loader.Module):
    """Security management"""

    strings = {
        "name": "Security",
        "no_args": "🚫 <b>Specify the user</b> (id, @username or reply)",
        "owner_added": "✅ <b>User <code>{}</code> is now an owner</b>",
        "owner_already": "ℹ️ <b>User <code>{}</code> is already an owner</b>",
        "owner_removed": "✅ <b>User <code>{}</code> is no longer an owner</b>",
        "owner_not_found": "🚫 <b>User <code>{}</code> is not an owner</b>",
        "owner_cant_remove": "🚫 <b>Can't remove the only owner of the bot</b>",
        "owner_list": "👑 <b>Owners:</b>\n\n{}",
        "no_owners": "🚫 <b>No owners configured. Use /start to claim the bot</b>",
        "security_header": "🔐 <b>Security settings</b>\n\n<i>Choose a module to configure command permissions</i>",
        "perms_header": "🔐 <b>Permissions of {}</b>\n\n<b>{}</b>\n<i>Tap the mask to toggle it. Owner mask can't be removed</i>",
        "inlinesec_header": "🔐 <b>Inline permissions</b>\n\n<i>Choose a module to configure inline handler permissions</i>",
        "toggled": "✅ <b>{}</b> {} — <b>{}</b>",
        "bounded": "🚫 <b>This mask is not available, because it is excluded by bounding mask</b>",
        "bounding_toggle": "🔰 <b>Bounding mask: {}</b>\n\n<i>When enabled, only owner-scoped commands are allowed for everyone. When disabled, the EVERYONE bit works</i>",
        "not_owner_self": "🚫 <b>You can't remove yourself from owners</b>",
    }

    strings_ru = {
        "name": "Безопасность",
        "no_args": "🚫 <b>Укажите пользователя</b> (id, @username или ответ)",
        "owner_added": "✅ <b>Пользователь <code>{}</code> теперь владелец</b>",
        "owner_already": "ℹ️ <b>Пользователь <code>{}</code> уже владелец</b>",
        "owner_removed": "✅ <b>Пользователь <code>{}</code> больше не владелец</b>",
        "owner_not_found": "🚫 <b>Пользователь <code>{}</code> не является владельцем</b>",
        "owner_cant_remove": "🚫 <b>Нельзя удалить единственного владельца бота</b>",
        "owner_list": "👑 <b>Владельцы:</b>\n\n{}",
        "no_owners": "🚫 <b>Владельцы не настроены. Используйте /start, чтобы завладеть ботом</b>",
        "security_header": "🔐 <b>Настройки безопасности</b>\n\n<i>Выберите модуль для настройки прав команд</i>",
        "perms_header": "🔐 <b>Права {}</b>\n\n<b>{}</b>\n<i>Нажмите на маску, чтобы переключить её. Маску владельца нельзя убрать</i>",
        "inlinesec_header": "🔐 <b>Права inline</b>\n\n<i>Выберите модуль для настройки прав inline-обработчиков</i>",
        "toggled": "✅ <b>{}</b> {} — <b>{}</b>",
        "bounded": "🚫 <b>Эта маска недоступна, так как исключена ограничивающей маской</b>",
        "bounding_toggle": "🔰 <b>Ограничивающая маска: {}</b>\n\n<i>Если включена — доступно только владельцам. Если выключена — работает бит EVERYONE</i>",
        "not_owner_self": "🚫 <b>Нельзя удалить самого себя из владельцев</b>",
    }

    @staticmethod
    def _get_mask_text(mask: int) -> str:
        return " ".join(
            f"{emoji} {name}"
            for name, emoji in DEFAULT_MASK_EMOJIES.items()
            if mask & getattr(security, name)
        ) or "🚫 None"

    @loader.command()
    async def owneradd(self, message: Message):
        """Add an owner (id, @username or reply)"""
        user_id = await utils.get_target(message)

        if user_id is None:
            await utils.answer(message, self.strings("no_args"))
            return

        if user_id == self.bot_id:
            await utils.answer(
                message,
                self.strings("owner_already").format(utils.escape_html(user_id)),
            )
            return

        owners = self._db.pointer("mokasi.security", "owner", [])

        if user_id in owners:
            await utils.answer(
                message,
                self.strings("owner_already").format(utils.escape_html(user_id)),
            )
            return

        owners.append(user_id)

        await utils.answer(
            message,
            self.strings("owner_added").format(utils.escape_html(user_id)),
        )

    @loader.command()
    async def ownerrm(self, message: Message):
        """Remove an owner (id, @username or reply)"""
        user_id = await utils.get_target(message)

        if user_id is None:
            await utils.answer(message, self.strings("no_args"))
            return

        if user_id == getattr(message.from_user, "id", None):
            await utils.answer(message, self.strings("not_owner_self"))
            return

        owners = self._db.pointer("mokasi.security", "owner", [])

        human_owners = [owner for owner in owners if owner != self.bot_id]

        if user_id not in human_owners:
            await utils.answer(
                message,
                self.strings("owner_not_found").format(utils.escape_html(user_id)),
            )
            return

        if len(human_owners) <= 1:
            await utils.answer(message, self.strings("owner_cant_remove"))
            return

        owners.remove(user_id)

        await utils.answer(
            message,
            self.strings("owner_removed").format(utils.escape_html(user_id)),
        )

    @loader.command()
    async def ownerlist(self, message: Message):
        """List owners"""
        owners = self._db.pointer("mokasi.security", "owner", [])

        human_owners = [owner for owner in owners if owner != self.bot_id]

        if not human_owners:
            await utils.answer(message, self.strings("no_owners"))
            return

        lines = []
        for i, owner in enumerate(human_owners, 1):
            name = ""
            try:
                chat = await message.bot.get_chat(owner)
                name = (
                    f" — <code>{utils.escape_html(chat.full_name)}</code>"
                    if getattr(chat, "full_name", None)
                    else ""
                )
            except Exception:
                pass

            lines.append(f"{i}. <code>{owner}</code>{name}")

        await utils.answer(
            message,
            self.strings("owner_list").format("\n".join(lines)),
        )

    def _mask_to_buttons(self, func, name: str) -> list:
        """Generate mask toggle buttons for the function"""
        buttons = []
        for mask_name, emoji in DEFAULT_MASK_EMOJIES.items():
            mask = getattr(security, mask_name)
            current = self._db.get("mokasi.security", "masks", {}).get(
                f"{func.__module__}.{func.__name__}",
                getattr(func, "security", security.DEFAULT_PERMISSIONS),
            )
            state = "✅" if current & mask else "❌"
            buttons.append(
                {
                    "text": f"{state} {emoji} {mask_name}",
                    "callback": self.inline__switch_perm,
                    "args": (name, mask_name),
                }
            )

        return buttons

    def _modules_markup(self) -> list:
        """Build module-picker markup for commands security"""
        modules_with_commands = [
            mod
            for mod in self.allmodules.modules
            if mod.commands
        ]

        return [
            [
                {
                    "text": f"👁 {mod.__class__.__name__}",
                    "callback": self.inline__choose_module,
                    "args": (mod.__class__.__name__,),
                }
                for mod in chunk
            ]
            for chunk in utils.chunks(modules_with_commands, 2)
        ] + [[{"text": "🔻 Close", "action": "close"}]]

    def _inline_modules_markup(self) -> list:
        """Build module-picker markup for inline security"""
        bounding = self._db.get(
            "mokasi.security",
            "bounding_mask",
            security.DEFAULT_PERMISSIONS,
        )

        reply_markup = [
            [
                {
                    "text": (
                        "🔰 Bounding mask: 👑 Owner only"
                        if bounding & security.OWNER
                        else "🔰 Bounding mask: 🌍 Everyone allowed"
                    ),
                    "callback": self.inline__toggle_bounding,
                }
            ]
        ]

        modules_with_inline = [
            mod
            for mod in self.allmodules.modules
            if mod.inline_handlers
        ]

        if modules_with_inline:
            reply_markup += [
                [
                    {
                        "text": f"👁 {mod.__class__.__name__}",
                        "callback": self.inline__choose_inline_module,
                        "args": (mod.__class__.__name__,),
                    }
                ]
                for mod in modules_with_inline
            ]

        reply_markup += [[{"text": "🔻 Close", "action": "close"}]]

        return reply_markup

    @loader.command()
    async def securitycmd(self, message: Message):
        """Open the security settings menu"""
        await self.inline.form(
            self.strings("security_header"),
            message,
            reply_markup=self._modules_markup(),
        )

    @loader.command()
    async def inlinesec(self, message: Message):
        """Open the inline security settings menu"""
        await self.inline.form(
            self.strings("inlinesec_header"),
            message,
            reply_markup=self._inline_modules_markup(),
        )

    async def inline__toggle_bounding(self, call: InlineCall):
        bounding = self._db.get(
            "mokasi.security",
            "bounding_mask",
            security.DEFAULT_PERMISSIONS,
        )

        if bounding & security.OWNER:
            new = security.ALL
        else:
            new = security.DEFAULT_PERMISSIONS

        self._db.set("mokasi.security", "bounding_mask", new)

        await call.edit(
            self.strings("bounding_toggle").format(
                "👑 Owner only" if new & security.OWNER else "🌍 Everyone allowed"
            ),
            reply_markup=[
                {
                    "text": (
                        "🔰 Bounding mask: 👑 Owner only"
                        if new & security.OWNER
                        else "🔰 Bounding mask: 🌍 Everyone allowed"
                    ),
                    "callback": self.inline__toggle_bounding,
                },
                {"text": "🔻 Close", "action": "close"},
            ],
        )

    async def inline__choose_module(self, call: InlineCall, module_name: str):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer("Module not found", show_alert=True)
            return

        text = "\n".join(
            f"▫️ <code>{utils.escape_html(cmd)}</code> — "
            f"{self._get_mask_text(self._get_flags_public(func))}"
            for cmd, func in mod.commands.items()
        )

        await call.edit(
            self.strings("perms_header").format(
                utils.escape_html(mod.__class__.__name__),
                text,
            ),
            reply_markup=[
                [
                    {
                        "text": f"{cmd} — {self._get_mask_text(self._get_flags_public(func))}",
                        "callback": self.inline__show_command,
                        "args": (module_name, cmd),
                    }
                ]
                for cmd, func in mod.commands.items()
            ]
            + [
                [
                    {
                        "text": "🔙 Back",
                        "callback": self.inline__back_to_modules,
                    }
                ],
                [{"text": "🔻 Close", "action": "close"}],
            ],
        )

    def _get_flags_public(self, func) -> int:
        return self._db.get("mokasi.security", "masks", {}).get(
            f"{func.__module__}.{func.__name__}",
            getattr(func, "security", security.DEFAULT_PERMISSIONS),
        )

    async def inline__back_to_modules(self, call: InlineCall):
        await call.edit(
            self.strings("security_header"),
            reply_markup=self._modules_markup(),
        )

    async def inline__show_command(self, call: InlineCall, module_name: str, command: str):
        mod = self.lookup(module_name)

        if not mod or command not in mod.commands:
            await call.answer("Command not found", show_alert=True)
            return

        func = mod.commands[command]

        await call.edit(
            self.strings("perms_header").format(
                utils.escape_html(f"{module_name}.{command}"),
                f"<code>{utils.escape_html(command)}</code>",
            ),
            reply_markup=[
                self._mask_to_buttons(func, f"{module_name}.{command}")
            ]
            + [
                [
                    {
                        "text": "🔙 Back",
                        "callback": self.inline__choose_module,
                        "args": (module_name,),
                    }
                ],
                [{"text": "🔻 Close", "action": "close"}],
            ],
        )

    async def inline__switch_perm(self, call: InlineCall, name: str, mask_name: str):
        module_name, command = name.rsplit(".", maxsplit=1)
        mod = self.lookup(module_name)

        if not mod or command not in mod.commands:
            await call.answer("Command not found", show_alert=True)
            return

        func = mod.commands[command]

        masks = self._db.get("mokasi.security", "masks", {})
        current = masks.get(
            f"{func.__module__}.{func.__name__}",
            getattr(func, "security", security.DEFAULT_PERMISSIONS),
        )

        mask = getattr(security, mask_name)

        if mask == security.OWNER:
            await call.answer(
                self.strings("bounded"),
                show_alert=True,
            )
            return

        bounding = self._db.get(
            "mokasi.security",
            "bounding_mask",
            security.DEFAULT_PERMISSIONS,
        )

        if mask & ~bounding:
            await call.answer(
                self.strings("bounded"),
                show_alert=True,
            )
            return

        current ^= mask

        if mask_name == "EVERYONE" and current & mask:
            # When enabling EVERYONE, drop other non-owner masks
            current = security.OWNER | mask

        masks[f"{func.__module__}.{func.__name__}"] = current
        self._db.set("mokasi.security", "masks", masks)

        await call.edit(
            self.strings("perms_header").format(
                utils.escape_html(f"{module_name}.{command}"),
                self._get_mask_text(current),
            ),
            reply_markup=[
                self._mask_to_buttons(func, f"{module_name}.{command}")
            ]
            + [
                [
                    {
                        "text": "🔙 Back",
                        "callback": self.inline__choose_module,
                        "args": (module_name,),
                    }
                ],
                [{"text": "🔻 Close", "action": "close"}],
            ],
        )

    async def inline__choose_inline_module(self, call: InlineCall, module_name: str):
        mod = self.lookup(module_name)

        if not mod:
            await call.answer("Module not found", show_alert=True)
            return

        await call.edit(
            self.strings("perms_header").format(
                utils.escape_html(mod.__class__.__name__),
                "\n".join(
                    f"▫️ <code>{utils.escape_html(name)}</code>"
                    for name in mod.inline_handlers
                ),
            ),
            reply_markup=[
                [
                    {
                        "text": f"{name} — {self._get_mask_text(self._get_flags_public(func))}",
                        "callback": self.inline__switch_inline_perm,
                        "args": (module_name, name),
                    }
                ]
                for name, func in mod.inline_handlers.items()
            ]
            + [
                [
                    {
                        "text": "🔙 Back",
                        "callback": self.inline__back_to_inline_modules,
                    }
                ],
                [{"text": "🔻 Close", "action": "close"}],
            ],
        )

    async def inline__back_to_inline_modules(self, call: InlineCall):
        await call.edit(
            self.strings("inlinesec_header"),
            reply_markup=self._inline_modules_markup(),
        )

    async def inline__switch_inline_perm(self, call: InlineCall, module_name: str, name: str):
        mod = self.lookup(module_name)

        if not mod or name not in mod.inline_handlers:
            await call.answer("Handler not found", show_alert=True)
            return

        func = mod.inline_handlers[name]

        masks = self._db.get("mokasi.security", "masks", {})
        current = masks.get(
            f"{func.__module__}.{func.__name__}",
            getattr(func, "security", security.DEFAULT_PERMISSIONS),
        )

        bounding = self._db.get(
            "mokasi.security",
            "bounding_mask",
            security.DEFAULT_PERMISSIONS,
        )

        if security.EVERYONE & ~bounding:
            await call.answer(
                self.strings("bounded"),
                show_alert=True,
            )
            return

        current ^= security.EVERYONE
        masks[f"{func.__module__}.{func.__name__}"] = current
        self._db.set("mokasi.security", "masks", masks)

        await self.inline__choose_inline_module(call, module_name)
