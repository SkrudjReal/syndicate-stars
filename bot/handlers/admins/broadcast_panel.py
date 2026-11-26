import asyncio
from collections import defaultdict
from html import escape
from uuid import uuid4

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func

from bot import broadcasts
from bot.database.engine import sessionmaker
from bot.database.models import User
from bot.filters import IsAdmin
from bot.utils.misc import get_editor

router = Router(name=__name__)
router.message.filter(IsAdmin(), F.chat.type == 'private')
router.callback_query.filter(IsAdmin(), F.message.chat.type == 'private')
locks = defaultdict(asyncio.Lock)


class BroadcastCompose(StatesGroup):
    post = State()
    buttons = State()


def keyboard(*rows):
    kb = InlineKeyboardBuilder()
    for row in rows:
        kb.row(*(types.InlineKeyboardButton(text=text, callback_data=data, style=style)
                 for text, data, style in row))
    return kb.as_markup()


def panel_keyboard():
    return keyboard([('Новая рассылка', 'admin:new', 'primary')],
                    [('Рассылки и статистика', 'admin:jobs', None)],
                    [('В главное меню', 'mm:return', 'danger')])


def compose_keyboard():
    return keyboard([('Готово', 'admin:ready', 'primary')], [('Отмена', 'admin:panel', 'danger')])


def job_keyboard(job):
    rows = []
    if job.can_started:
        rows.append([('Предпросмотр себе', f'admin:preview:{job.id}', None)])
        if not job.context.get('confirmed'):
            rows.append([('URL-кнопки', f'admin:buttons:{job.id}', None)])
        rows.append([('Продолжить' if job.context.get('confirmed') else 'Отправить всем', f'admin:ask:{job.id}', 'primary')])
    if job.can_stopped:
        rows.append([('Остановить', f'admin:stop:{job.id}', 'danger')])
    rows.extend([[('Обновить статистику', f'admin:job:{job.id}', None)], [('К рассылкам', 'admin:jobs', None)]])
    if not job.context.get('confirmed'):
        rows.append([('Удалить черновик', f'admin:delete:{job.id}', 'danger')])
    return keyboard(*rows)


async def panel_text():
    async with sessionmaker() as session:
        total = await session.scalar(select(func.count()).select_from(User).where(User.id > 0))
    return (f'<b>Админ-панель</b>\n\nПользователей: <b>{total}</b>\n\n'
            'Рассылка поддерживает текст с премиум-эмоджи, медиа, альбомы и URL-кнопки. '
            'Перед отправкой доступны предпросмотр и подтверждение.')


@router.message(Command('admin', 'cancel'))
async def admin_command(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(await panel_text(), reply_markup=panel_keyboard())


@router.callback_query(F.data.startswith('admin:'))
async def admin_action(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    parts = query.data.split(':')
    action = parts[1]
    try:
        if action == 'panel':
            await state.clear()
            await get_editor(query)(await panel_text(), reply_markup=panel_keyboard())
            return
        if action == 'new':
            await state.clear()
            await state.set_state(BroadcastCompose.post)
            await state.update_data(messages=[], request=uuid4().hex, panel_chat=query.message.chat.id,
                                    panel_message=query.message.message_id, panel_caption=query.message.caption is not None)
            await get_editor(query)(
                '<b>Новая рассылка</b>\n\nПришлите или перешлите один пост либо альбом до 10 медиа. '
                'Текст, форматирование и премиум-эмоджи сохранятся.\n\n'
                'После загрузки нажмите «Готово». Пока ничего не отправляется получателям.',
                reply_markup=compose_keyboard(),
            )
            return
        if action == 'ready':
            async with locks[query.from_user.id]:
                data = await state.get_data()
                if await state.get_state() != BroadcastCompose.post.state or not data.get('messages'):
                    raise ValueError('Сначала добавьте пост для рассылки.')
                messages = [types.Message.model_validate(m) for m in data['messages']]
                job = await broadcasts.create_job(messages, query.from_user.id)
                await state.clear()
            await get_editor(query)(broadcasts.status_text(job), reply_markup=job_keyboard(job))
            return
        if action == 'jobs':
            await state.clear()
            jobs = [] if broadcasts.service is None else sorted(broadcasts.service, key=lambda j: (j.context.get('created', 0), j.id), reverse=True)[:8]
            rows = [[(f'#{j.id} · {len(j.chats.success)}/{len(j.chats.total)}', f'admin:job:{j.id}', None)] for j in jobs]
            rows.append([('В админ-панель', 'admin:panel', None)])
            await get_editor(query)(
                '<b>Рассылки и статистика</b>\n\n'
                + ('Выберите рассылку. После перезапуска незавершённые рассылки приостановлены.' if jobs else 'Рассылок пока нет.'),
                reply_markup=keyboard(*rows),
            )
            return
        if len(parts) != 3 or not parts[2].isdigit():
            raise ValueError('Неизвестное действие.')
        job = broadcasts.get_job(int(parts[2]))
        if action == 'preview':
            ok, _ = await job.send(query.from_user.id)
            if not ok:
                raise ValueError('Предпросмотр не отправлен. Проверьте содержимое и попробуйте позже.')
        elif action == 'buttons':
            if job.context.get('confirmed'):
                raise ValueError('Кнопки можно менять только в черновике.')
            await state.set_state(BroadcastCompose.buttons)
            await state.update_data(job_id=job.id)
            await get_editor(query)(
                '<b>URL-кнопки</b>\n\nПришлите по одной кнопке на строку:\n'
                '<code>Купить звёзды | https://t.me/syndistars_bot</code>\n\n'
                'Чтобы убрать кнопки, пришлите <code>-</code>.',
                reply_markup=keyboard([('Отмена', f'admin:job:{job.id}', 'danger')]),
            )
            return
        elif action == 'ask':
            if not job.can_started:
                raise ValueError('Рассылка уже запущена или завершена.')
            await get_editor(query)(
                broadcasts.status_text(job) + f'\n\n<b>Отправить пост оставшимся {len(job.chats.pending)} получателям?</b>',
                reply_markup=keyboard([(f'Да, отправить · {len(job.chats.pending)}', f'admin:send:{job.id}', 'primary')],
                                      [('Назад', f'admin:job:{job.id}', None)]),
            )
            return
        elif action == 'send':
            await broadcasts.start_job(job)
        elif action == 'stop':
            if job.can_stopped:
                await job.stop()
        elif action == 'delete':
            if job.context.get('confirmed'):
                raise ValueError('Удалить можно только неотправленный черновик.')
            await job.delete()
            await state.clear()
            await get_editor(query)('Черновик удалён.', reply_markup=panel_keyboard())
            return
        elif action != 'job':
            raise ValueError('Неизвестное действие.')
        await state.clear()
        await get_editor(query)(broadcasts.status_text(job), reply_markup=job_keyboard(job))
    except ValueError as exc:
        await get_editor(query)(escape(str(exc)), reply_markup=panel_keyboard())


@router.message(BroadcastCompose.post)
async def receive_post(message: types.Message, state: FSMContext):
    async with locks[message.from_user.id]:
        data = await state.get_data()
        old = data.get('messages', [])
        if message.media_group_id and old and old[0].get('media_group_id') == message.media_group_id:
            messages = [m for m in old if m['message_id'] != message.message_id] + [message.model_dump(mode='json', exclude_none=True)]
        else:
            messages = [message.model_dump(mode='json', exclude_none=True)]
        try:
            broadcasts.content_from_messages([types.Message.model_validate(m) for m in messages])
        except ValueError as exc:
            await message.answer(escape(str(exc)))
            return
        await state.update_data(messages=messages)
        text = f'<b>Пост получен</b>\n\nСообщений в посте: {len(messages)}.\nНажмите «Готово», чтобы открыть предпросмотр и настройки.\n\nНовый отдельный пост заменит этот черновик.'
        kwargs = dict(chat_id=data['panel_chat'], message_id=data['panel_message'], reply_markup=compose_keyboard())
        if data['panel_caption']:
            await message.bot.edit_message_caption(caption=text, **kwargs)
        else:
            await message.bot.edit_message_text(text=text, **kwargs)


@router.message(BroadcastCompose.buttons)
async def receive_buttons(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        job = broadcasts.get_job(data['job_id'])
        markup = broadcasts.parse_buttons(message.text or '')
        await broadcasts.set_buttons(job, markup)
    except ValueError as exc:
        await message.answer(escape(str(exc)))
        return
    await state.clear()
    await message.answer(broadcasts.status_text(job), reply_markup=job_keyboard(job))
