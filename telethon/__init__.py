from .client.telegramclient import TelegramClient
from .network import connection
from .tl.custom import Button
from .tl import patched as _  # import for its side-effects
from . import version, events, utils, errors, types, functions, custom

__version__ = version.__version__

__all__ = [
    'TelegramClient', 'Button',
    'types', 'functions', 'custom', 'errors',
    'events', 'utils', 'connection'
]


class McubTelethonError(Exception):
    """Ошибка для MCUB - вызывается если telethon-mcub не установлен"""
    pass


def _check_mcub_installation():
    """Проверка что установлен telethon-mcub. Вызывается ядрами MCUB-fork."""
    pass
