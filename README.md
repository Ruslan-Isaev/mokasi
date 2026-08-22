# 🌘 Mokasi

**Mokasi** — личный модульный Telegram-бот на [aiogram 3](https://github.com/aiogram/aiogram),
архитектурно вдохновлённый [Hikka Userbot](https://github.com/hikariatama/Hikka):
та же модульная система (плагины-модули с конфигами, валидаторами и переводами),
та же модель безопасности (битовые маски прав, список владельцев),
полный inline-UI (формы, списки, галереи) и нативный inline-query.

Бот доступен **только владельцу и овнерам**. Каждое сообщение, каждый callback
и каждый inline-query проходят проверку безопасности.

## Установка

```bash
cd /root/mokasi
python3 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/pip install -r requirements.txt
```

## Первый запуск

1. Создайте бота у [@BotFather](https://t.me/BotFather), получите токен.
2. Включите inline-режим: `/setinline` → выберите бота → подсказку можно оставить пустой.
3. Запустите:

```bash
MOKASI_TOKEN=123456:ABC-DEF... .venv/bin/python -m mokasi
```

Либо создайте `config.json`:

```json
{
    "token": "123456:ABC-DEF...",
    "owner": 123456789
}
```

### Владелец (owner)

Владелец определяется в таком порядке:

1. Переменная окружения `MOKASI_OWNER` (числовой Telegram ID);
2. Поле `owner` в `config.json`;
3. Если владелец не задан — **первый написавший `/start` становится владельцем**
   (одноразово, бот предупредит об этом). До этого момента бот не выполняет
   ни одной команды.

Дополнительных владельцев добавляет владелец: `/owneradd <id|@username|reply>`,
удаляет — `/ownerrm`, список — `/ownerlist`.

## Команды

| Команда | Описание |
|---|---|
| `/start` | Захват владения (одноразово) / приветствие |
| `/help` | Интерактивная справка |
| `/modhelp <модуль|команда>` | Справка по модулю или команде |
| `/ping` | Задержка, аптайм, RAM |
| `/config` | Интерактивная настройка конфигов модулей |
| `/settings` | Настройки бота (префикс, ратлимит, traceback'и, защита ядра) |
| `/security` | Маски прав команд |
| `/inlinesec` | Маски прав inline-обработчиков + ограничивающая маска |
| `/loadmod` (alias `lm`) | Загрузка модуля (файл в ответ или URL) |
| `/unloadmod` (alias `ulm`) | Выгрузка внешнего модуля |
| `/listmod` | Список внешних модулей |
| `/clearmodules` | Выгрузка всех внешних модулей |
| `/info` | Инфо о боте (inline-форма) |

Inline: `@your_bot` в поле ввода → список доступных inline-команд.
`@your_bot info` — пример обработчика, открытого для всех (`@loader.inline_everyone`).

## Написание модулей

Модуль — один файл с классом-наследником `loader.Module`. Полный пример —
в [`examples/example_mod.py`](examples/example_mod.py).

```python
from aiogram.types import Message

from .. import loader, utils
from ..inline.types import InlineCall, InlineQuery


@loader.tds
class MyMod(loader.Module):
    """Документация модуля (переводится через @loader.tds)"""

    strings = {"name": "MyMod"}          # обязательно
    strings_ru = {"name": "МойМодуль"}   # опционально

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "flag",
                True,
                lambda: self.strings("_cfg_flag"),
                validator=loader.validators.Boolean(),
            ),
        )

    @loader.command(alias="alias1")
    async def mycmd(self, message: Message):
        """Справка команды"""
        await utils.answer(message, "Hello!")

    @loader.inline_handler(thumb_url="https://...")
    async def _inline_handler(self, query: InlineQuery) -> dict:
        return {
            "title": "Заголовок",
            "description": "Описание",
            "message": "<b>Текст</b>",
            "thumb": "https://...",
            "reply_markup": [{"text": "Кнопка", "action": "close"}],
        }

    @loader.callback_handler()
    async def _callback_handler(self, call: InlineCall):
        if call.data == "my_data":
            await call.answer("Pong!")

    @loader.watcher("only_pm")
    async def watcher(self, message: Message):
        ...

    @loader.loop(interval=60)
    async def _loop(self):
        ...
```

### Соглашения

- Метод с суффиксом `cmd` → команда (`mycmd` → `/my`), `_inline_handler` →
  inline-обработчик, `_callback_handler` → глобальный callback-обработчик,
  `watcher` → watcher (запускается на каждое сообщение).
- Конфиг объявляется в `__init__`, валидируется при присваивании
  (`mod.config["flag"] = ...`) и автосохраняется в БД (цикл-автосейвер).
- БД: `self.get(key, default)`, `self.set(key, value)`,
  `self.pointer(key, default)` — ключи автоматически в неймспейсе имени класса.
- Кнопки форм: `url` / `callback` (+`args`, `kwargs`) / `input` (+`handler`) /
  `data` / `action: close|unload|answer`; безопасность кнопок:
  `always_allow`, `force_me`, `disable_security`.
- `utils.answer(message, text, reply_markup=[...])` — с `reply_markup` отправляет
  inline-форму, иначе отвечает/редактирует; длинные тексты автоматически
  разбиваются на пагинируемый список.

### Установка модуля

- `/loadmod` в ответ на файл `.py` — с вопросом о сохранении на диск
  (сохранённые модули переустанавливаются при старте);
- `/loadmod https://...` — загрузка по URL;
- `# requires: pkg1 pkg2` в начале файла — автоматическая установка
  зависимостей через pip;
- `# scope: mokasi_min 1.0.0` — минимальная версия Mokasi.

Ядро защищено: внешние модули не могут перезаписать core-команды
или выгрузить core-модули (отключается в `/settings`, не рекомендуется).

## Модель безопасности

- **Маски** — битовые флаги на функции: `OWNER` (по умолчанию) и `EVERYONE`.
  Декораторы `@loader.owner`, `@loader.inline_everyone`, `@loader.unrestricted`;
  владелец всегда имеет доступ (бит OWNER добавляется автоматически).
- **Пер-командные маски** — переопределяются в `/security` и хранятся в БД
  (`masks` по ключу `module.funcname`), применяются без перезагрузки.
- **Ограничивающая маска** (`bounding_mask`, `/inlinesec`) — глобальный потолок:
  по умолчанию OWNER, т.е. бит EVERYONE не действует, пока владелец явно
  не разрешит «всем».
- **Чёрный список** — `blacklist_users` в БД (не-овнеров).
- **Формы наследуют маску вызвавшей команды** (stack-inspection), если не задан
  `manual_security`; `always_allow` — список дополнительных пользователей,
  `force_me` — только владелец, `disable_security` — отключить проверки для формы.
- **Callback-данные** — случайные 30-символьные токены (`secrets`), состояние
  (handler, args, права) хранится на сервере, в callback_data не передаётся.
- **Claim**: до появления владельца бот не выполняет ни одной команды,
  кроме одноразового `/start`.

## Структура

```
mokasi/
├── __main__.py      # точка входа: python -m mokasi
├── main.py          # загрузка: Bot → DB → Translator → Modules → Router → polling
├── types.py         # Module, ModuleConfig/ConfigValue, исключения, интроспекция
├── loader.py        # декораторы, InfiniteLoop, реестр Modules, lifecycle
├── security.py      # маски, SecurityManager
├── dispatcher.py    # CommandDispatcher: префикс → lookup → ratelimit → security
├── database.py      # JSON-БД с кольцом ревизий
├── pointers.py      # PointerList/PointerDict
├── translations.py  # Strings-прокси + опциональные langpacks/*.json
├── validators.py    # 14 валидаторов конфигов
├── utils.py         # get_args*, escape_html, answer, smart_split...
├── inline/          # InlineManager: формы, списки, галереи, пагинация
└── modules/         # core-модули (нельзя выгрузить)
```

БД — `db.json` (JSON-словарь `{owner: {key: value}}`, кольцо из 15 ревизий
для самовосстановления при порче файла).

## Тесты

```bash
.venv/bin/python tests/checks.py
```

Офлайн-набор (98 проверок, токен не нужен): БД/pointer-ы/ревизии, конфиги
и валидаторы, маски безопасности, диспетчеризация на синтетических
сообщениях, регистрация/выгрузка модулей и защита ядра, генерация разметки,
формы пагинации.

## Отличия от Hikka

Mokasi — бот, а не юзербот: не нужен MTProto-клиент, трюк `_invoke_unit`,
групповые права и tsec. Всё остальное (контракт модулей, конфиги, строки,
безопасность, inline-UI) — максимально близко к Hikka, чтобы модули
портировались с минимальными правками.
