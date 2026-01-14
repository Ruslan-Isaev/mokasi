import asyncio
import json
import logging
import sys
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
from tortoise import Tortoise

from core.config import Config
from core.localization import Localization
from core.module_loader import ModuleLoader
from core.database import init_db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ModularBot:
    def __init__(self):
        self.config = Config()
        self.localization = Localization(self.config.lang_file)
        self.bot = Bot(
            token=self.config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dp = Dispatcher()
        self.module_loader = None
        
    async def on_startup(self):
        """Инициализация при запуске"""
        try:
            # Инициализация БД
            await init_db()
            logger.info("Database initialized")
            
            # Загрузка модулей
            self.module_loader = ModuleLoader(self.bot, self.dp, self.config, self.localization)
            # Сохраняем module_loader в dispatcher для доступа из модулей
            self.dp['module_loader'] = self.module_loader
            await self.module_loader.load_all_modules()
            logger.info("Modules loaded")
            
        except Exception as e:
            logger.error(f"Error during startup: {e}", exc_info=True)
            raise
    
    async def on_shutdown(self):
        """Очистка при остановке"""
        try:
            await Tortoise.close_connections()
            await self.bot.session.close()
            logger.info("Bot shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    async def start_polling(self):
        """Запуск через polling"""
        try:
            await self.on_startup()
            logger.info("Starting bot in polling mode")
            await self.dp.start_polling(self.bot)
        finally:
            await self.on_shutdown()
    
    async def start_webhook(self):
        """Запуск через webhook"""
        try:
            await self.on_startup()
            
            # Настройка webhook
            webhook_url = f"{self.config.webhook_host}/webhook"
            await self.bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True
            )
            
            # Создание веб-приложения
            app = web.Application()
            
            # Регистрация обработчика webhook
            from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
            webhook_handler = SimpleRequestHandler(dispatcher=self.dp, bot=self.bot)
            webhook_handler.register(app, path='/webhook')
            setup_application(app, self.dp, bot=self.bot)
            
            # Запуск веб-сервера
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(
                runner,
                host=self.config.web_server_host,
                port=self.config.web_server_port
            )
            await site.start()
            
            logger.info(f"Webhook started on {self.config.web_server_host}:{self.config.web_server_port}")
            logger.info(f"Webhook URL: {webhook_url}")
            
            # Держим бота запущенным
            await asyncio.Event().wait()
            
        finally:
            await self.on_shutdown()
    
    async def run(self):
        """Основной метод запуска"""
        try:
            if self.config.use_webhook:
                await self.start_webhook()
            else:
                await self.start_polling()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)


def main():
    """Точка входа"""
    try:
        bot = ModularBot()
        asyncio.run(bot.run())
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
