import logging

from aiogram import Router, types, Bot

from bot.database.engine import Repositories
from bot.keyboards.inline import referrals_keyboard
from bot.utils.callback_factory.callback_factory import Partners
from bot.utils.misc import send_section
from bot import messages, referrals

router = Router(name=__name__)
logger = logging.getLogger()


@router.callback_query(Partners.filter())
async def partners_menu(query: types.CallbackQuery, repo: Repositories, bot: Bot) -> None:
    invited_count = await repo.users.count_referrals(query.from_user.id)
    balance = await repo.users.get_stars_balance(query.from_user.id)
    earned = await referrals.total_rewards(query.from_user.id)
    bot_info = await bot.me()
    referral_link = f't.me/{bot_info.username}?start=ref_{query.from_user.id}'

    await send_section(
        query, 'partners',
        messages.REFERRAL_MESSAGE.format(
            referral_link=referral_link,
            invited_count=invited_count,
            balance=f'{balance:.2f}',
            earned=f'{earned:.2f}',
        ),
        reply_markup=referrals_keyboard(),
    )
    await query.answer()
