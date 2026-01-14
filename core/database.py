import logging
from tortoise import Tortoise, fields
from tortoise.models import Model
from typing import List, Optional

logger = logging.getLogger(__name__)


class Admin(Model):
    """Модель администратора"""
    id = fields.IntField(pk=True)
    user_id = fields.BigIntField(unique=True, index=True)
    added_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "admins"
    
    @classmethod
    async def is_admin(cls, user_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        try:
            return await cls.filter(user_id=user_id).exists()
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False
    
    @classmethod
    async def get_all_admin_ids(cls) -> List[int]:
        """Получение всех ID администраторов"""
        try:
            admins = await cls.all().values_list('user_id', flat=True)
            return list(admins)
        except Exception as e:
            logger.error(f"Error getting admin IDs: {e}")
            return []


class ModuleRecord(Model):
    """Модель модуля"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, unique=True, index=True)
    file_path = fields.TextField()
    is_system = fields.BooleanField(default=False)
    is_active = fields.BooleanField(default=True)
    added_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    
    class Meta:
        table = "modules"
    
    @classmethod
    async def add_module(cls, name: str, file_path: str, is_system: bool = False):
        """Добавление или обновление модуля"""
        try:
            module, created = await cls.get_or_create(
                name=name,
                defaults={'file_path': file_path, 'is_system': is_system}
            )
            if not created:
                module.file_path = file_path
                module.is_active = True
                await module.save()
            return module
        except Exception as e:
            logger.error(f"Error adding module: {e}")
            raise
    
    @classmethod
    async def get_module(cls, name: str) -> Optional['ModuleRecord']:
        """Получение модуля по имени"""
        try:
            return await cls.filter(name=name).first()
        except Exception as e:
            logger.error(f"Error getting module: {e}")
            return None
    
    @classmethod
    async def delete_module(cls, name: str) -> bool:
        """Удаление модуля"""
        try:
            module = await cls.get_module(name)
            if module and not module.is_system:
                await module.delete()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting module: {e}")
            return False
    
    @classmethod
    async def get_all_modules(cls, is_system: Optional[bool] = None) -> List['ModuleRecord']:
        """Получение всех модулей"""
        try:
            query = cls.filter(is_active=True)
            if is_system is not None:
                query = query.filter(is_system=is_system)
            return await query.all()
        except Exception as e:
            logger.error(f"Error getting modules: {e}")
            return []


class ErrorLog(Model):
    """Модель лога ошибок"""
    id = fields.IntField(pk=True)
    module_name = fields.CharField(max_length=255, null=True)
    error_type = fields.CharField(max_length=255)
    error_message = fields.TextField()
    traceback = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "error_logs"
    
    @classmethod
    async def log_error(cls, error_type: str, error_message: str, 
                       module_name: Optional[str] = None, traceback: Optional[str] = None):
        """Логирование ошибки в БД"""
        try:
            await cls.create(
                module_name=module_name,
                error_type=error_type,
                error_message=error_message,
                traceback=traceback
            )
        except Exception as e:
            logger.error(f"Error logging to database: {e}")


async def init_db():
    """Инициализация базы данных"""
    try:
        await Tortoise.init(
            db_url='sqlite://bot.db',
            modules={'models': ['core.database']}
        )
        await Tortoise.generate_schemas()
        logger.info("Database initialized successfully")
        
        # Инициализация главного админа из конфига
        from core.config import Config
        config = Config()
        if config.admin_id:
            admin_exists = await Admin.filter(user_id=config.admin_id).exists()
            if not admin_exists:
                await Admin.create(user_id=config.admin_id)
                logger.info(f"Main admin {config.admin_id} initialized")
                
    except Exception as e:
        logger.error(f"Database initialization error: {e}", exc_info=True)
        raise
