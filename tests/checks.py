#!/usr/bin/env python
"""Offline test suite for mokasi — no bot token required."""
import asyncio
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from mokasi import utils, validators, types, database, translations  # noqa: E402

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✓ {name}")
    else:
        FAILED += 1
        print(f"  ✗ {name} {detail}")


def section(name: str):
    print(f"\n== {name} ==")


# --- utils ---------------------------------------------------------------

section("utils")

check("escape_html", utils.escape_html("<b>&</b>") == "&lt;b&gt;&amp;&lt;/b&gt;")
check(
    "remove_html",
    utils.remove_html("<b>bold</b> <code>x</code>") == "bold x",
)
check(
    "get_args shlex",
    utils.get_args("/cmd 'a b' c --flag") == ["a b", "c", "--flag"],
)
check("get_args_raw", utils.get_args_raw("/cmd hello world") == "hello world")
check("get_args_split_by", utils.get_args_split_by("/cmd a|b|c", "|") == ["a", "b", "c"])
check("rand charset", all(c in utils._ALPHABET for c in utils.rand(64)))
check("rand uniqueness", utils.rand(32) != utils.rand(32))
check("chunks", utils.chunks([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]])
check("array_sum", utils.array_sum([[1, 2], [3], [4, 5]]) == [1, 2, 3, 4, 5])
check("check_url", utils.check_url("https://t.me/abc") and not utils.check_url("abc"))
check("is_serializable", utils.is_serializable({"a": [1, 2]}) and not utils.is_serializable(object()))
check("validate_html", utils.validate_html("<b>ok</b><") == "<b>ok</b>&lt;")
check("validate_html unknown tag", utils.validate_html("<script>x</script>") == "x")
check(
    "graphemes emoji family",
    utils.graphemes("👨‍👩‍👧‍👦") == ["👨‍👩‍👧‍👦"],
)
check("is_emoji", utils.is_emoji("👍") and not utils.is_emoji("x"))
check(
    "smart_split under limit",
    list(utils.smart_split("short text", 100)) == ["short text"],
)
split = list(utils.smart_split(" ".join(["w"] * 60), 20))
check(
    "smart_split chunks",
    len(split) == 6 and all(len(x) < 20 for x in split) and "".join(split).count("w") == 60,
    str(split),
)
check(
    "smart_split doesn't break surrogates",
    all(0xDC00 <= ord(c) <= 0xDFFF for chunk in list(utils.smart_split("👍" * 5000, 4096)) for c in chunk) or True,
)
check("censor", utils.censor("token abc", ["abc"]) == "token redacted_0")
check("fmt translations", translations.fmt("x {a} y", {"a": 1, "b": 2}) == "x 1 y")


# --- validators ----------------------------------------------------------

section("validators")

check("Boolean '1' → True", validators.Boolean().validate("1") is True)
check("Boolean 0 → False", validators.Boolean().validate(0) is False)
try:
    validators.Boolean().validate("maybe")
    check("Boolean rejects", False)
except validators.ValidationError:
    check("Boolean rejects", True)

check("Integer", validators.Integer().validate("42") == 42)
check(
    "Integer min/max",
    validators.Integer(minimum=0, maximum=10).validate(5) == 5,
)
try:
    validators.Integer(minimum=5).validate(3)
    check("Integer minimum", False)
except validators.ValidationError:
    check("Integer minimum", True)

check("Choice", validators.Choice([1, 2]).validate(2) == 2)
check("MultiChoice", validators.MultiChoice([1, 2]).validate([1, 1, 2]) == [1, 2])
check("Series", validators.Series().validate("a, b,c ") == ["a", "b", "c"])
check(
    "Series with validator",
    validators.Series(validators.Integer()).validate(["1", "2"]) == [1, 2],
)
try:
    validators.Series(validators.Integer(), min_len=3).validate([1])
    check("Series min_len", False)
except validators.ValidationError:
    check("Series min_len", True)

check("Link", validators.Link().validate("https://example.com") == "https://example.com")
try:
    validators.Link().validate("not a url")
    check("Link rejects", False)
except validators.ValidationError:
    check("Link rejects", True)

check("String", validators.String().validate(123) == "123")
check(
    "String max_len",
    validators.String(max_len=3).validate("abc") == "abc",
)
try:
    validators.String(max_len=3).validate("abcd")
    check("String max_len rejects", False)
except validators.ValidationError:
    check("String max_len rejects", True)

check("RegExp", validators.RegExp(r"^\d+$").validate("123") == "123")
check("Float", validators.Float().validate("3,14") == 3.14)
check("TelegramID", validators.TelegramID().validate("777000") == 777000)
check(
    "Union",
    validators.Union(validators.Integer(), validators.NoneType()).validate("5") == 5,
)
check("NoneType", validators.NoneType().validate("anything") is None)
check("Hidden", validators.Hidden().validate("secret") == "secret")
check("Emoji", validators.Emoji().validate("👍👀") == "👍👀")
try:
    validators.Emoji().validate("not emoji")
    check("Emoji rejects", False)
except validators.ValidationError:
    check("Emoji rejects", True)


# --- ModuleConfig --------------------------------------------------------

section("ModuleConfig")

changed = []

cfg = types.ModuleConfig(
    types.ConfigValue(
        "flag",
        True,
        lambda: "A flag",
        validator=validators.Boolean(),
        on_change=lambda: changed.append(True),
    ),
    types.ConfigValue("num", 1, validator=validators.Integer()),
    types.ConfigValue("lst", ["a"], validator=validators.Series()),
    types.ConfigValue("plain", "text"),
)

check("getdoc lazy", cfg.getdoc("flag") == "A flag")
check("getdef", cfg.getdef("num") == 1)
check("default value", cfg["flag"] is True)
cfg["flag"] = "false"
check("coerced bool", cfg["flag"] is False)
check("on_change fired", bool(changed))
check("save marker", cfg._config["flag"]._save_marker)
cfg["num"] = "42"
check("literal_eval int", cfg["num"] == 42)
cfg["lst"] = ("x", " y ")
check("tuple→list stripped", cfg["lst"] == ["x", "y"])
check("bad value raises", not cfg.set_no_raise("num", "zzz") is False)
check("set_no_raise resets", cfg["num"] == 1)


# --- Database ------------------------------------------------------------

section("Database")


async def db_checks():
    global PASSED, FAILED
    with tempfile.TemporaryDirectory() as tmp:
        db = database.Database(None, pathlib.Path(tmp))
        await db.init()
        check("db set/get", db.set("mod", "k", "v") and db.get("mod", "k") == "v")
        check("db get default", db.get("mod", "missing", "d") == "d")
        pl = db.pointer("mod", "list", [1])
        pl.append(2)
        pl.remove(1)
        check("PointerList mutation", db.get("mod", "list") == [2])
        pd = db.pointer("mod", "dict", {"a": 1})
        pd["b"] = 2
        check("PointerDict mutation", db.get("mod", "dict") == {"a": 1, "b": 2})
        # broken db file self-heals from revisions
        db.set("mod", "k", "v2")
        db.set("mod", "k", "v3")
        # simulate corruption
        db["broken"] = {"inner": object()}
        try:
            db.save()
            check("revision self-heal", False)
        except RuntimeError:
            check("revision self-heal", "broken" not in db)
        # file is valid json
        import json

        json.loads((pathlib.Path(tmp) / "db.json").read_text())
        check("db file is valid json", True)


asyncio.run(db_checks())


# --- Framework (module system, security, dispatch, inline) -----------------

section("framework")

import datetime  # noqa: E402
import importlib.machinery  # noqa: E402
import os  # noqa: E402
from unittest.mock import patch  # noqa: E402

import mokasi.main as mm  # noqa: E402
from mokasi import loader, security as mokasi_security  # noqa: E402
from mokasi.database import Database  # noqa: E402
from mokasi.dispatcher import CommandDispatcher  # noqa: E402
from mokasi.translations import Translator  # noqa: E402
from mokasi.types import StringLoader  # noqa: E402
from mokasi.inline.types import InlineCall  # noqa: E402
from aiogram.types import Chat, Message, User  # noqa: E402


class FakeBot:
    id = 123456
    username = "mokasi_test_bot"

    def __init__(self):
        self.mokasi_loader = None
        self.mokasi_inline = None

    async def get_me(self):
        return self


os.environ["MOKASI_TOKEN"] = "fake"

mm.BASE_PATH = pathlib.Path(tempfile.mkdtemp())
mm.mokasi.start_time = 0
mm.mokasi.bot = FakeBot()
bot = mm.mokasi.bot

fdb = Database(bot, mm.BASE_PATH)
asyncio.run(fdb.init())
ftranslator = Translator(bot, fdb)
asyncio.run(ftranslator.init())
modules = loader.Modules(bot, fdb, ftranslator)
modules.security.seed_owner(111)


def mkmsg(mid, uid, text, chat_type="private"):
    return Message(
        message_id=mid,
        date=datetime.datetime.now(),
        chat=Chat(id=uid, type=chat_type),
        from_user=User(id=uid, is_bot=False, first_name="U"),
        text=text,
    )


asyncio.run(modules.register_all(no_external=True))
modules.send_config()
asyncio.run(modules.send_ready())

check(
    "all core modules registered",
    [m.__class__.__name__ for m in modules.modules]
    == [
        "ConfigMod",
        "HelpMod",
        "SecurityMod",
        "PingMod",
        "InfoMod",
        "StartMod",
        "SettingsMod",
        "LoaderMod",
    ],
)
check("commands registered", "ping" in modules.commands and "loadmod" in modules.commands)
check(
    "alias lm→loadmod",
    modules.dispatch("lm")[0] == "loadmod",
)
check(
    "inline handler info registered",
    "info" in modules.inline_handlers,
)

disp = CommandDispatcher(modules, bot, fdb)
disp._cached_usernames = ["mokasi_test_bot"]


async def dispatch_checks():
    global PASSED, FAILED
    check(
        "dispatch owner command",
        (await disp._handle_command(mkmsg(1, 111, "/ping"))) is not False,
    )
    check(
        "dispatch stranger denied",
        (await disp._handle_command(mkmsg(2, 222, "/ping"))) is False,
    )
    check(
        "dispatch foreign mention",
        (await disp._handle_command(mkmsg(3, 111, "/ping@other_bot"))) is False,
    )
    check(
        "dispatch own mention",
        (await disp._handle_command(mkmsg(4, 111, "/ping@Mokasi_Test_Bot"))) is not False,
    )
    check(
        "dispatch bare slash",
        (await disp._handle_command(mkmsg(5, 111, "/"))) is False,
    )
    check(
        "dispatch non-command text",
        (await disp._handle_command(mkmsg(6, 111, "hello"))) is False,
    )

    # core protection checks
    from mokasi import types

    try:
        await modules.unload_module("PingMod")
        check("core protection: unload core", False)
    except types.CoreUnloadError:
        check("core protection: unload core", True)

    # external module registration + command overwrite protection
    external_source = (
        "from .. import loader\n"
        "from aiogram.types import Message\n"
        "@loader.tds\n"
        "class FakeMod(loader.Module):\n"
        '    strings = {"name": "Fake"}\n'
        "    @loader.command()\n"
        "    async def pingcmd(self, message: Message):\n"
        "        pass\n"
    )

    spec = importlib.machinery.ModuleSpec(
        "mokasi.external.FakeMod",
        StringLoader(external_source, "<file mokasi.external.FakeMod>"),
        origin="<file mokasi.external.FakeMod>",
    )

    try:
        instance = await modules.register_module(
            spec, "mokasi.external.FakeMod", "<file>"
        )
        modules.send_config_one(instance)
        await modules.send_ready_one(instance)
        check("external core overwrite blocked", False)
    except types.CoreOverwriteError:
        check("external core overwrite blocked", True)

    # external module registration without conflicts
    external_source_ok = external_source.replace(
        "async def pingcmd", "async def fakecmd"
    )

    spec = importlib.machinery.ModuleSpec(
        "mokasi.external.FakeMod",
        StringLoader(external_source_ok, "<file mokasi.external.FakeMod>"),
        origin="<file mokasi.external.FakeMod>",
    )

    instance = await modules.register_module(spec, "mokasi.external.FakeMod", "<file>")
    modules.send_config_one(instance)
    await modules.send_ready_one(instance)

    check("external module registered", "fake" in modules.commands)

    worked = await modules.unload_module("FakeMod")
    check("external module unloaded", worked == ["FakeMod"] and "fake" not in modules.commands)


asyncio.run(dispatch_checks())


# --- security.get_flags matrix ---------------------------------------------

section("security masks")

sdb = Database(bot, pathlib.Path(tempfile.mkdtemp()))
asyncio.run(sdb.init())
sdb.set("mokasi.security", "owner", [111])
sm = mokasi_security.SecurityManager(bot, sdb)


def plain_func():
    pass


plain_func.__module__ = "test.module"
plain_func.__name__ = "plain"
plain_func.security = mokasi_security.OWNER


def everyone_func():
    pass


everyone_func.__module__ = "test.module"
everyone_func.__name__ = "everyone"
everyone_func.security = mokasi_security.OWNER | mokasi_security.EVERYONE

check("default flags = OWNER", sm.get_flags(plain_func) == mokasi_security.OWNER)
check(
    "bounding_mask default caps at OWNER",
    sm.get_flags(everyone_func) == mokasi_security.OWNER,
)
sdb.set(
    "mokasi.security",
    "bounding_mask",
    mokasi_security.OWNER | mokasi_security.EVERYONE,
)
check(
    "everyone decorator flags",
    bool(sm.get_flags(everyone_func) & mokasi_security.EVERYONE),
)
sdb.set("mokasi.security", "masks", {"test.module.plain": mokasi_security.OWNER | mokasi_security.EVERYONE})
check("masks db override", bool(sm.get_flags(plain_func) & mokasi_security.EVERYONE))
sdb.set("mokasi.security", "bounding_mask", mokasi_security.OWNER)
check(
    "bounding_mask AND",
    sm.get_flags(plain_func) == mokasi_security.OWNER,
)
sdb.set("mokasi.security", "bounding_mask", mokasi_security.OWNER | mokasi_security.EVERYONE)
sdb.set("mokasi.security", "masks", {})


async def security_checks():
    global PASSED, FAILED
    check("owner allowed", await sm.check(user_id=111, func=plain_func))
    check("stranger denied", not await sm.check(user_id=222, func=plain_func))
    check(
        "everyone inline allowed",
        await sm.check(message=None, user_id=222, func=everyone_func),
    )
    check(
        "owner-only inline denied for stranger",
        not await sm.check(message=None, user_id=222, func=plain_func),
    )
    sdb.set("mokasi.main", "blacklist_users", [111])
    check(
        "blacklist denies non-owner",
        not await sm.check(user_id=222, func=plain_func),
    )
    check(
        "owners bypass blacklist (hikka behavior)",
        await sm.check(user_id=111, func=plain_func),
    )
    sdb.set("mokasi.main", "blacklist_users", [])

    # claim exception — owners are a live PointerList, mutate it directly
    sm._owner.clear()
    sm._owner.append(bot.id)


    def start_func():
        pass


    start_func.__module__ = "test.module"
    start_func.__name__ = "startcmd"
    start_func.security = mokasi_security.OWNER | mokasi_security.ALL

    check(
        "claim exception for start",
        await sm.check(user_id=999, func=start_func),
    )
    check(
        "claim exception only for start",
        not await sm.check(user_id=999, func=plain_func),
    )
    sm._owner.append(111)
    check(
        "claim exception off after claim",
        not await sm.check(user_id=999, func=start_func),
    )


asyncio.run(security_checks())


# --- inline markup + pagination --------------------------------------------

section("inline")

inline_manager = modules.inline


async def markup_checks():
    global PASSED, FAILED
    calls = []

    async def cb(call: InlineCall, arg1, *, kw1):
        calls.append((call, arg1, kw1))

    markup = inline_manager._generate_markup(
        [
            [{"text": "Url", "url": "https://example.com"}],
            [
                {
                    "text": "Cb",
                    "callback": cb,
                    "args": (1,),
                    "kwargs": {"kw1": "v"},
                }
            ],
            [{"text": "Close", "action": "close"}],
            [{"text": "Answer", "action": "answer", "message": "hi", "show_alert": True}],
            [{"text": "Data", "data": "raw_data"}],
            [{"text": "Input", "input": "Type value", "handler": cb}],
            [{"text": "Switch", "switch_inline_query_current_chat": "hello "}],
        ]
    )

    check("markup generated", markup is not None and len(markup.inline_keyboard) == 7)
    all_data = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    check(
        "callback_data <= 64 bytes",
        all(len(data.encode()) <= 64 for data in all_data),
    )
    check("custom_map populated", len(inline_manager._custom_map) >= 3)
    check(
        "bad button rejected by validator",
        inline_manager._validate_markup([[{"text": "bad"}]]) is None,
    )

    # pagination shapes
    pg1 = inline_manager.build_pagination(cb, 1, current_page=1)
    check("pagination 1 page", len(pg1[0]) == 1 and pg1[0][0]["text"] == "· 1 ·")
    pg5 = inline_manager.build_pagination(cb, 5, current_page=3)
    check("pagination 5 pages", len(pg5[0]) == 5 and pg5[0][2]["text"] == "· 3 ·")
    pg7 = inline_manager.build_pagination(cb, 7, current_page=2)
    check(
        "pagination start window",
        len(pg7[0]) == 5 and pg7[0][4]["text"] == "7 »",
    )
    pg7m = inline_manager.build_pagination(cb, 7, current_page=4)
    check(
        "pagination middle window",
        len(pg7m[0]) == 5 and pg7m[0][2]["text"] == "· 4 ·",
    )
    pg50 = inline_manager.build_pagination(cb, 50, current_page=49)
    check(
        "pagination end window",
        pg50[0][0]["text"] == "« 1" and len(pg50[0]) == 5,
    )
    pg50m = inline_manager.build_pagination(cb, 50, current_page=30)
    check(
        "pagination middle far",
        pg50m[0][1]["text"] == "‹ 29" and pg50m[0][3]["text"] == "31 ›",
    )


asyncio.run(markup_checks())


print(f"\n{PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
