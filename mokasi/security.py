# Mokasi — a modular personal Telegram bot framework
# Security model, ported from Hikka (https://github.com/hikariatama/Hikka)
# and adapted for a single bot: bit-flag masks + owner list
"""Checks the commands' security"""

import logging
import typing

from .database import Database
from .types import Command

logger = logging.getLogger(__name__)

OWNER = 1 << 0
SUDO = 1 << 1
SUPPORT = 1 << 2
GROUP_OWNER = 1 << 3
GROUP_ADMIN_ADD_ADMINS = 1 << 4
GROUP_ADMIN_CHANGE_INFO = 1 << 5
GROUP_ADMIN_BAN_USERS = 1 << 6
GROUP_ADMIN_DELETE_MESSAGES = 1 << 7
GROUP_ADMIN_PIN_MESSAGES = 1 << 8
GROUP_ADMIN_INVITE_USERS = 1 << 9
GROUP_ADMIN = 1 << 10
GROUP_MEMBER = 1 << 11
PM = 1 << 12
EVERYONE = 1 << 13

BITMAP = {
    "OWNER": OWNER,
    "EVERYONE": EVERYONE,
}

GROUP_ADMIN_ANY = (
    GROUP_ADMIN_ADD_ADMINS
    | GROUP_ADMIN_CHANGE_INFO
    | GROUP_ADMIN_BAN_USERS
    | GROUP_ADMIN_DELETE_MESSAGES
    | GROUP_ADMIN_PIN_MESSAGES
    | GROUP_ADMIN_INVITE_USERS
    | GROUP_ADMIN
)

DEFAULT_PERMISSIONS = OWNER
PUBLIC_PERMISSIONS = GROUP_OWNER | GROUP_ADMIN_ANY | GROUP_MEMBER | PM

ALL = (1 << 13) - 1


def owner(func: Command) -> Command:
    return _sec(func, OWNER)


def _deprecated(name: str) -> callable:
    def decorator(func: Command) -> Command:
        logger.debug("Using deprecated decorator `%s`, which will have no effect", name)
        return func

    return decorator


sudo = _deprecated("sudo")
support = _deprecated("support")


def unrestricted(func: Command) -> Command:
    return _sec(func, ALL)


def inline_everyone(func: Command) -> Command:
    return _sec(func, EVERYONE)


def _sec(func: Command, flags: int) -> Command:
    prev = getattr(func, "security", 0)
    func.security = prev | OWNER | flags
    return func


class SecurityManager:
    """Manages command execution security policy"""

    def __init__(self, client: "aiogram.Bot", db: Database):  # type: ignore  # noqa: F821
        self._client = client
        self._db = db

        self._default = self.default = db.get(__name__, "default", DEFAULT_PERMISSIONS)
        self._owner = self.owner = db.pointer(__name__, "owner", [])

        self._reload_rights()

    def seed_owner(self, user_id: int) -> bool:
        """Add an owner id from env/config, if not present yet"""
        if user_id and user_id not in self._owner:
            self._owner.append(user_id)
            return True

        return False

    def _reload_rights(self):
        """
        Internal method to ensure that account owner is always in the owner list
        """
        if self._client.id not in self._owner:
            self._owner.append(self._client.id)

    def get_flags(self, func: typing.Union[Command, int]) -> int:
        """
        Gets the security flags for the given function

        :param func: function or flags
        :return: security flags
        """

        if isinstance(func, int):
            config = func
        else:
            # Return masks there so user don't need to reboot
            # every time he changes permissions. It doesn't
            # decrease security at all, bc user anyway can
            # access this attribute
            config = self._db.get(__name__, "masks", {}).get(
                f"{func.__module__}.{func.__name__}",
                getattr(func, "security", self._default),
            )

        if config & ~ALL and not config & EVERYONE:
            logger.error("Security config contains unknown bits")
            return False

        return config & self._db.get(__name__, "bounding_mask", DEFAULT_PERMISSIONS)

    async def check(
        self,
        message: typing.Any = None,
        func: typing.Optional[Command] = None,
        user_id: typing.Optional[int] = None,
        inline_cmd: typing.Optional[str] = None,
    ) -> bool:
        """
        Check if user is permitted to execute certain command

        :param message: aiogram Message (or None for inline interactions)
        :param func: function to check
        :param user_id: user ID (if not resolvable from message)
        :param inline_cmd: inline command name (unused, kept for compat)
        :return: True if permitted, False otherwise
        """
        self._reload_rights()

        config = self.get_flags(func)
        if not config:
            return False

        if user_id is None:
            user_id = getattr(getattr(message, "from_user", None), "id", None)
            if user_id is None:
                return False

        # The bot's own messages are always allowed
        if user_id == self._client.id:
            return True

        # Owners are always allowed
        if user_id in self._owner:
            return True

        # Claim exception: if no owner is configured yet (only the bot itself
        # is in the list), the `start` command is allowed for anyone
        # (one-time owner claim)
        if (
            func is not None
            and not isinstance(func, int)
            and func.__name__ == "startcmd"
            and all(user == self._client.id for user in self._owner)
        ):
            return True

        if user_id in self._db.get("mokasi.main", "blacklist_users", []):
            return False

        # Inline interactions (inline queries, callback queries on messages
        # not bound to any chat) require the EVERYONE bit
        if message is None:
            return bool(config & EVERYONE)

        return False

    def check_inline_security(self, *, func: typing.Optional[Command], user: int) -> bool:
        """
        Check if user is permitted to interact with inline elements
        :param func: function to check
        :param user: user ID
        :return: True if permitted, False otherwise
        """
        return self.check(message=None, func=func, user_id=user)
