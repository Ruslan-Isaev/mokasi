import importlib
import importlib.util
import logging
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Dict, Optional, List
from aiogram import Bot, Dispatcher

from core.config import Config
from core.localization import Localization
from core.database import ModuleRecord

logger = logging.getLogger(__name__)


class ModuleInfo:
    """Информация о модуле"""
    def __init__(self, name: str, description: str = "", commands: Dict[str, str] = None, 
                 is_system: bool = False, dependencies: List[str] = None):
        self.name = name
        self.description = description
        self.commands = commands or {}
        self.is_system = is_system
        self.dependencies = dependencies or []


class ModuleLoader:
    """Загрузчик модулей"""
    
    def __init__(self, bot: Bot, dp: Dispatcher, config: Config, localization: Localization):
        self.bot = bot
        self.dp = dp
        self.config = config
        self.localization = localization
        self.loaded_modules: Dict[str, ModuleInfo] = {}
        self.system_modules_dir = Path("modules/system")
        self.user_modules_dir = Path("modules/user")
        
        # Создание директорий
        self.system_modules_dir.mkdir(parents=True, exist_ok=True)
        self.user_modules_dir.mkdir(parents=True, exist_ok=True)
    
    async def load_all_modules(self):
        """Загрузка всех модулей при запуске"""
        try:
            # Загрузка системных модулей
            await self._load_modules_from_directory(self.system_modules_dir, is_system=True)
            
            # Загрузка пользовательских модулей
            await self._load_modules_from_directory(self.user_modules_dir, is_system=False)
            
            logger.info(f"Total modules loaded: {len(self.loaded_modules)}")
            
        except Exception as e:
            logger.error(f"Error loading modules: {e}", exc_info=True)
    
    async def _load_modules_from_directory(self, directory: Path, is_system: bool):
        """Загрузка модулей из директории"""
        try:
            for file_path in directory.glob("*.py"):
                if file_path.name.startswith("_"):
                    continue
                
                module_name = file_path.stem
                try:
                    await self.load_module(str(file_path), module_name, is_system)
                except Exception as e:
                    logger.error(f"Failed to load module {module_name}: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Error loading from directory {directory}: {e}")
    
    async def load_module(self, file_path: str, module_name: str, is_system: bool = False) -> bool:
        """Загрузка отдельного модуля"""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"Module file not found: {file_path}")
                return False
            
            # Загрузка модуля
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                logger.error(f"Cannot load spec for module: {module_name}")
                return False
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            
            # Выполнение модуля
            spec.loader.exec_module(module)
            
            # Получение информации о модуле
            if not hasattr(module, 'register'):
                logger.error(f"Module {module_name} has no 'register' function")
                return False
            
            # Проверка и установка зависимостей
            if hasattr(module, 'DEPENDENCIES'):
                dependencies = getattr(module, 'DEPENDENCIES', [])
                if dependencies:
                    install_success = await self._install_dependencies(dependencies, module_name)
                    if not install_success:
                        return False
            
            # Регистрация модуля
            module_info = await module.register(self.bot, self.dp, self.config, self.localization)
            
            if isinstance(module_info, ModuleInfo):
                module_info.is_system = is_system
                self.loaded_modules[module_name] = module_info
                
                # Сохранение в БД
                await ModuleRecord.add_module(module_name, file_path, is_system)
                
                logger.info(f"Module {module_name} loaded successfully")
                return True
            else:
                logger.error(f"Module {module_name} returned invalid ModuleInfo")
                return False
                
        except Exception as e:
            logger.error(f"Error loading module {module_name}: {e}", exc_info=True)
            from core.database import ErrorLog
            await ErrorLog.log_error(
                error_type=type(e).__name__,
                error_message=str(e),
                module_name=module_name,
                traceback=traceback.format_exc()
            )
            return False
    
    async def _install_dependencies(self, dependencies: List[str], module_name: str) -> bool:
        """Установка зависимостей модуля"""
        try:
            logger.info(f"Installing dependencies for {module_name}: {dependencies}")
            
            for dep in dependencies:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", dep],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    logger.error(f"Failed to install {dep}: {result.stderr}")
                    return False
            
            logger.info(f"Dependencies installed successfully for {module_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error installing dependencies for {module_name}: {e}")
            return False
    
    async def unload_module(self, module_name: str) -> bool:
        """Выгрузка модуля"""
        try:
            if module_name in self.loaded_modules:
                # Удаление из загруженных модулей
                del self.loaded_modules[module_name]
                
                # Удаление из sys.modules
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                logger.info(f"Module {module_name} unloaded")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error unloading module {module_name}: {e}")
            return False
    
    async def reload_module(self, module_name: str) -> bool:
        """Перезагрузка модуля"""
        try:
            module_record = await ModuleRecord.get_module(module_name)
            if not module_record:
                return False
            
            # Выгрузка старого модуля
            await self.unload_module(module_name)
            
            # Загрузка нового модуля
            return await self.load_module(
                module_record.file_path,
                module_name,
                module_record.is_system
            )
            
        except Exception as e:
            logger.error(f"Error reloading module {module_name}: {e}")
            return False
    
    def get_module_info(self, module_name: str) -> Optional[ModuleInfo]:
        """Получение информации о модуле"""
        return self.loaded_modules.get(module_name)
    
    def get_all_system_modules(self) -> Dict[str, ModuleInfo]:
        """Получение всех системных модулей"""
        return {name: info for name, info in self.loaded_modules.items() if info.is_system}
    
    def get_all_user_modules(self) -> Dict[str, ModuleInfo]:
        """Получение всех пользовательских модулей"""
        return {name: info for name, info in self.loaded_modules.items() if not info.is_system}
