from aiogram import Router, types
from aiogram.filters import Command

from bot import messages

router = Router(name=__name__)


@router.message(Command(commands=['dev', 'developer', 'info']))
async def dev(msg: types.Message) -> None:
    special_wine = messages.PREMIUM_EMOJI_DICT.get('special_wine', '🍷')
    text = f'{special_wine} Разработчик бота — <b>@velunae</b>'
    no_premium_text = '🍷 Разработчик бота — <b>@velunae</b>'

    try:
        await msg.answer(text, message_effect_id='5159385139981059251')
    except Exception:
        await msg.answer(no_premium_text, message_effect_id='5159385139981059251')
