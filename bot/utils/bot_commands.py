from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat, BotCommandScopeAllPrivateChats

from bot.settings import settings

async def set_commands(bot: Bot):
    await del_commands(bot)

    commands = [
        BotCommand(command="start", description='Главное меню и покупка звёзд ✨'),
        BotCommand(command="help", description="Поддержка и помощь"),
        BotCommand(command="dev", description="О разработчике 🍷"),
    ]

    admin_commands = [
        BotCommand(command="start", description='Главное меню и покупка звёзд ✨'),
        BotCommand(command="help", description="Поддержка и помощь"),
        BotCommand(command="dev", description="О разработчике 🍷"),
    ]

    try:
        await bot.set_my_commands(commands, BotCommandScopeAllPrivateChats())
        for chat_id in settings.admins:
            await bot.set_my_commands(admin_commands, BotCommandScopeChat(chat_id=chat_id))
    except Exception as e:
        print(e)

async def del_commands(bot: Bot):
    try:
        await bot.delete_my_commands(BotCommandScopeDefault())
        await bot.delete_my_commands(BotCommandScopeAllPrivateChats())
        for chat_id in settings.admins:
            await bot.delete_my_commands(BotCommandScopeChat(chat_id=chat_id))
    except Exception as e:
        print(e)
