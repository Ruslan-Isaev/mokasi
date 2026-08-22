# Mokasi — a modular personal Telegram bot framework
# Utilities, ported from Hikka (https://github.com/hikariatama/Hikka)
# and adapted for aiogram 3
import asyncio
import functools
import html as _html
import inspect
import io
import json
import logging
import os
import re
import secrets
import shlex
import time
import typing
from urllib.parse import urlparse

from aiogram.types import (
    BufferedInputFile,
    Message as AiogramMessage,
)
from aiogram.utils.text_decorations import html_decoration

logger = logging.getLogger(__name__)

ListLike = typing.Union[list, set, tuple]

_HTML_TAGS_RE = re.compile(
    r"(</?a.*?>|</?b>|</?i>|</?u>|</?strong>|</?em>|</?code>|</?strike>|"
    r"</?del>|</?pre.*?>|</?emoji.*?>|</?tg-emoji.*?>)",
    re.UNICODE,
)

# Approximation of Unicode grapheme clusters: emoji codepoints + ZWJ chains
# + variation selectors
_GRAPHEME_RE = re.compile(
    r"(?:[\uD800-\uDBFF][\uDC00-\uDFFF]|.)"
    r"(?:[‍](?:[\uD800-\uDBFF][\uDC00-\uDFFF]|.))*[︎️]*"
)

_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # emoticons, dingbats, pictographs
    "☀-➿"  # misc symbols, dingbats
    "⬀-⯿"  # misc symbols and arrows
    "←-⇿"  # arrows
    "■-◿"  # geometric shapes
    "︀-️"  # variation selectors
    "‍"  # zero width joiner
    "⃣"  # keycap combining mark
    "❣❤✂✅✈✉✊-✍"
    "™ℹ⏏⏩-⏳⤴⤵〰〽㊗㊙"
    "©®"
    "]"
)


def graphemes(text: str, /) -> typing.List[str]:
    """
    Split text into approximate grapheme clusters
    :param text: Text to split
    :return: List of graphemes
    """
    return _GRAPHEME_RE.findall(text)


def is_emoji(grapheme: str, /) -> bool:
    """
    Check if grapheme contains an emoji
    :param grapheme: Grapheme to check
    :return: True if grapheme is an emoji
    """
    return bool(_EMOJI_RE.search(grapheme))


def get_bot(message: typing.Optional[AiogramMessage]) -> typing.Optional[typing.Any]:
    """
    Resolve the aiogram Bot bound to the message.
    Falls back to the framework singleton, because the contextvar
    does not always propagate into detached tasks.
    :param message: Message to resolve the bot from
    :return: Bot instance or None
    """
    bot = getattr(message, "bot", None)

    if bot is None:
        from . import main

        bot = getattr(main.mokasi, "bot", None)

    return bot


def get_args(message: typing.Union[AiogramMessage, str]) -> typing.Union[list, bool]:
    """
    Get arguments from message
    :param message: Message or string to get arguments from
    :return: List of arguments
    """
    if isinstance(message, str):
        text = message
    else:
        text = message.text or message.caption or ""
        if not text:
            return False

    if len(text := text.split(maxsplit=1)) <= 1:
        return []

    text = text[1]

    try:
        split = shlex.split(text)
    except ValueError:
        return text  # Cannot split, let's assume that it's just one long message

    return list(filter(lambda x: len(x) > 0, split))


def get_args_raw(message: typing.Union[AiogramMessage, str]) -> str:
    """
    Get the parameters to the command as a raw string (not split)
    :param message: Message or string to get arguments from
    :return: Raw string of arguments
    """
    if isinstance(message, str):
        text = message
    else:
        text = message.text or message.caption or ""
        if not text:
            return ""

    return args[1] if len(args := text.split(maxsplit=1)) > 1 else ""


def get_args_html(message: AiogramMessage) -> str:
    """
    Get the parameters to the command as string with HTML (not split)
    :param message: Message to get arguments from
    :return: String with HTML arguments
    """
    raw = message.text or message.caption or ""

    if not raw:
        return ""

    bot = get_bot(message)

    if bot is None or getattr(bot, "mokasi_loader", None) is None:
        return raw

    prefix = bot.mokasi_loader.get_prefix()

    if prefix not in raw:
        return raw

    try:
        start = raw.index(" ", raw.index(prefix) + 1) + 1
    except ValueError:
        return ""

    args_text = raw[start:]

    if not message.entities:
        return args_text

    entities = []
    for entity in message.entities:
        if entity.type == "bot_command" and entity.offset < start:
            continue

        if entity.offset + entity.length <= start:
            continue

        new_offset = max(entity.offset - start, 0)
        new_length = min(
            entity.length - (start - entity.offset),
            len(args_text) - new_offset,
        )

        if new_length > 0:
            entities.append(
                entity.model_copy(
                    update={"offset": new_offset, "length": new_length},
                ),
            )

    if not entities:
        return args_text

    return html_decoration.unparse(args_text, entities)


def get_args_split_by(
    message: typing.Union[AiogramMessage, str],
    separator: str,
) -> typing.List[str]:
    """
    Split args with a specific separator
    :param message: Message or string to get arguments from
    :param separator: Separator to split by
    :return: List of arguments
    """
    return [
        section.strip() for section in get_args_raw(message).split(separator) if section
    ]


def get_chat_id(message: typing.Union[AiogramMessage, int]) -> int:
    """
    Get the chat ID, but without -100 if it's a channel
    :param message: Message to get chat ID from
    :return: Chat ID
    """
    if isinstance(message, int):
        return message

    chat_id = getattr(message, "chat_id", None) or getattr(
        getattr(message, "chat", None),
        "id",
        None,
    )

    if isinstance(chat_id, int) and str(chat_id).startswith("-100"):
        return int(str(chat_id)[4:])

    return chat_id


def escape_html(text: str, /) -> str:
    """
    Pass all untrusted/potentially corrupt input here
    :param text: Text to escape
    :return: Escaped text
    """
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_quotes(text: str, /) -> str:
    """
    Escape quotes to html quotes
    :param text: Text to escape
    :return: Escaped text
    """
    return escape_html(text).replace('"', "&quot;")


def get_base_dir() -> str:
    """
    Get directory of this file
    :return: Directory of this file
    """
    return get_dir(__file__)


def get_dir(mod: str) -> str:
    """
    Get directory of given module
    :param mod: Module's `__file__` to get directory of
    :return: Directory of given module
    """
    return os.path.abspath(os.path.dirname(os.path.abspath(mod)))


async def get_target(message: AiogramMessage, arg_no: int = 0) -> typing.Optional[int]:
    """
    Get target from message:
    replied user or argument (id or @username)
    :param message: Message to get target from
    :param arg_no: Argument number to check
    :return: Target user id or None
    """
    args = get_args(message)

    if message.reply_to_message and not args:
        return getattr(message.reply_to_message.from_user, "id", None)

    if not args or len(args) <= arg_no:
        return None

    arg = args[arg_no]

    if arg.isdigit():
        return int(arg)

    # Try to resolve @username
    try:
        user = await get_bot(message).get_chat(arg)
        if getattr(user, "type", None) == "private":
            return user.id
    except Exception:
        return None

    return None


def run_sync(func, *args, **kwargs):
    """
    Run a non-async function in a new thread and return an awaitable
    :param func: Sync-only function to execute
    :return: Awaitable coroutine
    """
    return asyncio.get_running_loop().run_in_executor(
        None,
        functools.partial(func, *args, **kwargs),
    )


def run_async(loop: asyncio.AbstractEventLoop, coro: typing.Awaitable) -> typing.Any:
    """
    Run an async function as a non-async function, blocking till it's done
    :param loop: Event loop to run the coroutine in
    :param coro: Coroutine to run
    :return: Result of the coroutine
    """
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def censor(
    obj: typing.Any,
    to_censor: typing.Optional[typing.Iterable[str]] = None,
    replace_with: str = "redacted_{count}",
) -> typing.Any:
    """
    Recursively censors the given strings in an object
    :param obj: Object to censor
    :param to_censor: Strings to censor
    :param replace_with: Replacement string
    :return: Censored object
    """
    if to_censor is None:
        to_censor = []

    if isinstance(obj, str):
        for i, item in enumerate(to_censor):
            if item:
                obj = obj.replace(item, replace_with.format(count=i))
        return obj

    if isinstance(obj, dict):
        return {key: censor(value, to_censor, replace_with) for key, value in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [censor(item, to_censor, replace_with) for item in obj]

    return obj


async def answer(
    message: typing.Union[AiogramMessage, "InlineCall", "InlineMessage"],  # type: ignore  # noqa: F821
    response: str,
    *,
    reply_markup: typing.Optional[typing.Any] = None,
    **kwargs,
) -> typing.Any:
    """
    Use this to give the response to a command
    :param message: Message to answer to. Can be an aiogram message or
                    a mokasi inline object
    :param response: Response to send
    :param reply_markup: Reply markup to send. If specified, inline form
                         will be used
    :return: Message or inline object

    :example:
        >>> await utils.answer(message, "Hello world!")
        >>> await utils.answer(
            message,
            "Hello world!",
            reply_markup=[{"text": "Hello!", "data": "world"}],
            silent=True,
            disable_security=True,
        )
    """
    from .inline.types import InlineCall, InlineMessage

    if isinstance(message, list) and message:
        message = message[0]

    if reply_markup is not None:
        if not isinstance(reply_markup, (list, dict)):
            raise ValueError("reply_markup must be a list or dict")

        if reply_markup:
            kwargs.pop("message", None)
            if isinstance(message, (InlineMessage, InlineCall)):
                await message.edit(response, reply_markup, **kwargs)
                return

            return await get_bot(message).mokasi_loader.inline.form(
                response,
                message=message,
                reply_markup=reply_markup,
                **kwargs,
            )

    if isinstance(message, (InlineMessage, InlineCall)):
        await message.edit(response)
        return message

    bot = get_bot(message)
    kwargs.setdefault("disable_web_page_preview", True)
    parse_mode = kwargs.pop("parse_mode", None)

    edit = (
        message.from_user is not None
        and bot is not None
        and message.from_user.id == bot.id
        and not message.via_bot
        and not message.forward_origin
    )

    reply_kwargs = {}
    if not edit:
        if message.reply_to_message:
            reply_kwargs["reply_to_message_id"] = message.reply_to_message.message_id

        if getattr(message, "is_topic_message", False):
            reply_kwargs["message_thread_id"] = message.message_thread_id

        if "reply_to" in kwargs:
            reply_kwargs["reply_to_message_id"] = kwargs.pop("reply_to")

    if isinstance(response, str) and not kwargs.pop("asfile", False):
        if len(response) >= 4096:
            try:
                strings = list(smart_split(response, 4096))

                if len(strings) > 10:
                    raise ValueError("Too many chunks")

                list_ = await bot.mokasi_loader.inline.list(
                    message=message,
                    strings=strings,
                )

                if not list_:
                    raise ValueError("List not created")

                return list_
            except Exception:
                file = BufferedInputFile(
                    response.encode("utf-8"),
                    "command_result.txt",
                )

                result = await bot.send_document(
                    get_chat_id(message),
                    file,
                    caption="Command result is too long, file attached instead",
                    **reply_kwargs,
                )

                if edit:
                    await message.delete()

                return result

        if edit:
            return await message.edit_text(response, **kwargs)

        return await message.answer(
            response,
            **reply_kwargs,
            **kwargs,
        )

    if isinstance(response, AiogramMessage):
        # Send the text of the referenced message
        text = response.text or response.caption or ""
        if edit:
            return await message.edit_text(text, **kwargs)

        return await message.answer(text, **reply_kwargs, **kwargs)

    if isinstance(response, bytes):
        response = io.BytesIO(response)
    elif isinstance(response, str):
        response = io.BytesIO(response.encode("utf-8"))

    if name := kwargs.pop("filename", None):
        response.name = name

    if edit:
        return await message.answer_document(response, **kwargs)

    return await message.answer_document(response, **reply_kwargs, **kwargs)


def chunks(_list: ListLike, n: int, /) -> typing.List[list]:
    """
    Split list into chunks of size n
    :param _list: List to split
    :param n: Size of each chunk
    :return: List of chunks
    """
    return [_list[i : i + n] for i in range(0, len(_list), n)]


def array_sum(
    array: typing.List[typing.List[typing.Any]], /
) -> typing.List[typing.Any]:
    """
    Performs basic sum operation on array
    :param array: Array to sum
    :return: Sum of array
    """
    result = []
    for item in array:
        result += item

    return result


_ALPHABET = "abcdefghijklmnopqrstuvwxyz1234567890"


def rand(size: int, /) -> str:
    """
    Return cryptographically random string of len `size`
    :param size: Length of string
    :return: Random string
    """
    return "".join(secrets.choice(_ALPHABET) for _ in range(size))


def smart_split(
    text: str,
    length: int = 4096,
    split_on: ListLike = ("\n", " "),
    min_length: int = 1,
) -> typing.Iterator[str]:
    """
    Split the message into smaller messages.
    The end of each message except the last one is stripped of characters
    from [split_on]
    :param text: the plain text input
    :param length: the maximum length of a single message
    :param split_on: characters (or strings) which are preferred for
                     a message break
    :param min_length: ignore any matches on [split_on] strings before this
                       number of characters into each message
    :return: iterator, which returns strings
    """
    text_length = len(text)
    text_offset = 0

    while text_offset < text_length:
        if text_offset + length >= text_length:
            yield text[text_offset:]
            break

        search_index = -1
        for search in split_on:
            search_index = text.rfind(
                search,
                text_offset + min_length,
                text_offset + length,
            )
            if search_index != -1:
                break

        if search_index == -1:
            split_index = text_offset + length
        else:
            split_index = search_index

        # Never break a surrogate pair (e.g. emoji)
        while (
            split_index < text_length
            and 0xDC00 <= ord(text[split_index]) <= 0xDFFF
        ):
            split_index -= 1

        exclude = 0
        while split_index + exclude < text_length and text[split_index + exclude] in split_on:
            exclude += 1

        yield text[text_offset:split_index].rstrip("".join(split_on))
        text_offset = split_index + exclude


def check_url(url: str) -> bool:
    """
    Statically checks url for validity
    :param url: URL to check
    :return: True if valid, False otherwise
    """
    try:
        return bool(urlparse(url).netloc)
    except Exception:
        return False


def is_serializable(x: typing.Any, /) -> bool:
    """
    Checks if object is JSON-serializable
    :param x: Object to check
    :return: True if object is JSON-serializable, False otherwise
    """
    try:
        json.dumps(x)
        return True
    except Exception:
        return False


def get_lang_flag(countrycode: str) -> str:
    """
    Gets an emoji of specified countrycode
    :param countrycode: 2-letter countrycode
    :return: Emoji flag
    """
    if (
        len(
            code := [
                c
                for c in countrycode.lower()
                if c in "abcdefghijklmnopqrstuvwxyz0123456789"
            ]
        )
        == 2
    ):
        return "".join([chr(ord(c.upper()) + (ord("🇦") - ord("A"))) for c in code])

    return countrycode


def remove_html(text: str, escape: bool = False) -> str:
    """
    Removes HTML tags from text
    :param text: Text to remove HTML from
    :param escape: Escape HTML
    :return: Text without HTML
    """
    return (escape_html if escape else str)(_HTML_TAGS_RE.sub("", text))


def get_kwargs() -> typing.Dict[str, typing.Any]:
    """
    Get kwargs of function, in which is called
    :return: kwargs
    """
    # https://stackoverflow.com/a/65927265/19170642
    keys, _, _, values = inspect.getargvalues(inspect.currentframe().f_back)
    return {key: values[key] for key in keys if key != "self"}


def mime_type(message: AiogramMessage) -> str:
    """
    Get mime type of document in message
    :param message: Message with document
    :return: Mime type or empty string if not present
    """
    return getattr(getattr(message, "document", None), "mime_type", None) or ""


def find_caller(
    stack: typing.Optional[typing.List[inspect.FrameInfo]] = None,
) -> typing.Any:
    """
    Attempts to find command in stack
    :param stack: Stack to search in
    :return: Command-caller or None
    """
    from .types import Module

    caller = next(
        (
            frame_info
            for frame_info in stack or inspect.stack()
            if hasattr(frame_info, "function")
            and any(
                inspect.isclass(cls_)
                and issubclass(cls_, Module)
                and cls_ is not Module
                for cls_ in frame_info.frame.f_globals.values()
            )
        ),
        None,
    )

    if not caller:
        return next(
            (
                frame_info.frame.f_locals["func"]
                for frame_info in stack or inspect.stack()
                if hasattr(frame_info, "function")
                and frame_info.function == "future_dispatcher"
                and (
                    "CommandDispatcher"
                    in getattr(getattr(frame_info, "frame", None), "f_globals", {})
                )
            ),
            None,
        )

    return next(
        (
            getattr(cls_, caller.function, None)
            for cls_ in caller.frame.f_globals.values()
            if inspect.isclass(cls_) and issubclass(cls_, Module)
        ),
        None,
    )


_ALLOWED_HTML_TAGS = {
    "b",
    "strong",
    "i",
    "em",
    "u",
    "ins",
    "s",
    "strike",
    "del",
    "code",
    "pre",
    "a",
    "tg-spoiler",
    "blockquote",
    "tg-emoji",
}

_HTML_TAG_TOKEN_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9-]*)[^>]*>")


def validate_html(html: str) -> str:
    """
    Removes broken and unknown tags from html, closes unclosed ones
    :param html: HTML to validate
    :return: Valid HTML
    """
    stack = []
    result = []
    pos = 0

    for match in _HTML_TAG_TOKEN_RE.finditer(html):
        result.append(_escape_text_segment(html[pos : match.start()]))
        tag = match.group(0)
        name = match.group(1).lower()

        if name not in _ALLOWED_HTML_TAGS:
            # Drop unknown tag entirely
            pos = match.end()
            continue

        if tag.startswith("</"):
            if stack and stack[-1] == name:
                stack.pop()
                result.append(tag)
        else:
            if name == "a" and "href" not in tag:
                # Links without href break the parser
                pos = match.end()
                continue

            result.append(tag)
            stack.append(name)

        pos = match.end()

    result.append(_escape_text_segment(html[pos:]))

    for name in reversed(stack):
        result.append(f"</{name}>")

    return "".join(result)


def _escape_text_segment(text: str) -> str:
    """Escape a raw text segment, preserving already-escaped entities"""
    return escape_html(_html.unescape(text))


def iter_attrs(obj: typing.Any, /) -> typing.List[typing.Tuple[str, typing.Any]]:
    """
    Returns list of attributes of object
    :param obj: Object to iterate over
    :return: List of attributes and their values
    """
    return ((attr, getattr(obj, attr)) for attr in dir(obj))


def formatted_uptime() -> str:
    """
    Get bot uptime
    :return: Formatted uptime string
    """
    from . import main

    up = round(time.time() - main.mokasi.start_time)
    days = up // 86400
    hours = (up - days * 86400) // 3600
    minutes = (up - days * 86400 - hours * 3600) // 60
    seconds = up - days * 86400 - hours * 3600 - minutes * 60

    return "{}d {}h {}m {}s".format(days, hours, minutes, seconds)


def get_ram_usage() -> float:
    """
    Get RAM usage of current process
    :return: RAM usage in MB
    """
    try:
        import resource

        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:
        return 0.0
