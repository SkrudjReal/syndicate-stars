import logging

from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramAPIError

from aiogram_dialog import (
    Dialog,
    Window,
    DialogManager,
    StartMode
)
from aiogram_dialog.widgets.kbd import (
    Row,
    PrevPage,
    FirstPage,
    NextPage,
    LastPage,
    CurrentPage
)
from aiogram_dialog.widgets.text import (
    Const,
    ScrollingText,
    Format
)

from bot.filters import IsAdmin
from bot.messages import BOT_INFO
from bot.utils.misc import bot_info_dict
from bot.database.models.user_models import Stars
from bot.database.engine import Repositories

from bot import funcs

router = Router()
logger = logging.getLogger(__name__)

router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class DialogSG(StatesGroup):
    TEXT = State()

dialog = Dialog(
    Window(
        Const("Просмотр списка:\n"),
        ScrollingText(
            text=Format("{start_data[operations_text]}"),
            id="text_scroll",
            page_size=1000,
        ),
        Row(
            FirstPage(scroll="text_scroll", text=Format("⏮️")),
            PrevPage(scroll="text_scroll", text=Format("◀️")),
            CurrentPage(scroll="text_scroll"),
            NextPage(scroll="text_scroll", text=Format("▶️")),
            LastPage(scroll="text_scroll", text=Format("⏭️"))
        ),
        # MAIN_MENU_BTN,
        state=DialogSG.TEXT,
    ),
)

@router.message(Command("botinfo"))
async def bot_info(message: types.Message) -> None:
    text = BOT_INFO.format(**await bot_info_dict())
    await message.answer(text=text)

@router.message(Command('course'))
async def change_stars_course(msg: types.Message, repo: Repositories) -> None:

    course = msg.text.split()[-1]

    if not funcs.is_number(course):
        await msg.answer('Курс должен быть числом (в долларах). Пример команды: /course 0.015')
        return

    text = f'Курс на звёзды установлен: <b>{course}$ за 1 зв.</b>'

    course = int(float(course)*10000)

    await repo.users.set_stars_course(course)

    await msg.answer(text)

@router.message(Command('top_stars'))
async def top_stars(msg: types.Message, repo: Repositories, dialog_manager: DialogManager) -> None:

    admin_id = msg.from_user.id

    stars = await repo.users.top_user_stars()

    stars_history = funcs.format_top_user_stars(stars)

    # it is important to reset stack because user wants to restart everything
    await dialog_manager.start(
        DialogSG.TEXT,
        mode=StartMode.NEW_STACK,
        data={"operations_text": stars_history}
    )

def extract_id(message: types.Message) -> int:
    """
    Извлекает ID юзера из хэштега в сообщении

    :param message: сообщение, из хэштега в котором нужно достать айди пользователя
    :return: ID пользователя, извлечённый из хэштега в сообщении
    """
    # Получение списка сущностей (entities) из текста или подписи к медиафайлу в отвечаемом сообщении
    entities = message.entities or message.caption_entities
    # Если всё сделано верно, то последняя (или единственная) сущность должна быть хэштегом...
    if not entities or entities[-2].type != "hashtag":
        raise ValueError("Не удалось извлечь ID для ответа!")

    # ... более того, хэштег должен иметь вид #id123456, где 123456 — ID получателя
    hashtag = entities[-2].extract_from(message.text or message.caption)
    if len(hashtag) < 4 or not hashtag[3:].isdigit():  # либо просто #id, либо #idНЕЦИФРЫ
        raise ValueError("Некорректный ID для ответа!")

    return int(hashtag[3:])

@router.message(
    (F.reply_to_message) &
    (F.reply_to_message.text.contains('#id')) &
    (F.text.lower().regexp(r'^ответ\n[\s\S]+')))
async def reply_to_user(message: types.Message, bot: Bot, repo: Repositories):
    """
    Ответ администратора на сообщение юзера (отправленное ботом).
    Используется метод copy_message, поэтому ответить можно чем угодно, хоть опросом.

    :param message: сообщение от админа, являющееся ответом на другое сообщение
    :param l10n: объект локализации
    """
    if not message.reply_to_message.from_user.is_bot:
        return

    # Вырезаем ID
    try:
        user_id = extract_id(message.reply_to_message)
    except ValueError as ex:
        return await message.reply('Не удалось извлечь ID пользователя.')

    adm_us = message.from_user.username

    user_entity = funcs.entity_create(user_id, user_id)
    admin_entity = funcs.entity_create(message.from_user.id, message.from_user.full_name)
    # Пробуем отправить копию сообщения.
    # В теории, это можно оформить через errors_handler, но мне так нагляднее
    try:
        await bot.send_message(
            user_id,
            text=(
                f'Ответ от администратора <b>{admin_entity} {"@"+adm_us if adm_us else ""}</b>{message.text[5:]}'
            ))
        await message.reply(f'Сообщение отправлено пользователю {user_entity}.')
    except TelegramAPIError as ex:
        await message.reply('Не удалось отправить сообщение пользователю.')
        print(ex)


@router.message(Command('withdraw_history'))
async def stars_history(msg: types.Message, repo: Repositories, dialog_manager: DialogManager) -> None:

    if len(msg.text.split()) > 1 and funcs.is_user_mention(msg.text.split()[1]):
        user_id = funcs.link_getter(msg.text.split()[1])
        operations = await repo.users.select_user_withdraw_history(user_id)
    else:
        operations = await repo.users.select_all_withdraw_history()

    operations_text = funcs.format_withdraw_history(operations)

    # it is important to reset stack because user wants to restart everything
    await dialog_manager.start(
        DialogSG.TEXT,
        mode=StartMode.NEW_STACK,
        data={"operations_text": operations_text}
    )
