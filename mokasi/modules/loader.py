# Mokasi core module — external module management
import asyncio
import ast
import contextlib
import importlib.machinery
import io
import logging
import os
import re
import sys
import typing

import aiohttp
from aiogram.types import Message

from .. import loader, main, utils
from ..inline.types import InlineCall
from ..types import StringLoader

logger = logging.getLogger(__name__)


@loader.tds
class LoaderMod(loader.Module):
    """Loads modules"""

    strings = {
        "name": "Loader",
        "provide_module": "<b>Provide a module:</b>\n<code>.loadmod &lt;reply to file&gt;</code> or <code>.loadmod &lt;url&gt;</code>",
        "bad_unicode": "Invalid module encoding. Please, use UTF-8",
        "module_fs": "💾 <b>Save module to disk?</b>\n<i>This will make the module load automatically on boot</i>",
        "save": "💾 Save",
        "no_save": "🚫 Don't save",
        "save_for_all": "✅ Always save",
        "never_save": "🚫 Never save",
        "will_save_fs": "Module will be saved to filesystem",
        "no_class": "Specify module classname to unload",
        "unload_core": "Module {} is core and cannot be unloaded",
        "unloaded": "{} Module <code>{}</code> unloaded!",
        "not_unloaded": "Module not found",
        "confirm_clearmodules": "🗑 <b>Are you sure you want to unload all external modules?</b>",
        "clearmodules": "🗑 Unload all",
        "cancel": "🚫 Cancel",
        "loaded_mods_header": "📦 <b>Loaded external modules:</b>",
        "no_external": "🚫 <b>No external modules loaded</b>",
        "loading": "⏳ <b>Loading module...</b>",
        "success": "✅ <b>Module <code>{}</code> loaded!</b>\n{}",
        "error": "🚫 <b>Module load failed:</b>\n<code>{}</code>",
        "requirements": "📦 Installing requirements: <code>{}</code>...",
        "requirements_failed": "🚫 <b>Requirements install failed:</b>\n<code>{}</code>",
        "core_overwrite": "🚫 <b>{}</b>",
        "downloading": "⬇️ <b>Downloading module...</b>",
        "bad_url": "🚫 <b>Invalid URL</b>",
    }

    strings_ru = {
        "name": "Загрузчик",
        "provide_module": "<b>Пришлите модуль:</b>\n<code>.loadmod &lt;ответ на файл&gt;</code> или <code>.loadmod &lt;ссылка&gt;</code>",
        "bad_unicode": "Неверная кодировка модуля. Используйте UTF-8",
        "module_fs": "💾 <b>Сохранить модуль на диск?</b>\n<i>Модуль будет автоматически загружаться при старте</i>",
        "save": "💾 Сохранить",
        "no_save": "🚫 Не сохранять",
        "save_for_all": "✅ Всегда сохранять",
        "never_save": "🚫 Никогда не сохранять",
        "will_save_fs": "Модуль будет сохранён на диск",
        "no_class": "Укажите имя класса модуля для выгрузки",
        "unload_core": "Модуль {} — ядро, его нельзя выгрузить",
        "unloaded": "{} Модуль <code>{}</code> выгружен!",
        "not_unloaded": "Модуль не найден",
        "confirm_clearmodules": "🗑 <b>Вы уверены, что хотите выгрузить все внешние модули?</b>",
        "clearmodules": "🗑 Выгрузить все",
        "cancel": "🚫 Отмена",
        "loaded_mods_header": "📦 <b>Загруженные внешние модули:</b>",
        "no_external": "🚫 <b>Нет загруженных внешних модулей</b>",
        "loading": "⏳ <b>Загружаю модуль...</b>",
        "success": "✅ <b>Модуль <code>{}</code> загружен!</b>\n{}",
        "error": "🚫 <b>Ошибка загрузки модуля:</b>\n<code>{}</code>",
        "requirements": "📦 Устанавливаю зависимости: <code>{}</code>...",
        "requirements_failed": "🚫 <b>Ошибка установки зависимостей:</b>\n<code>{}</code>",
        "core_overwrite": "🚫 <b>{}</b>",
        "downloading": "⬇️ <b>Скачиваю модуль...</b>",
        "bad_url": "🚫 <b>Некорректная ссылка</b>",
    }

    async def client_ready(self, client, db):
        # Reinstall external modules persisted in db
        self.allmodules.send_config_one(self)
        asyncio.ensure_future(self._update_modules())

    @loader.loop(interval=3, wait_before=True, autostart=True)
    async def _config_autosaver(self):
        for mod in self.allmodules.modules:
            if (
                not hasattr(mod, "config")
                or not mod.config
                or not isinstance(mod.config, loader.ModuleConfig)
            ):
                continue

            for option, config in mod.config._config.items():
                if not hasattr(config, "_save_marker"):
                    continue

                delattr(mod.config._config[option], "_save_marker")
                mod.pointer("__config__", {})[option] = config.value

        self._db.save()

    def update_modules_in_db(self):
        if self.allmodules.secure_boot:
            return

        self.set(
            "loaded_modules",
            {
                module.__class__.__name__: module.__origin__
                for module in self.allmodules.modules
                if not module.__origin__.startswith("<core")
            },
        )

    async def _update_modules(self):
        todo = self.get("loaded_modules", {})
        logger.debug("Loading modules: %s", todo)
        for name, origin in todo.items():
            with contextlib.suppress(Exception):
                if utils.check_url(origin):
                    doc = await self._download_url(origin)
                    await self.load_module(doc, None, origin=origin)
                else:
                    path = os.path.join(loader.LOADED_MODULES_DIR, f"{name}.py")
                    if os.path.isfile(path):
                        doc = open(path).read()
                        await self.load_module(doc, None, origin="<file>")

    async def _download_url(self, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.text()

    @staticmethod
    def _get_classname(doc: str) -> typing.Optional[str]:
        """Get the class name of the module via AST"""
        try:
            module = ast.parse(doc)
        except SyntaxError:
            return None

        for node in module.body:
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    # Support both `class X(Module)` and `class X(loader.Module)`
                    if isinstance(base, ast.Name) and base.id == "Module":
                        return node.name
                    if isinstance(base, ast.Attribute) and base.attr == "Module":
                        return node.name

        return None

    async def _install_requirements(self, doc: str) -> bool:
        match = re.search(loader.VALID_PIP_PACKAGES, doc)
        if not match:
            return True

        packages = match.group(1).split()
        self._db.save()

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            *packages,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0

    async def load_module(
        self,
        doc: str,
        message: typing.Optional[Message],
        name: typing.Optional[str] = None,
        origin: str = "<string>",
        did_requirements: bool = False,
        save_fs: bool = False,
    ):
        if any(line.replace(" ", "") == "#scope:inline" for line in doc.splitlines()) and not self.inline.init_complete:
            if isinstance(message, Message):
                await utils.answer(message, "Inline manager is not initialized")
            return

        if re.search(r"# ?scope: ?mokasi_min", doc):
            ver = re.search(r"# ?scope: ?mokasi_min ((?:\d+\.){2}\d+)", doc).group(1)
            ver_ = tuple(map(int, ver.split(".")))
            if main.__version__ < ver_:
                if isinstance(message, Message):
                    await utils.answer(
                        message,
                        f"🚫 <b>Module requires mokasi {ver}, but {'.'.join(map(str, main.__version__))} is installed</b>",
                    )
                return

        if name is None:
            classname = self._get_classname(doc)
            if not classname:
                if isinstance(message, Message):
                    await utils.answer(
                        message,
                        self.strings("error").format(
                            utils.escape_html("No Module subclass found")
                        ),
                    )
                return
        else:
            classname = name

        module_name = f"mokasi.external.{classname}"

        try:
            spec = importlib.machinery.ModuleSpec(
                module_name,
                StringLoader(doc, f"<file {module_name}>"),
                origin=f"<file {module_name}>",
            )

            instance = await self.allmodules.register_module(
                spec,
                module_name,
                origin,
                save_fs=save_fs,
            )

            self.allmodules.send_config_one(instance)
            await self.allmodules.send_ready_one(instance, from_dlmod=True)

            if isinstance(message, (Message, InlineCall)):
                commands = "\n".join(
                    f"▫️ <code>{self.get_prefix()}{cmd}</code>"
                    for cmd in instance.commands
                )
                await utils.answer(
                    message,
                    self.strings("success").format(
                        utils.escape_html(classname),
                        commands,
                    ),
                )
        except loader.CoreOverwriteError as e:
            if isinstance(message, (Message, InlineCall)):
                await utils.answer(
                    message,
                    self.strings("core_overwrite").format(utils.escape_html(str(e))),
                )
        except loader.LoadError as e:
            if isinstance(message, (Message, InlineCall)):
                await utils.answer(
                    message,
                    self.strings("error").format(utils.escape_html(str(e))),
                )
        except ModuleNotFoundError as e:
            if not did_requirements:
                if isinstance(message, (Message, InlineCall)):
                    await utils.answer(
                        message,
                        self.strings("requirements").format(
                            utils.escape_html(e.name or "")
                        ),
                    )

                await self._install_requirements(doc)
                await self.load_module(
                    doc,
                    message,
                    name=classname,
                    origin=origin,
                    did_requirements=True,
                    save_fs=save_fs,
                )
                return

            if isinstance(message, (Message, InlineCall)):
                await utils.answer(
                    message,
                    self.strings("error").format(utils.escape_html(str(e))),
                )
        except Exception as e:
            logger.exception("Failed to load %s", classname)
            if isinstance(message, (Message, InlineCall)):
                await utils.answer(
                    message,
                    self.strings("error").format(utils.escape_html(str(e))),
                )

    async def _inline__load(
        self,
        call: InlineCall,
        doc: str,
        path_: str,
        mode: str,
    ):
        save = False
        if mode == "all_yes":
            self._db.set(main.__name__, "permanent_modules_fs", True)
            self._db.set(main.__name__, "disable_modules_fs", False)
            await call.answer(self.strings("will_save_fs"))
            save = True
        elif mode == "all_no":
            self._db.set(main.__name__, "disable_modules_fs", True)
            self._db.set(main.__name__, "permanent_modules_fs", False)
        elif mode == "once":
            save = True

        await self.load_module(doc, call, origin=path_ or "<string>", save_fs=save)

    @loader.command(alias="lm")
    async def loadmod(self, message: Message):
        """Load a module from an attached file or URL"""
        args = utils.get_args_raw(message)
        if "-fs" in args:
            force_save = True
            args = args.replace("-fs", "").strip()
        else:
            force_save = False

        doc = None

        if utils.check_url(args):
            await utils.answer(message, self.strings("downloading"))
            try:
                doc = await self._download_url(args)
            except Exception:
                await utils.answer(message, self.strings("bad_url"))
                return

            await self.load_module(
                doc,
                message,
                origin=args,
                save_fs=(
                    force_save
                    or self._db.get(main.__name__, "permanent_modules_fs", False)
                    and not self._db.get(main.__name__, "disable_modules_fs", False)
                ),
            )
            self.update_modules_in_db()
            return

        file = getattr(message, "document", None) or getattr(
            message.reply_to_message, "document", None
        )

        if file is None:
            await utils.answer(message, self.strings("provide_module"))
            return

        try:
            downloaded = await message.bot.download(file)
            doc = downloaded.read().decode()
        except UnicodeDecodeError:
            await utils.answer(message, self.strings("bad_unicode"))
            return
        except Exception:
            await utils.answer(message, self.strings("provide_module"))
            return

        if (
            not self._db.get(main.__name__, "disable_modules_fs", False)
            and not self._db.get(main.__name__, "permanent_modules_fs", False)
            and not force_save
        ):
            if await self.inline.form(
                self.strings("module_fs"),
                message=message,
                reply_markup=[
                    [
                        {
                            "text": self.strings("save"),
                            "callback": self._inline__load,
                            "args": (doc, None, "once"),
                        },
                        {
                            "text": self.strings("no_save"),
                            "callback": self._inline__load,
                            "args": (doc, None, "no"),
                        },
                    ],
                    [
                        {
                            "text": self.strings("save_for_all"),
                            "callback": self._inline__load,
                            "args": (doc, None, "all_yes"),
                        }
                    ],
                    [
                        {
                            "text": self.strings("never_save"),
                            "callback": self._inline__load,
                            "args": (doc, None, "all_no"),
                        }
                    ],
                ],
            ):
                return

        await self.load_module(
            doc,
            message,
            save_fs=(
                force_save
                or self._db.get(main.__name__, "permanent_modules_fs", False)
                and not self._db.get(main.__name__, "disable_modules_fs", False)
            ),
        )
        self.update_modules_in_db()

    @loader.command(alias="ulm")
    async def unloadmod(self, message: Message):
        """Unload an external module by its class name"""
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings("no_class"))
            return

        try:
            worked = await self.allmodules.unload_module(args)
        except loader.CoreUnloadError as e:
            await utils.answer(
                message,
                self.strings("unload_core").format(utils.escape_html(e.module)),
            )
            return

        if not self.allmodules.secure_boot:
            self.set(
                "loaded_modules",
                {
                    mod: link
                    for mod, link in self.get("loaded_modules", {}).items()
                    if mod not in worked
                },
            )

        msg = (
            self.strings("unloaded").format(
                "✅",
                ", ".join(
                    [
                        utils.escape_html(mod[:-3] if mod.endswith("Mod") else mod)
                        for mod in worked
                    ]
                ),
            )
            if worked
            else self.strings("not_unloaded")
        )

        await utils.answer(message, msg)

    @loader.command()
    async def listmod(self, message: Message):
        """List loaded external modules"""
        external = [
            module
            for module in self.allmodules.modules
            if not module.__origin__.startswith("<core")
        ]

        if not external:
            await utils.answer(message, self.strings("no_external"))
            return

        strings = [
            self.strings("loaded_mods_header")
            + "\n"
            + "\n".join(
                f"▫️ <b>{utils.escape_html(mod.__class__.__name__)}</b>\n"
                f"   <code>{utils.escape_html(mod.__origin__)}</code>"
                for mod in external
            )
        ]

        await self.inline.list(message, strings)

    @loader.command()
    async def clearmodules(self, message: Message):
        """Unload all external modules (with confirmation)"""
        await self.inline.form(
            self.strings("confirm_clearmodules"),
            message,
            reply_markup=[
                {
                    "text": self.strings("clearmodules"),
                    "callback": self._inline__clearmodules,
                },
                {
                    "text": self.strings("cancel"),
                    "action": "close",
                },
            ],
        )

    async def _inline__clearmodules(self, call: InlineCall):
        self.set("loaded_modules", {})

        for mod in [mod for mod in self.allmodules.modules if not mod.__origin__.startswith("<core")]:
            with contextlib.suppress(Exception):
                await self.allmodules.unload_module(mod.__class__.__name__)

        await call.edit("✅ <b>All external modules unloaded</b>")
