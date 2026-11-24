import logging

from aiogram import Router, F, types
from aiogram.filters import Command
from bot.utils.photos import send_photo

from bot.utils.callback_factory.callback_factory import Support
from bot.keyboards.inline import support_keyboard
from bot.utils.misc import send_section
from bot import messages

router = Router(name=__name__)
logger = logging.getLogger()


@router.message(Command('help', 'support'))
async def support_command(msg: types.Message) -> None:
    await send_photo(
        msg, messages.IMAGE_PATHS['support'],
        caption=messages.SUPPORT_MESSAGE,
        reply_markup=support_keyboard(),
    )


@router.callback_query(Support.filter(F.action == 'support'))
async def support_handler(query: types.CallbackQuery) -> None:
    await send_section(query, 'support', messages.SUPPORT_MESSAGE, reply_markup=support_keyboard())
    await query.answer()
