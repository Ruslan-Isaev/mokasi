"""
Пример пользовательского модуля
Показывает как создавать модули с доступом к БД и админам
"""
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from core.config import Config
from core.localization import Localization
from core.module_loader import ModuleInfo
from core.database import Admin

logger = logging.getLogger(__name__)

# Зависимости (если нужны)
DEPENDENCIES = ["git+https://github.com/Ruslan-Isaev/TermGPT"]

# Глобальные переменные
bot: Bot = None
dp: Dispatcher = None
config: Config = None
lang: Localization = None


async def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    if user_id == config.admin_id:
        return True
    return await Admin.is_admin(user_id)


async def example_handler(message: Message):
    """Пример команды"""
    try:
        # Проверка доступа, если модуль приватный
        if not config.public_user_modules:
            if not await is_admin(message.from_user.id):
                await message.answer("У вас нет доступа к этой команде")
                return
        
        # Получение списка админов
        admin_ids = await Admin.get_all_admin_ids()
        
        response = f"Привет, {message.from_user.first_name}!\n"
        response += f"Это пример пользовательского модуля.\n"
        response += f"Количество администраторов: {len(admin_ids)}"
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Error in example_handler: {e}", exc_info=True)
        await message.answer(f"Ошибка: {e}")


async def info_handler(message: Message):
    """Информация о боте"""
    try:
        info = f"<b>Информация о боте</b>\n\n"
        info += f"ID бота: {bot.id}\n"
        info += f"Публичные модули: {'Да' if config.public_user_modules else 'Нет'}\n"
        
        await message.answer(info)
        
    except Exception as e:
        logger.error(f"Error in info_handler: {e}", exc_info=True)


async def register(bot_instance: Bot, dp_instance: Dispatcher, 
                   config_instance: Config, lang_instance: Localization) -> ModuleInfo:
    """Регистрация модуля - вызывается при загрузке"""
    global bot, dp, config, lang
    
    bot = bot_instance
    dp = dp_instance
    config = config_instance
    lang = lang_instance
    
    # Регистрация обработчиков ВНУТРИ функции register
    dp.message.register(example_handler, Command("example"))
    dp.message.register(info_handler, Command("info"))
    
    return ModuleInfo(
        name="example",
        description="Пример пользовательского модуля",
        commands={
            "example": "Пример команды",
            "info": "Информация о боте"
        },
        is_system=False,
        dependencies=DEPENDENCIES
    )