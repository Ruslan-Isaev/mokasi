# Mokasi — a modular personal Telegram bot framework
# Translation system, ported from Hikka (https://github.com/hikariatama/Hikka)
# and simplified: JSON langpacks only, built-in validator strings
import json
import logging
import typing
from pathlib import Path

from . import utils
from .database import Database

logger = logging.getLogger(__name__)

PACKS = Path(__file__).parent / "langpacks"

SUPPORTED_LANGUAGES = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
}

# Built-in strings, used to render validator documentation.
# Structure: {string_id: {lang: text}}
VALIDATOR_STRINGS = {
    "validators.boolean": {
        "en": "Boolean",
        "ru": "Логическое значение",
    },
    "validators.positive": {
        "en": "positive",
        "ru": "положительное",
    },
    "validators.negative": {
        "en": "negative",
        "ru": "отрицательное",
    },
    "validators.digits": {
        "en": ", must contain exactly {digits} digits",
        "ru": ", должно содержать ровно {digits} цифр",
    },
    "validators.integer": {
        "en": "{sign} Integer",
        "ru": "Целое число{sign}",
    },
    "validators.integer_min": {
        "en": "{sign} Integer, which is >= {minimum}{digits}",
        "ru": "Целое число{sign}, которое >= {minimum}{digits}",
    },
    "validators.integer_max": {
        "en": "{sign} Integer, which is <= {maximum}{digits}",
        "ru": "Целое число{sign}, которое <= {maximum}{digits}",
    },
    "validators.integer_range": {
        "en": "{sign} Integer, which is {minimum} <= value <= {maximum}{digits}",
        "ru": "Целое число{sign}, которое {minimum} <= значение <= {maximum}{digits}",
    },
    "validators.choice": {
        "en": "One of the following: {possible}",
        "ru": "Одно из следующих значений: {possible}",
    },
    "validators.multichoice": {
        "en": "Multiple values of the following: {possible}",
        "ru": "Несколько значений из следующих: {possible}",
    },
    "validators.each": {
        "en": ", each of which is {each}",
        "ru": ", каждое из которых {each}",
    },
    "validators.series": {
        "en": "Sequence of values{each}{len}",
        "ru": "Последовательность значений{each}{len}",
    },
    "validators.fixed_len": {
        "en": ", which must contain exactly {fixed_len} items",
        "ru": ", которая должна содержать ровно {fixed_len} элементов",
    },
    "validators.max_len": {
        "en": ", which must contain up to {max_len} items",
        "ru": ", которая должна содержать до {max_len} элементов",
    },
    "validators.min_len": {
        "en": ", which must contain at least {min_len} items",
        "ru": ", которая должна содержать минимум {min_len} элементов",
    },
    "validators.len_range": {
        "en": ", which must contain from {min_len} to {max_len} items",
        "ru": ", которая должна содержать от {min_len} до {max_len} элементов",
    },
    "validators.link": {
        "en": "Valid URL",
        "ru": "Корректный URL",
    },
    "validators.string": {
        "en": "String",
        "ru": "Строка",
    },
    "validators.string_fixed_len": {
        "en": "String, which is exactly {length} characters long",
        "ru": "Строка, которая состоит ровно из {length} символов",
    },
    "validators.string_max_len": {
        "en": "String, which is up to {max_len} characters long",
        "ru": "Строка, которая состоит максимум из {max_len} символов",
    },
    "validators.string_min_len": {
        "en": "String, which is at least {min_len} characters long",
        "ru": "Строка, которая состоит минимум из {min_len} символов",
    },
    "validators.string_len_range": {
        "en": "String, which is from {min_len} to {max_len} characters long",
        "ru": "Строка, которая состоит из {min_len}–{max_len} символов",
    },
    "validators.regex": {
        "en": "Value matching the following regex: {regex}",
        "ru": "Значение, соответствующее регулярному выражению: {regex}",
    },
    "validators.float": {
        "en": "{sign} Float",
        "ru": "Число с плавающей точкой{sign}",
    },
    "validators.float_min": {
        "en": "{sign} Float, which is >= {minimum}",
        "ru": "Число с плавающей точкой{sign}, которое >= {minimum}",
    },
    "validators.float_max": {
        "en": "{sign} Float, which is <= {maximum}",
        "ru": "Число с плавающей точкой{sign}, которое <= {maximum}",
    },
    "validators.float_range": {
        "en": "{sign} Float, which is {minimum} <= value <= {maximum}",
        "ru": "Число с плавающей точкой{sign}, которое {minimum} <= значение <= {maximum}",
    },
    "validators.empty": {
        "en": "Empty value",
        "ru": "Пустое значение",
    },
    "validators.union": {
        "en": "Value matching one of the following:\n",
        "ru": "Значение, соответствующее одному из следующих:\n",
    },
    "validators.emoji": {
        "en": "Emoji",
        "ru": "Эмодзи",
    },
    "validators.emoji_fixed_len": {
        "en": "Emoji, which is exactly {length} emojis long",
        "ru": "Эмодзи, которое состоит ровно из {length} эмодзи",
    },
    "validators.emoji_min_len": {
        "en": "Emoji, which is at least {min_len} emojis long",
        "ru": "Эмодзи, которое состоит минимум из {min_len} эмодзи",
    },
    "validators.emoji_max_len": {
        "en": "Emoji, which is up to {max_len} emojis long",
        "ru": "Эмодзи, которое состоит максимум из {max_len} эмодзи",
    },
    "validators.emoji_len_range": {
        "en": "Emoji, which is from {min_len} to {max_len} emojis long",
        "ru": "Эмодзи, которое состоит из {min_len}–{max_len} эмодзи",
    },
    "validators.entity_like": {
        "en": "Entity link or ID",
        "ru": "Ссылка на сущность или ID",
    },
}


def fmt(text: str, kwargs: dict) -> str:
    for key, value in kwargs.items():
        if f"{{{key}}}" in text:
            text = text.replace(f"{{{key}}}", str(value))

    return text


class BaseTranslator:
    def _get_pack_content(
        self,
        pack: Path,
        prefix: str = "mokasi.modules.",
    ) -> typing.Optional[dict]:
        return self._get_pack_raw(pack.read_text(), prefix)

    def _get_pack_raw(
        self,
        content: str,
        prefix: str = "mokasi.modules.",
    ) -> typing.Optional[dict]:
        content = json.loads(content)
        if all(len(key) == 2 for key in content):
            # Multi-language pack
            return {
                language: {
                    f"{module.strip('$')}.{key}"
                    if module.startswith("$")
                    else f"{prefix}{module}.{key}": value
                    for module, strings in pack.items()
                    for key, value in strings.items()
                    if key != "name"
                }
                for language, pack in content.items()
            }

        return {
            (
                f"{module.strip('$')}.{key}"
                if module.startswith("$")
                else f"{prefix}{module}.{key}"
            ): value
            for module, strings in content.items()
            for key, value in strings.items()
            if key != "name"
        }

    def getkey(self, key: str) -> typing.Any:
        return self._data.get(key, False)

    def gettext(self, text: str) -> typing.Any:
        return self.getkey(text) or text

    async def load_module_translations(self, pack_url: str) -> typing.Union[bool, dict]:
        """Load external per-module translation pack (JSON)"""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(pack_url) as resp:
                    data = await resp.json()
        except Exception:
            logger.exception("Unable to decode %s", pack_url)
            return False

        if any(len(key) != 2 for key in data):
            return data

        if lang := self.db.get(__name__, "lang", False):
            return next(
                (data[language] for language in lang.split() if language in data),
                data.get("en", {}),
            )

        return data.get("en", {})


class Translator(BaseTranslator):
    def __init__(self, client: "aiogram.Bot", db: Database):  # type: ignore  # noqa: F821
        self._client = client
        self.db = db
        self._data = {}
        self.raw_data = {}

    async def init(self) -> bool:
        any_ = False
        if lang := self.db.get(__name__, "lang", False):
            for language in lang.split():
                for possible_path in [
                    PACKS / f"{language}.json",
                ]:
                    if possible_path.exists():
                        data = self._get_pack_content(possible_path)
                        self._data.update(data)
                        self.raw_data[language] = data
                        any_ = True

        for language in SUPPORTED_LANGUAGES:
            if language not in self.raw_data and (PACKS / f"{language}.json").exists():
                self.raw_data[language] = self._get_pack_content(
                    PACKS / f"{language}.json"
                )

        return any_


class ExternalTranslator(BaseTranslator):
    """Provides translated docs for validators and other built-ins"""

    def __init__(self):
        self.data = {
            lang: {
                key: strings.get(lang, strings["en"])
                for key, strings in VALIDATOR_STRINGS.items()
            }
            for lang in SUPPORTED_LANGUAGES
        }

    def get(self, key: str, lang: str) -> str:
        return self.data[lang].get(key, False) or key

    def getdict(self, key: str, **kwargs) -> dict:
        return {
            lang: fmt(self.data[lang].get(key, False) or key, kwargs)
            for lang in self.data
        }


class Strings:
    def __init__(self, mod: "Module", translator: "Translator"):  # type: ignore  # noqa: F821
        self._mod = mod
        self._translator = translator

        if not translator:
            logger.debug("Module %s got empty translator %s", mod, translator)

        self._base_strings = mod.strings  # Back 'em up, bc they will get replaced
        self.external_strings = {}

    def get(self, key: str, lang: typing.Optional[str] = None) -> str:
        try:
            return self._translator.raw_data[lang][f"{self._mod.__module__}.{key}"]
        except KeyError:
            return self[key]

    def __getitem__(self, key: str) -> str:
        return (
            self.external_strings.get(key, None)
            or (
                self._translator.getkey(f"{self._mod.__module__}.{key}")
                if self._translator is not None
                else False
            )
            or (
                getattr(
                    self._mod,
                    next(
                        (
                            f"strings_{lang}"
                            for lang in self._translator.db.get(
                                __name__,
                                "lang",
                                "en",
                            ).split(" ")
                            if hasattr(self._mod, f"strings_{lang}")
                            and isinstance(getattr(self._mod, f"strings_{lang}"), dict)
                            and key in getattr(self._mod, f"strings_{lang}")
                        ),
                        utils.rand(32),
                    ),
                    self._base_strings,
                )
                if self._translator is not None
                else self._base_strings
            ).get(
                key,
                self._base_strings.get(key, "Unknown strings"),
            )
        )

    def __call__(
        self,
        key: str,
        _: typing.Optional[typing.Any] = None,
    ) -> str:
        return self.__getitem__(key)

    def __iter__(self):
        return self._base_strings.__iter__()


translator = ExternalTranslator()
