from .client.telegramclient import TelegramClient
from .network import connection
from .tl.custom import Button
from .tl import patched as _  # import for its side-effects
from . import version, events, utils, errors, types, functions, custom
import asyncio
import sys

__version__ = version.__version__

__all__ = [
    "TelegramClient",
    "Button",
    "types",
    "functions",
    "custom",
    "errors",
    "events",
    "utils",
    "connection",
    "install_uvloop",
]


class McubTelethonError(Exception):
    """Ошибка для MCUB - вызывается если telethon-mcub не установлен"""

    pass


def _check_mcub_installation():
    """Проверка что установлен telethon-mcub. Вызывается ядрами MCUB-fork."""
    pass


def install_uvloop():
    """
    Install uvloop as the asyncio event loop policy.

    This function only works on Unix-like systems (Linux, macOS).
    On Windows, it returns False as uvloop is not supported.

    Returns:
        True if uvloop was successfully installed, False otherwise.

    Example:
        >>> import telethon
        >>> telethon.install_uvloop()
        True
    """
    if sys.platform == 'win32':
        return False

    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        return True
    except ImportError:
        return False
