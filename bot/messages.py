PREMIUM_EMOJI_DICT = {
    'star': '<tg-emoji emoji-id="5951810621887484519">⭐️</tg-emoji>',
    'rocket': '<tg-emoji emoji-id="5372917041193828849">🚀</tg-emoji>',
    'star_wand': '<tg-emoji emoji-id="5373107480043724304">✨</tg-emoji>',
    'white_star': '<tg-emoji emoji-id="5208968969750330825">⭐️</tg-emoji>',
    'support': '<tg-emoji emoji-id="6032653721853234759">🗣</tg-emoji>',
    'partners': '<tg-emoji emoji-id="6032594876506312598">👥</tg-emoji>',
    'quests': '<tg-emoji emoji-id="5415968693857298117">❔</tg-emoji>',
    'confirm': '<tg-emoji emoji-id="6138879610386912023">✅</tg-emoji>',
    'active_quest': '<tg-emoji emoji-id="5416032847783799335">❗️</tg-emoji>',
    'decline': '<tg-emoji emoji-id="5213460324425935151">❌</tg-emoji>',
    'special_wine': '<tg-emoji emoji-id="5305267075739037458">🍷</tg-emoji>',
    'question': '<tg-emoji emoji-id="5415867457183164214">❔</tg-emoji>'
}

STARS_COURSE_DEFAULT = 0.015

COMMISSION_PERCENT = 2

COMMISSION_PERCENT_FK = 3

ICON_EMOJI_IDS = {
    'back_arrow': '6039539366177541657',
    'support': '6032653721853234759',
    'partners': '6032594876506312598',
    'withdraw_stars': '5773677501825945508',
    'white_star': '5208968969750330825',
    'quests': '5415968693857298117',
    'buy_subscribers': '6032625495328165724',
    'create_quest': '5415599803411211152',
    'top_up_balance': '5769126056262898415',
    'confirm': '6138879610386912023',
    'decline': '5213460324425935151',
    'active_quest': '5416032847783799335',
    'buy_stars': '5890727932011223292',
    'calc': '6021792097454002931',
    'cryptobot': '5397597950501204351',
    'sbp': '5294247005701292072',
    'ton': '5370546279375982437',
    'usdt_ton': '5280846677673010353',
    'lolzteam': '5280957144231846453',
    'xrocket': '5415897719522744378',
    'pay': '5890848474563352982',
    'payment_wallet': '5276398496008663230',
    'iris': '5278611606756942667',
    'cryptocurrency': '5776023601941582822'
}

_PEMOJI = PREMIUM_EMOJI_DICT

IMAGE_PATHS = {
    'welcome': 'media/syndicate_welcome.jpeg',
    'main_menu': 'media/syndicate_main_page.jpeg',
    'partners': 'media/syndicate_main_page.jpeg',
    'withdraw_stars': 'media/syndicate_main_page.jpeg',
    'support': 'media/syndicate_main_page.jpeg',
    'buy_stars': 'media/syndicate_main_page.jpeg',
}

WELCOME_MESSAGE = (
    f'<b>Магазин Telegram {_PEMOJI["star"]} звёзд и Premium</b>\n\n'
    f'{_PEMOJI["rocket"]} <b>Как оформить заказ:</b>\n'
    '• Откройте <b>Купить Звёзды</b> — выберите количество звёзд или срок Telegram Premium и оплатите заказ\n'
    '• После оплаты звёзды или Premium отправляются автоматически; при сбое отправки звёзд они остаются на балансе бота.'
)

REFERRAL_MESSAGE = (
    f'{_PEMOJI["partners"]} <b>Рефералы — 15%</b>\n\n'
    'Приглашайте друзей по вашей ссылке и получайте <b>15% от купленных ими звёзд</b> '
    'на внутренний баланс после подтверждения оплаты. Покупки в подарок тоже учитываются.\n'
    'Для Premium бонус рассчитывается от звёздного эквивалента стоимости подписки '
    'без комиссии по курсу бота на момент оформления счёта.\n'
    'Бонус начисляется с точностью до 0,01 звезды с округлением вниз.\n\n'
    f'{_PEMOJI["partners"]} <b>Ваша ссылка:</b>\n'
    '<code>https://{referral_link}</code>\n\n'
    f'{_PEMOJI["partners"]} Приглашено: <b>{{invited_count}}</b>\n'
    f'{_PEMOJI["star"]} Всего заработано: <b>{{earned}}</b>\n'
    f'{_PEMOJI["white_star"]} Внутренний баланс: <b>{{balance}}</b>\n\n'
    'Вывод — от <b>50 звёзд</b>, целым количеством. Дробный остаток сохраняется.'
)

BOT_INFO = (
    '🤖 Bot information: \n\n'
    '🐍 <b>Python: {python} </b> \n'
    '🗂 <b>Aiogram: {aiogram} </b> \n '
    '📟 <b>CPU: {process_cpu_percent}% </b> \n'
    '📟 <b>RAM: {process_ram} MB ({process_ram_percent}%) </b> \n'
    '🚀 <b>Bot working: <code>{bot_working}</code> </b> \n\n'
    '📊 Server information: \n\n'
    '📟 <b>CPU: {cpu} ядер(-ро) {cpu_load}% </b> \n'
    '📟 <b>RAM: {ram} / {ram_load_mb}MB ({ram_load}%) </b> \n'
    '💻 <b>Arch: {arch} </b> \n'
    '💿 <b>OS: {os} </b> \n\n'
    '👥 <b>All users in db: {users_in_db}</b> \n'
)

SUPPORT_MESSAGE = (
    f'{_PEMOJI["support"]} <b>Поддержка</b>\n\n'
    'Если у вас возникли вопросы по оплате, доставке звёзд или Telegram Premium, напишите в поддержку:\n'
    f'{_PEMOJI["support"]} @maneramur или @velunae\n\n'
    'Для быстрого перехода выберите контакт ниже.'
)


FIRST_WELCOME_MESSAGE = '<tg-emoji emoji-id="5265259240628439723">❤️</tg-emoji> | <b>Добро пожаловать в Syndicate Stars!</b>\nЗдесь вы можете оформить Telegram Stars и Telegram Premium — для себя или в подарок другу.\n\n<tg-emoji emoji-id="5395720246633979940">🌟</tg-emoji> <b>Частые вопросы:</b>\n<blockquote expandable><tg-emoji emoji-id="5951810621887484519">⭐️</tg-emoji> <b>Товары и реферальный бонус</b>\nStars — от 50 штук, Premium — на 3, 6 или 12 месяцев. За заказы друзей вы получаете 15% на внутренний баланс: от купленных звёзд или от звёздного эквивалента цены Premium без комиссии по курсу бота на момент заказа. Вывод — от 50 звёзд в разделе «Рефералы».\n\n<tg-emoji emoji-id="6037175527846975726">🎁</tg-emoji> <b>Подарки и оплата</b>\nПодарки друзьям оформляются только по <b>@username</b> (ID и ссылки не принимаются). Оплата: CryptoBot (комиссия 2%) и СБП (комиссия 3%).\n\n<tg-emoji emoji-id="5415867457183164214">❔</tg-emoji> <b>Если автоотправка Stars не удалась</b>\nЗвёзды сохранятся на вашем внутреннем балансе — напишите в поддержку, и мы поможем.</blockquote>\n\n<tg-emoji emoji-id="6032653721853234759">🗣</tg-emoji> Если возникнут вопросы, пишите в поддержку: <a href="https://t.me/maneramur">@maneramur</a> или <a href="https://t.me/velunae">@velunae</a>.\n\n<i>Нажмите «Продолжить?», чтобы открыть главное меню.</i>'
