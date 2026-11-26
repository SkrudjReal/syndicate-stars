"""Integration with loRes228/aiogram_broadcaster (MIT), pinned in uv.lock."""
import asyncio
import logging
import time
from urllib.parse import urlsplit

from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import (Message, InlineKeyboardMarkup, InlineKeyboardButton,
                           InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio)
from aiogram_broadcaster import Broadcaster, Mailer
from aiogram_broadcaster.contents import MessageSendContent, MediaGroupContent
from aiogram_broadcaster.intervals import SimpleInterval
from aiogram_broadcaster.mailer.status import MailerStatus
from aiogram_broadcaster.storages.sqlalchemy import SQLAlchemyStorage
from aiogram_broadcaster.utils.sleep import sleep
from sqlalchemy import select

from bot.database.engine import sessionmaker
from bot.database.models import User

logger = logging.getLogger(__name__)
service = None
tasks = {}
_start_lock = asyncio.Lock()


class RetryingMailer(Mailer):
    async def send(self, chat_id, **kwargs):
        # Retry before the library records the final outcome, so 429 retries do
        # not count as failed deliveries. Never retry an ambiguous network error.
        kwargs.pop('disable_error_handling', None)
        for attempt in range(4):
            try:
                _, result = await super().send(chat_id, disable_error_handling=True, **kwargs)
            except TelegramRetryAfter as error:
                failure = error
                if attempt < 3 and await sleep(self._stop_event, error.retry_after + .2):
                    continue
                break
            except TelegramAPIError as error:
                failure = error
                break
            else:
                await self.broadcaster.event.emit_success_send(chat_id=chat_id, response=result, **self.context)
                return True, result
        await self.broadcaster.event.emit_failed_send(chat_id=chat_id, error=failure, **self.context)
        return False, failure


class PersistentBroadcaster(Broadcaster):
    async def create_mailer(self, **kwargs):
        return await RetryingMailer.create(broadcaster=self, **kwargs)

    async def restore_mailers(self):
        async for mailer_id, record in self.storage.get_records():
            if record.bot_id != self.bots[0].id:
                continue
            await RetryingMailer.create_from_record(broadcaster=self, mailer_id=mailer_id, record=record)


def url_markup(markup):
    if not markup:
        return None
    rows = [[button for button in row if button.url] for row in markup.inline_keyboard]
    rows = [row for row in rows if row]
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def parse_buttons(text):
    if text.strip() in ('-', 'Без кнопок'):
        return None
    rows = []
    for line in text.splitlines():
        label, sep, url = line.partition('|')
        label, url = label.strip(), url.strip()
        parsed = urlsplit(url)
        if not sep or not 1 <= len(label) <= 64 or parsed.scheme not in ('https', 'http', 'tg'):
            raise ValueError('Формат: Текст кнопки | https://example.com')
        if not parsed.netloc or parsed.username or parsed.password or len(url) > 2048:
            raise ValueError('Укажите корректную ссылку без логина и пароля.')
        rows.append([InlineKeyboardButton(text=label, url=url)])
    if not 1 <= len(rows) <= 10:
        raise ValueError('Добавьте от 1 до 10 кнопок, по одной на строку.')
    return InlineKeyboardMarkup(inline_keyboard=rows)


def content_from_messages(messages):
    messages = sorted(messages, key=lambda m: m.message_id)
    if not messages or len(messages) > 10:
        raise ValueError('Нужен один пост или альбом до 10 медиа.')
    allowed = ('text', 'photo', 'video', 'animation', 'document', 'audio', 'voice', 'video_note', 'sticker')
    for message in messages:
        if message.has_protected_content or not any(getattr(message, key) for key in allowed):
            raise ValueError('Поддерживаются текст, фото, видео, GIF, файлы, аудио, голосовые, видеосообщения и стикеры без защиты копирования.')
    if len(messages) == 1:
        message = messages[0].model_copy(update={'reply_markup': url_markup(messages[0].reply_markup)})
        return MessageSendContent(message=message, parse_mode=None, reply_markup=message.reply_markup), message.reply_markup
    if not messages[0].media_group_id or any(m.media_group_id != messages[0].media_group_id for m in messages):
        raise ValueError('Пришлите один пост или один альбом.')
    media = []
    for message in messages:
        kwargs = {'caption': message.caption, 'caption_entities': message.caption_entities, 'parse_mode': None}
        if message.photo:
            item = InputMediaPhoto(media=message.photo[-1].file_id, has_spoiler=message.has_media_spoiler or False,
                                   show_caption_above_media=message.show_caption_above_media or False, **kwargs)
        elif message.video:
            item = InputMediaVideo(media=message.video.file_id, has_spoiler=message.has_media_spoiler or False,
                                   show_caption_above_media=message.show_caption_above_media or False, **kwargs)
        elif message.audio:
            item = InputMediaAudio(media=message.audio.file_id, **kwargs)
        elif message.document:
            item = InputMediaDocument(media=message.document.file_id, **kwargs)
        else:
            raise ValueError('Неподдерживаемый тип альбома.')
        media.append(item)
    return MediaGroupContent(media=media, allow_paid_broadcast=False), None


async def initialize(bot):
    global service
    service = PersistentBroadcaster(bot, storage=SQLAlchemyStorage(sessionmaker, table_name='broadcast_mailers'))

    @service.event.success_send()
    async def attach_album_buttons(mailer, chat_id, response):
        buttons = mailer.context.get('buttons')
        if isinstance(mailer.content, MediaGroupContent) and buttons and response:
            try:
                await mailer.bot.edit_message_reply_markup(chat_id=chat_id, message_id=response[-1].message_id,
                                                          reply_markup=InlineKeyboardMarkup.model_validate(buttons))
            except TelegramAPIError:
                logger.warning('Album buttons could not be attached for mailer %s', mailer.id)

    @service.event.completed()
    async def notify_completed(mailer):
        try:
            await mailer.bot.send_message(mailer.context['admin_id'], '✅ Рассылка завершена.\n\n' + status_text(mailer))
        except TelegramAPIError:
            logger.warning('Could not notify broadcast administrator')

    await service.restore_mailers()
    # Restored jobs stay paused. Starting/resuming always requires confirmation.


async def create_job(messages, admin_id):
    if service is None:
        raise ValueError('Сервис рассылок ещё запускается.')
    content, buttons = content_from_messages(messages)
    async with sessionmaker() as session:
        chats = list(await session.scalars(select(User.id).where(User.id > 0)))
    if not chats:
        raise ValueError('В базе пока нет получателей.')
    return await service.create_mailer(
        chats=chats, content=content, interval=SimpleInterval(interval=max(.1, len(messages) * .05)),
        admin_id=admin_id, created=int(time.time()), confirmed=False, recipient_count=len(chats),
        buttons=buttons.model_dump(mode='json', exclude_none=True) if buttons else None,
    )


def get_job(job_id):
    if service is None or job_id not in service.mailers:
        raise ValueError('Рассылка не найдена.')
    return service.mailers[job_id]


async def set_buttons(job, markup):
    if job.status is not MailerStatus.STOPPED or job.context.get('confirmed'):
        raise ValueError('Кнопки можно менять только в черновике.')
    job.context['buttons'] = markup.model_dump(mode='json', exclude_none=True) if markup else None
    if isinstance(job.content, MessageSendContent):
        job.content.message = job.content.message.model_copy(update={'reply_markup': markup})
        job.content.reply_markup = markup
    async with service.storage.update_record(job.id) as record:
        record.content = job.content
        record.context['buttons'] = job.context['buttons']


async def start_job(job):
    async with _start_lock:
        if job.id in tasks and not tasks[job.id].done():
            raise ValueError('Эта рассылка уже запущена.')
        if any(not task.done() for task in tasks.values()):
            raise ValueError('Дождитесь завершения текущей рассылки или остановите её.')
        if not job.can_started:
            raise ValueError('Эту рассылку нельзя запустить.')
        job.context['confirmed'] = True
        async with service.storage.update_record(job.id) as record:
            record.context['confirmed'] = True
        task = job.start()
        tasks[job.id] = task
        def done(result):
            tasks.pop(job.id, None)
            if not result.cancelled() and result.exception():
                logger.error('Broadcast %s stopped: %s', job.id, type(result.exception()).__name__)
        task.add_done_callback(done)
        await asyncio.sleep(0)


def status_text(job):
    status = {MailerStatus.STARTED: 'В работе', MailerStatus.STOPPED: 'Приостановлена' if job.context.get('confirmed') else 'Черновик',
              MailerStatus.COMPLETED: 'Завершена'}[job.status]
    return (f'<b>Рассылка #{job.id} · {status}</b>\n'
            f'Получателей: {job.context.get("recipient_count", len(job.chats.total))}\nДоставлено: {len(job.chats.success)}\n'
            f'Не доставлено: {len(job.chats.failed)}\nОсталось: {len(job.chats.pending)}')


async def shutdown():
    if service is None:
        return
    for job in list(service):
        if job.can_stopped:
            await job.stop()
    pending = list(tasks.values())
    if pending:
        try:
            await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=15)
        except TimeoutError:
            logger.warning('Broadcast shutdown timed out; jobs remain paused for manual review.')
