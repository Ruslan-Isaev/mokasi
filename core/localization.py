import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Localization:
    """Класс для управления локализацией"""
    
    def __init__(self, lang_file: str):
        self.lang_file = Path(lang_file)
        self._strings = self._load_strings()
    
    def _load_strings(self) -> dict:
        """Загрузка строк локализации"""
        try:
            if not self.lang_file.exists():
                logger.warning(f"Language file {self.lang_file} not found, creating default")
                self._create_default_lang()
            
            with open(self.lang_file, 'r', encoding='utf-8') as f:
                strings = json.load(f)
                logger.info(f"Localization loaded from {self.lang_file}")
                return strings
                
        except Exception as e:
            logger.error(f"Error loading localization: {e}", exc_info=True)
            return {}
    
    def _create_default_lang(self):
        """Создание файла локализации по умолчанию (русский)"""
        default_strings = {
            "welcome": "Добро пожаловать!",
            "module_loaded": "✅ Модуль <b>{name}</b> успешно загружен",
            "module_updated": "✅ Модуль <b>{name}</b> успешно обновлён",
            "module_deleted": "✅ Модуль <b>{name}</b> удалён",
            "module_error": "❌ Ошибка при загрузке модуля <b>{name}</b>:\n<code>{error}</code>",
            "module_not_found": "❌ Модуль <b>{name}</b> не найден",
            "module_conflict": "⚠️ Модуль с именем <b>{name}</b> уже существует. Хотите перезаписать?",
            "module_sent": "📄 Файл модуля <b>{name}</b>",
            "module_predefined": "❌ Невозможно удалить предустановленный модуль <b>{name}</b>",
            "module_deps_installing": "📦 Установка зависимостей для модуля <b>{name}</b>...",
            "module_deps_error": "❌ Ошибка установки зависимостей:\n<code>{error}</code>",
            "admin_added": "✅ Пользователь <b>{user_id}</b> добавлен в администраторы",
            "admin_removed": "✅ Пользователь <b>{user_id}</b> удалён из администраторов",
            "admin_already": "⚠️ Пользователь <b>{user_id}</b> уже является администратором",
            "not_admin": "❌ У вас нет прав для выполнения этой команды",
            "reply_to_file": "❌ Ответьте на сообщение с файлом .py",
            "invalid_file": "❌ Неверный формат файла. Требуется .py файл",
            "provide_url": "❌ Укажите URL для загрузки модуля",
            "provide_module_name": "❌ Укажите название модуля",
            "provide_user_id": "❌ Укажите ID пользователя",
            "download_error": "❌ Ошибка при загрузке файла:\n<code>{error}</code>",
            "restart_msg": "🔄 Перезапуск бота...",
            "log_sent": "📋 Лог-файл",
            "no_log": "❌ Лог-файл не найден",
            "help_admin_title": "🔧 <b>Административные команды</b>\n\n",
            "help_user_title": "📚 <b>Пользовательские команды</b>\n\n",
            "help_system_modules": "<b>Системные модули:</b>\n",
            "help_user_modules": "<b>Пользовательские модули:</b>\n",
            "no_modules": "Нет загруженных модулей",
            "yes": "✅ Да",
            "no": "❌ Нет",
            "canceled": "❌ Отменено"
        }
        
        self.lang_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lang_file, 'w', encoding='utf-8') as f:
            json.dump(default_strings, f, indent=4, ensure_ascii=False)
    
    def get(self, key: str, **kwargs) -> str:
        """Получение локализованной строки с форматированием"""
        try:
            string = self._strings.get(key, key)
            if kwargs:
                return string.format(**kwargs)
            return string
        except Exception as e:
            logger.error(f"Error formatting localization string '{key}': {e}")
            return key
    
    def __call__(self, key: str, **kwargs) -> str:
        """Альтернативный способ вызова"""
        return self.get(key, **kwargs)
