"""
Системный модуль управления модулями и администраторами
"""
import logging
import os
import sys
import aiohttp
from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.config import Config
from core.localization import Localization
from core.module_loader import ModuleInfo
from core.database import Admin, ModuleRecord

logger = logging.getLogger(__name__)

# Глобальные переменные для доступа из обработчиков
bot: Bot = None
dp: Dispatcher = None
config: Config = None
lang: Localization = None
module_loader = None


async def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    if user_id == config.admin_id:
        return True
    return await Admin.is_admin(user_id)


async def admin_required(message: Message):
    """Проверка прав администратора"""
    if not await is_admin(message.from_user.id):
        await message.answer(lang.get("not_admin"))
        return False
    return True


async def load_module_handler(message: Message):
    """Загрузка модуля из файла"""
    if not await admin_required(message):
        return
    
    try:
        if not message.reply_to_message or not message.reply_to_message.document:
            await message.answer(lang.get("reply_to_file"))
            return
        
        document = message.reply_to_message.document
        
        if not document.file_name.endswith('.py'):
            await message.answer(lang.get("invalid_file"))
            return
        
        module_name = document.file_name[:-3]
        
        # Проверка на конфликт имен
        if module_name in module_loader.loaded_modules:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=lang.get("yes"), callback_data=f"overwrite_lm_{module_name}"),
                    InlineKeyboardButton(text=lang.get("no"), callback_data="cancel_load")
                ]
            ])
            await message.answer(
                lang.get("module_conflict", name=module_name),
                reply_markup=keyboard
            )
            return
        
        await _load_module_from_file(message, document, module_name)
        
    except Exception as e:
        logger.error(f"Error in load_module_handler: {e}", exc_info=True)
        await message.answer(lang.get("module_error", name="unknown", error=str(e)))


async def overwrite_module_callback(callback: CallbackQuery):
    """Подтверждение перезаписи модуля"""
    try:
        module_name = callback.data.split("_", 2)[2]
        document = callback.message.reply_to_message.document
        
        await _load_module_from_file(callback.message, document, module_name, overwrite=True)
        await callback.answer()
        await callback.message.delete()
        
    except Exception as e:
        logger.error(f"Error in overwrite callback: {e}")
        await callback.answer(lang.get("module_error", name="unknown", error=str(e)))


async def cancel_load_callback(callback: CallbackQuery):
    """Отмена загрузки"""
    await callback.message.edit_text(lang.get("canceled"))
    await callback.answer()


async def _load_module_from_file(message: Message, document, module_name: str, overwrite: bool = False):
    """Загрузка модуля из файла"""
    try:
        # Определение директории
        user_modules_dir = Path("modules/user")
        file_path = user_modules_dir / f"{module_name}.py"
        
        # Скачивание файла
        file = await bot.get_file(document.file_id)
        await bot.download_file(file.file_path, file_path)
        
        # Загрузка модуля
        if overwrite:
            await module_loader.unload_module(module_name)
        
        success = await module_loader.load_module(str(file_path), module_name, is_system=False)
        
        if success:
            if overwrite:
                await message.answer(lang.get("module_updated", name=module_name))
            else:
                await message.answer(lang.get("module_loaded", name=module_name))
        else:
            await message.answer(lang.get("module_error", name=module_name, error="Ошибка регистрации"))
            
    except Exception as e:
        logger.error(f"Error loading module from file: {e}", exc_info=True)
        await message.answer(lang.get("module_error", name=module_name, error=str(e)))


async def download_load_module_handler(message: Message):
    """Загрузка модуля по URL"""
    if not await admin_required(message):
        return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(lang.get("provide_url"))
            return
        
        url = args[1]
        module_name = Path(url).stem
        
        # Проверка на конфликт имен
        if module_name in module_loader.loaded_modules:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=lang.get("yes"), callback_data=f"overwrite_dlm_{url}"),
                    InlineKeyboardButton(text=lang.get("no"), callback_data="cancel_load")
                ]
            ])
            await message.answer(
                lang.get("module_conflict", name=module_name),
                reply_markup=keyboard
            )
            return
        
        await _download_and_load_module(message, url, module_name)
        
    except Exception as e:
        logger.error(f"Error in download_load_module_handler: {e}", exc_info=True)
        await message.answer(lang.get("download_error", error=str(e)))


async def overwrite_dlm_callback(callback: CallbackQuery):
    """Подтверждение перезаписи модуля из URL"""
    try:
        url = callback.data.split("_", 2)[2]
        module_name = Path(url).stem
        
        await _download_and_load_module(callback.message, url, module_name, overwrite=True)
        await callback.answer()
        await callback.message.delete()
        
    except Exception as e:
        logger.error(f"Error in overwrite dlm callback: {e}")
        await callback.answer(lang.get("download_error", error=str(e)))


async def _download_and_load_module(message: Message, url: str, module_name: str, overwrite: bool = False):
    """Скачивание и загрузка модуля"""
    try:
        user_modules_dir = Path("modules/user")
        file_path = user_modules_dir / f"{module_name}.py"
        
        # Скачивание файла
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await message.answer(lang.get("download_error", error=f"HTTP {response.status}"))
                    return
                
                content = await response.read()
                with open(file_path, 'wb') as f:
                    f.write(content)
        
        # Загрузка модуля
        if overwrite:
            await module_loader.unload_module(module_name)
        
        success = await module_loader.load_module(str(file_path), module_name, is_system=False)
        
        if success:
            if overwrite:
                await message.answer(lang.get("module_updated", name=module_name))
            else:
                await message.answer(lang.get("module_loaded", name=module_name))
        else:
            await message.answer(lang.get("module_error", name=module_name, error="Ошибка регистрации"))
            
    except Exception as e:
        logger.error(f"Error downloading module: {e}", exc_info=True)
        await message.answer(lang.get("download_error", error=str(e)))


async def unload_module_handler(message: Message):
    """Удаление модуля"""
    if not await admin_required(message):
        return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(lang.get("provide_module_name"))
            return
        
        module_name = args[1]
        
        # Проверка существования модуля
        module_record = await ModuleRecord.get_module(module_name)
        if not module_record:
            await message.answer(lang.get("module_not_found", name=module_name))
            return
        
        # Проверка на системный модуль
        if module_record.is_system:
            await message.answer(lang.get("module_predefined", name=module_name))
            return
        
        # Удаление модуля
        await module_loader.unload_module(module_name)
        await ModuleRecord.delete_module(module_name)
        
        # Удаление файла
        file_path = Path(module_record.file_path)
        if file_path.exists():
            file_path.unlink()
        
        await message.answer(lang.get("module_deleted", name=module_name))
        
    except Exception as e:
        logger.error(f"Error in unload_module_handler: {e}", exc_info=True)
        await message.answer(lang.get("module_error", name=module_name, error=str(e)))


async def send_module_handler(message: Message):
    """Отправка файла модуля"""
    if not await admin_required(message):
        return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(lang.get("provide_module_name"))
            return
        
        module_name = args[1]
        module_record = await ModuleRecord.get_module(module_name)
        
        if not module_record:
            await message.answer(lang.get("module_not_found", name=module_name))
            return
        
        file_path = Path(module_record.file_path)
        if not file_path.exists():
            await message.answer(lang.get("module_not_found", name=module_name))
            return
        
        document = FSInputFile(file_path)
        await message.answer_document(
            document,
            caption=lang.get("module_sent", name=module_name)
        )
        
    except Exception as e:
        logger.error(f"Error in send_module_handler: {e}", exc_info=True)
        await message.answer(lang.get("module_error", name=module_name, error=str(e)))


async def add_admin_handler(message: Message):
    """Добавление администратора"""
    if not await admin_required(message):
        return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(lang.get("provide_user_id"))
            return
        
        user_id = int(args[1])
        
        if await Admin.is_admin(user_id):
            await message.answer(lang.get("admin_already", user_id=user_id))
            return
        
        await Admin.create(user_id=user_id)
        await message.answer(lang.get("admin_added", user_id=user_id))
        
    except ValueError:
        await message.answer(lang.get("provide_user_id"))
    except Exception as e:
        logger.error(f"Error in add_admin_handler: {e}", exc_info=True)


async def remove_admin_handler(message: Message):
    """Удаление администратора"""
    if not await admin_required(message):
        return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(lang.get("provide_user_id"))
            return
        
        user_id = int(args[1])
        
        admin = await Admin.filter(user_id=user_id).first()
        if admin:
            await admin.delete()
            await message.answer(lang.get("admin_removed", user_id=user_id))
        else:
            await message.answer(lang.get("module_not_found", name=str(user_id)))
        
    except ValueError:
        await message.answer(lang.get("provide_user_id"))
    except Exception as e:
        logger.error(f"Error in remove_admin_handler: {e}", exc_info=True)


async def get_log_handler(message: Message):
    """Отправка лог-файла"""
    if not await admin_required(message):
        return
    
    try:
        log_path = Path("bot.log")
        if not log_path.exists():
            await message.answer(lang.get("no_log"))
            return
        
        document = FSInputFile(log_path)
        await message.answer_document(document, caption=lang.get("log_sent"))
        
    except Exception as e:
        logger.error(f"Error in get_log_handler: {e}", exc_info=True)


async def restart_handler(message: Message):
    """Перезапуск бота"""
    if not await admin_required(message):
        return
    
    try:
        await message.answer(lang.get("restart_msg"))
        
        # Перезапуск
        os.execv(sys.executable, [sys.executable] + sys.argv)
        
    except Exception as e:
        logger.error(f"Error in restart_handler: {e}", exc_info=True)


async def help_admin_handler(message: Message):
    """Справка по административным командам"""
    if not await admin_required(message):
        return
    
    try:
        help_text = lang.get("help_admin_title")
        
        # Системные модули
        system_modules = module_loader.get_all_system_modules()
        if system_modules:
            help_text += lang.get("help_system_modules")
            for name, info in system_modules.items():
                # Экранирование специальных символов HTML
                safe_name = name.replace('<', '&lt;').replace('>', '&gt;')
                safe_desc = info.description.replace('<', '&lt;').replace('>', '&gt;') if info.description else ""
                
                help_text += f"\n<b>{safe_name}</b>"
                if safe_desc:
                    help_text += f" - {safe_desc}"
                if info.commands:
                    for cmd, desc in info.commands.items():
                        safe_cmd = cmd.replace('<', '&lt;').replace('>', '&gt;')
                        safe_cmd_desc = desc.replace('<', '&lt;').replace('>', '&gt;')
                        help_text += f"\n  /{safe_cmd} - {safe_cmd_desc}"
                help_text += "\n"
        
        await message.answer(help_text)
        
    except Exception as e:
        logger.error(f"Error in help_admin_handler: {e}", exc_info=True)
        # Отправка ошибки без HTML разметки
        await message.answer(f"Ошибка при формировании справки: {str(e)}")


async def help_user_handler(message: Message):
    """Справка по пользовательским командам"""
    try:
        # Проверка доступа
        is_user_admin = await is_admin(message.from_user.id)
        if not config.public_user_modules and not is_user_admin:
            await message.answer(lang.get("not_admin"))
            return
        
        help_text = lang.get("help_user_title")
        
        # Пользовательские модули
        user_modules = module_loader.get_all_user_modules()
        if user_modules:
            help_text += lang.get("help_user_modules")
            for name, info in user_modules.items():
                # Экранирование специальных символов HTML
                safe_name = name.replace('<', '&lt;').replace('>', '&gt;')
                safe_desc = info.description.replace('<', '&lt;').replace('>', '&gt;') if info.description else ""
                
                help_text += f"\n<b>{safe_name}</b>"
                if safe_desc:
                    help_text += f" - {safe_desc}"
                if info.commands:
                    for cmd, desc in info.commands.items():
                        safe_cmd = cmd.replace('<', '&lt;').replace('>', '&gt;')
                        safe_cmd_desc = desc.replace('<', '&lt;').replace('>', '&gt;')
                        help_text += f"\n  /{safe_cmd} - {safe_cmd_desc}"
                help_text += "\n"
        else:
            help_text += lang.get("no_modules")
        
        await message.answer(help_text)
        
    except Exception as e:
        logger.error(f"Error in help_user_handler: {e}", exc_info=True)
        # Отправка ошибки без HTML разметки
        await message.answer(f"Ошибка при формировании справки: {str(e)}")


async def register(bot_instance: Bot, dp_instance: Dispatcher, 
                   config_instance: Config, lang_instance: Localization) -> ModuleInfo:
    """Регистрация модуля"""
    global bot, dp, config, lang, module_loader
    
    bot = bot_instance
    dp = dp_instance
    config = config_instance
    lang = lang_instance
    
    # Получение module_loader из dispatcher
    module_loader = dp.get('module_loader')
    
    # Регистрация обработчиков
    dp.message.register(load_module_handler, Command("lm"))
    dp.message.register(download_load_module_handler, Command("dlm"))
    dp.message.register(unload_module_handler, Command("ulm"))
    dp.message.register(send_module_handler, Command("ml"))
    dp.message.register(add_admin_handler, Command("addadmin"))
    dp.message.register(remove_admin_handler, Command("rmadmin"))
    dp.message.register(get_log_handler, Command("getlog"))
    dp.message.register(restart_handler, Command("restart"))
    dp.message.register(help_admin_handler, Command("helpadmin"))
    dp.message.register(help_user_handler, Command("helpuser"))
    
    # Регистрация callback handlers
    dp.callback_query.register(overwrite_module_callback, F.data.startswith("overwrite_lm_"))
    dp.callback_query.register(overwrite_dlm_callback, F.data.startswith("overwrite_dlm_"))
    dp.callback_query.register(cancel_load_callback, F.data == "cancel_load")
    
    return ModuleInfo(
        name="manager",
        description="Управление модулями и администраторами",
        commands={
            "lm": "Загрузить модуль из файла",
            "dlm": "Загрузить модуль по URL",
            "ulm": "Удалить модуль",
            "ml": "Отправить файл модуля",
            "addadmin": "Добавить администратора",
            "rmadmin": "Удалить администратора",
            "getlog": "Получить лог-файл",
            "restart": "Перезапустить бота",
            "helpadmin": "Административная справка",
            "helpuser": "Пользовательская справка"
        },
        is_system=True
    )
