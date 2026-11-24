import contextlib
import html
import platform
import subprocess
import sys
import time
from datetime import timedelta
from typing import Any, Callable, Awaitable

import aiogram
import psutil

from aiogram import types
from bot.database import get_repo

time_st = time.perf_counter()


def get_editor(query_or_msg: types.CallbackQuery | types.Message) -> Callable[..., Awaitable]:
    """Returns edit_caption or edit_text wrapped with a uniform (text, **kwargs) signature.
    Silently ignores 'message is not modified' errors."""
    from aiogram.exceptions import TelegramBadRequest

    msg = query_or_msg.message if isinstance(query_or_msg, types.CallbackQuery) else query_or_msg

    if msg.caption is not None:
        async def editor(text: str, **kwargs):
            with contextlib.suppress(TelegramBadRequest):
                return await msg.edit_caption(caption=text, **kwargs)
    else:
        async def editor(text: str, **kwargs):
            with contextlib.suppress(TelegramBadRequest):
                return await msg.edit_text(text=text, **kwargs)

    return editor


async def send_section(
    query: types.CallbackQuery,
    image_key: str,
    text: str,
    reply_markup=None,
) -> types.Message | None:
    """Меняет фото и caption через edit_media, или fallback на edit_caption/edit_text."""
    from bot.utils.photos import send_photo
    from aiogram.exceptions import TelegramBadRequest
    from bot import messages as msgs

    msg = query.message
    path = msgs.IMAGE_PATHS.get(image_key)

    if path and msg.photo:
        # Сообщение с фото — меняем через edit_media
        with contextlib.suppress(TelegramBadRequest):
            return await send_photo(msg, path, text, reply_markup, edit=True)
    elif path and not msg.photo:
        # Текстовое сообщение, но нужно фото — удаляем и отправляем новое
        with contextlib.suppress(TelegramBadRequest):
            await msg.delete()
        return await send_photo(
            msg, path, caption=text, reply_markup=reply_markup,
        )
    elif msg.photo or msg.caption is not None:
        # Фото есть, но путь не указан — просто edit_caption
        with contextlib.suppress(TelegramBadRequest):
            return await msg.edit_caption(caption=text, reply_markup=reply_markup)
    else:
        # Текстовое сообщение — edit_text
        with contextlib.suppress(TelegramBadRequest):
            return await msg.edit_text(text=text, reply_markup=reply_markup)


def bytes_to_megabytes(b: float) -> float:
    return round(b / 1024 / 1024, 1)


def uptime() -> int:
    return round(time.perf_counter() - time_st)


def formatted_uptime() -> str:
    return str(timedelta(seconds=uptime()))


async def bot_info_dict() -> dict[str, Any]:
    inf = {
        'cpu': 'n/a',
        'cpu_load': 'n/a',
        'ram': 'n/a',
        'ram_load_mb': 'n/a',
        'ram_load': 'n/a',
        'arch_emoji': 'n/a',
        'arch': 'n/a',
        'os': 'n/a',
        'python': 'n/a',
        'aiogram': aiogram.__version__,
        'process_ram': 'n/a',
        'process_ram_percent': 'n/a',
        'process_cpu_percent': 'n/a',
        'bot_working': formatted_uptime(),
        'users_in_db': 0,
    }

    with contextlib.suppress(Exception):
        inf['cpu'] = psutil.cpu_count(logical=True)

    with contextlib.suppress(Exception):
        inf['cpu_load'] = psutil.cpu_percent()

    with contextlib.suppress(Exception):
        inf['ram'] = bytes_to_megabytes(psutil.virtual_memory().total - psutil.virtual_memory().available)

    with contextlib.suppress(Exception):
        inf['ram_load_mb'] = bytes_to_megabytes(psutil.virtual_memory().total)

    with contextlib.suppress(Exception):
        inf['ram_load'] = psutil.virtual_memory().percent

    with contextlib.suppress(Exception):
        inf['arch'] = html.escape(platform.architecture()[0])

    inf['arch_emoji'] = (
        '<emoji document_id=5172881503478088537>💻</emoji>'
        if '64' in inf.get('arch', '')
        else '<emoji document_id=5174703196676817427>💻</emoji>'
    )

    with contextlib.suppress(Exception):
        with subprocess.Popen('cat /etc/*release', stdout=subprocess.PIPE, shell=True) as proc:
            if proc.stdout:
                system = proc.stdout.read().decode('utf-8')
                b = system.find('DISTRIB_DESCRIPTION="') + 21
                system = system[b: system.find('"', b)]
                inf['os'] = html.escape(system)

    with contextlib.suppress(Exception):
        inf['python'] = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'

    process = psutil.Process()

    with contextlib.suppress(Exception):
        inf['process_ram'] = bytes_to_megabytes(process.memory_info().rss)

    with contextlib.suppress(Exception):
        inf['process_ram_percent'] = round(process.memory_percent(), 1)

    with contextlib.suppress(Exception):
        inf['process_cpu_percent'] = round(process.cpu_percent(), 1)

    async with get_repo() as repo:
        inf['users_in_db'] = await repo.users.get_all(count=True)

    return inf
