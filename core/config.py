import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Config:
    """Класс для управления конфигурацией бота"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self._config = self._load_config()
        
    def _load_config(self) -> dict:
        """Загрузка конфигурации из файла"""
        try:
            if not self.config_path.exists():
                logger.warning(f"Config file {self.config_path} not found, creating default")
                self._create_default_config()
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("Configuration loaded successfully")
                return config
                
        except Exception as e:
            logger.error(f"Error loading config: {e}", exc_info=True)
            raise
    
    def _create_default_config(self):
        """Создание конфигурации по умолчанию"""
        default_config = {
            "ADMIN_ID": 0,
            "BOT_TOKEN": "your_token_here",
            "USE_WEBHOOK": False,
            "WEBHOOK_HOST": "https://yourdomain.com",
            "WEB_SERVER_HOST": "127.0.0.1",
            "WEB_SERVER_PORT": 8443,
            "PUBLIC_USER_MODULES": True,
            "LANG_FILE": "langs/ru.json"
        }
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
    
    def save(self):
        """Сохранение конфигурации"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}", exc_info=True)
    
    @property
    def admin_id(self) -> int:
        return self._config.get("ADMIN_ID", 0)
    
    @property
    def bot_token(self) -> str:
        return self._config.get("BOT_TOKEN", "")
    
    @property
    def use_webhook(self) -> bool:
        value = self._config.get("USE_WEBHOOK", False)
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)
    
    @property
    def webhook_host(self) -> str:
        return self._config.get("WEBHOOK_HOST", "")
    
    @property
    def web_server_host(self) -> str:
        return self._config.get("WEB_SERVER_HOST", "127.0.0.1")
    
    @property
    def web_server_port(self) -> int:
        return self._config.get("WEB_SERVER_PORT", 8443)
    
    @property
    def public_user_modules(self) -> bool:
        return self._config.get("PUBLIC_USER_MODULES", True)
    
    @property
    def lang_file(self) -> str:
        return self._config.get("LANG_FILE", "langs/ru.json")
