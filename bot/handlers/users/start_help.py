import logging

from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from bot.utils.photos import send_photo

from aiogram_dialog import DialogManager

from bot.database.engine import Repositories
from bot.keyboards.inline import start_keyboard, welcome_keyboard
from bot.utils.misc import send_section
from bot.utils.callback_factory.callback_factory import MainMenu
from bot import messages
from bot.database.models import User
from sqlalchemy import select, update

router = Router(name=__name__)
logger = logging.getLogger()


async def send_first_welcome(msg: types.Message, repo: Repositories) -> bool:
    # Confirmation is recorded only by the Continue callback, never by delivery.
    async with repo.session.begin():
        user = await repo.session.scalar(
            select(User).where(User.id == msg.from_user.id).with_for_update().execution_options(populate_existing=True),
        )
        if not user.welcome_accepted:
            await send_photo(
                msg, messages.IMAGE_PATHS['welcome'], caption=messages.FIRST_WELCOME_MESSAGE,
                message_effect_id='5159385139981059251',
                reply_markup=welcome_keyboard(),
            )
            return True
        return False


@router.callback_query(MainMenu.filter(F.action == 'continue'), flags={'user': False, 'chat': False})
async def continue_welcome(query: types.CallbackQuery, repo: Repositories, state: FSMContext,
                           dialog_manager: DialogManager) -> None:
    await repo.session.execute(update(User).where(User.id == query.from_user.id).values(welcome_accepted=True))
    await repo.session.commit()
    await state.clear()
    await dialog_manager.reset_stack()
    await query.message.edit_reply_markup(reply_markup=None)
    await send_photo(
        query.message, messages.IMAGE_PATHS['main_menu'],
        caption=messages.WELCOME_MESSAGE, reply_markup=start_keyboard(),
    )
    await query.answer()


@router.message(CommandStart(), flags={'user': False, 'chat': False})
async def start(msg: types.Message, repo: Repositories, bot: Bot, state: FSMContext,
                dialog_manager: DialogManager) -> None:
    await state.clear()
    await dialog_manager.reset_stack()

    args = msg.text.split(maxsplit=1)

    referrer_id: int | None = None
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            referrer_id = int(args[1][4:])
            if referrer_id == msg.from_user.id:
                referrer_id = None
        except ValueError:
            pass

    await repo.users.get_or_create_user(msg.from_user, referrer_id=referrer_id)
    if await send_first_welcome(msg, repo):
        return

    await send_photo(
        msg, messages.IMAGE_PATHS['main_menu'],
        caption=messages.WELCOME_MESSAGE,
        reply_markup=start_keyboard(),
    )

@router.callback_query(
    MainMenu.filter(F.action == 'return'),
    flags={'user': False, 'chat': False}
)
async def return_menu(
    query: types.CallbackQuery, state: FSMContext,
    dialog_manager: DialogManager) -> None:

    await send_section(query, 'main_menu', messages.WELCOME_MESSAGE, reply_markup=start_keyboard())
    await state.clear()
    await dialog_manager.reset_stack()
    await query.answer()
