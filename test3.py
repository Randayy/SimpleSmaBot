import json
import os
import re
import random
import asyncio
from datetime import datetime, timedelta, timezone

UA_TZ = timezone(timedelta(hours=2))  # Київ UTC+3 (літній час) / UTC+2 (зимовий)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ChatJoinRequestHandler, ContextTypes, filters
)
import pandas as pd
import ta
from openai import AsyncOpenAI
from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

# ─── КОНФІГ ────────────────────────────────────────────────────
TOKEN = "8578407218:AAGE5kM5El_nw0j8O83ErH4VJgMvxbm7rBc"
SSID = '42["auth",{"session":"0dc1s5l5704vapvmm8oh57nmtm","isDemo":1,"uid":125727409,"platform":1,"isFastHistory":true,"isOptimized":true}]'
REF_LINK_BASE = "https://u3.shortink.io/register?utm_campaign=793458&utm_source=affiliate&utm_medium=sr&a=zk5yIcrmNGT0Jb&ac=pocketbrocker&code=BEZ100"
OPENAI_API_KEY = "sk-proj-HWnhX_rfVxbW8j4K8ISZH3YF-Z6PxGzgKIRyv559VmsAzDNlP7kCJisrNOqDO8XJBSswkWpRW0T3BlbkFJq0KjXy_N17hHmLcBwnbnT8zU"
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

JSON_PATH = "registered_accounts.json"
ACTIVATED_PATH = "activated_accounts.json"
DEPOSIT_PATH = "deposited_accounts.json"
STATS_PATH = "stats.json"
BINDINGS_PATH = "id_bindings.json"
USERS_PATH = "all_users.json"
OTC_SETTINGS_PATH = "otc_settings.json"

ADMIN_IDS = [452052752,8337970493,6704855261]
ALLOWED_USERS_PATH = "allowed_users_bezdelnik.json"

ASKING_ID = "asking_id"
BROADCAST_MODE = "broadcast_mode"
ADDING_USER_MODE = "adding_user_mode"
AI_CHAT_MODE = "ai_chat_mode"
WORKING_TIMEFRAMES = [60, 120, 180, 300, 600, 900, 1800, 3600]

ASSET_TYPES = [
    ("💱 Форекс", "forex"),
    ("₿ Крипта", "crypto"),
    ("📈 Акції", "stock"),
    ("🛢 Сировина", "commodity"),
    ("📊 Індекси", "index"),
]

ALL_INDICATORS = [
    ("RSI", "rsi"),
    ("EMA", "ema"),
    ("MACD", "macd"),
    ("Stochastic", "stoch"),
    ("Bollinger", "bb"),
]

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

LANG_SETTINGS_PATH = "lang_settings.json"
DEFAULT_LANG = "uk"
SUPPORTED_LANGS = ("uk", "ru")


# ─── ПЕРЕКЛАДИ (i18n) ──────────────────────────────────────────
TR = {
    # ── Таймфрейми ──
    "tf_sec": {"uk": "сек", "ru": "сек"},
    "tf_min": {"uk": "хв", "ru": "мин"},
    "tf_hour": {"uk": "год", "ru": "час"},

    # ── Типи активів ──
    "atype_forex":     {"uk": "💱 Форекс", "ru": "💱 Форекс"},
    "atype_crypto":    {"uk": "₿ Крипта", "ru": "₿ Крипта"},
    "atype_stock":     {"uk": "📈 Акції", "ru": "📈 Акции"},
    "atype_commodity": {"uk": "🛢 Сировина", "ru": "🛢 Сырьё"},
    "atype_index":     {"uk": "📊 Індекси", "ru": "📊 Индексы"},

    # ── Загальні кнопки ──
    "btn_back":        {"uk": "⬅️ Назад", "ru": "⬅️ Назад"},
    "btn_main_menu":   {"uk": "⬅️ Головне меню", "ru": "⬅️ Главное меню"},
    "btn_help":        {"uk": "💬 ДОПОМОГА", "ru": "💬 ПОМОЩЬ"},
    "btn_random_pair": {"uk": "🎲 Випадкова пара", "ru": "🎲 Случайная пара"},
    "btn_get_signal":  {"uk": "🚀 Отримати сигнал", "ru": "🚀 Получить сигнал"},
    "btn_cancel":      {"uk": "❌ Скасувати", "ru": "❌ Отменить"},
    "btn_admin_back":  {"uk": "⬅️ Адмін панель", "ru": "⬅️ Админ панель"},

    # ── Головне меню ──
    "menu_title":         {"uk": "🏠 *BEZDELNIK BOT* — Головне меню:", "ru": "🏠 *BEZDELNIK BOT* — Главное меню:"},
    "menu_activated":     {"uk": "✅ Бот активований\n\n*BEZDELNIK BOT* — Головне меню:", "ru": "✅ Бот активирован\n\n*BEZDELNIK BOT* — Главное меню:"},
    "menu_activated_now": {"uk": "🎉 Бот активовано!\n\n*BEZDELNIK BOT* — Головне меню:", "ru": "🎉 Бот активирован!\n\n*BEZDELNIK BOT* — Главное меню:"},
    "otc_on":   {"uk": "OTC ✅ АКТИВОВАНО", "ru": "OTC ✅ АКТИВИРОВАНО"},
    "otc_off":  {"uk": "OTC ❌ НЕ АКТИВОВАНО", "ru": "OTC ❌ НЕ АКТИВИРОВАНО"},
    "btn_on_request":   {"uk": "📲 НА ЗАПИТ", "ru": "📲 ПО ЗАПРОСУ"},
    "btn_auto_ai":      {"uk": "⚡ АВТО ШІ", "ru": "⚡ АВТО ИИ"},
    "btn_indicators":   {"uk": "📊 ІНДИКАТОРИ", "ru": "📊 ИНДИКАТОРЫ"},
    "btn_bezdelnik_ai": {"uk": "🧠 BEZDELNIK AI", "ru": "🧠 BEZDELNIK AI"},
    "btn_my_signals":   {"uk": "📋 МОЇ СИГНАЛИ", "ru": "📋 МОИ СИГНАЛЫ"},
    "btn_admin_panel":  {"uk": "⚙️ АДМІН ПАНЕЛЬ", "ru": "⚙️ АДМИН ПАНЕЛЬ"},
    "btn_lang_uk": {"uk": "🇺🇦 Українська", "ru": "🇺🇦 Українська"},
    "btn_lang_ru": {"uk": "🇷🇺 Русский", "ru": "🇷🇺 Русский"},

    # ── Блок сигналу ──
    "sig_title":      {"uk": "📊 *СИГНАЛ BEZDELNIK*", "ru": "📊 *СИГНАЛ BEZDELNIK*"},
    "sig_type":       {"uk": "🏷 Тип:", "ru": "🏷 Тип:"},
    "sig_direction":  {"uk": "📈 Напрямок:", "ru": "📈 Направление:"},
    "sig_expiration": {"uk": "⏱ Час експірації:", "ru": "⏱ Время экспирации:"},
    "sig_confidence": {"uk": "💯 Впевненість:", "ru": "💯 Уверенность:"},
    "sig_payout":     {"uk": "💰 Виплата:", "ru": "💰 Выплата:"},
    "sig_method":     {"uk": "🤖 Метод:", "ru": "🤖 Метод:"},
    "sig_entry":      {"uk": "💲 Ціна входу:", "ru": "💲 Цена входа:"},

    # ── Результат угоди ──
    "res_profit": {"uk": "ПРОФІТ", "ru": "ПРОФИТ"},
    "res_loss":   {"uk": "ЗБИТОК", "ru": "УБЫТОК"},
    "res_exit":   {"uk": "💲 Ціна виходу:", "ru": "💲 Цена выхода:"},
    "res_diff":   {"uk": "📊 Різниця:", "ru": "📊 Разница:"},

    # ── Значення індикаторів ──
    "val_ema_bull":  {"uk": "Бичача ↑", "ru": "Бычья ↑"},
    "val_ema_bear":  {"uk": "Медвежа ↓", "ru": "Медвежья ↓"},
    "val_macd_bull": {"uk": "Бичачий ↑", "ru": "Бычий ↑"},
    "val_macd_bear": {"uk": "Медвежий ↓", "ru": "Медвежий ↓"},
    "val_bb_low":    {"uk": "Нижня межа 📉", "ru": "Нижняя граница 📉"},
    "val_bb_high":   {"uk": "Верхня межа 📈", "ru": "Верхняя граница 📈"},
    "val_bb_mid":    {"uk": "Середина ➡️", "ru": "Середина ➡️"},

    "data_error": {"uk": "Помилка отримання даних для {name}", "ru": "Ошибка получения данных для {name}"},

    # ── Стартові / навігаційні тексти ──
    "signal_cooldown": {
        "uk": "⏳ <b>Ви зможете отримати новий сигнал через {m}хв {s}секунд</b>",
        "ru": "⏳ <b>Вы сможете получить новый сигнал через {m}мин {s}секунд</b>",
    },
    "choose_asset_type": {"uk": "📂 Оберіть тип активу:", "ru": "📂 Выберите тип актива:"},
    "no_assets":         {"uk": "❌ Немає доступних активів. Спробуйте пізніше.", "ru": "❌ Нет доступных активов. Попробуйте позже."},
    "no_assets_type":    {"uk": "❌ Наразі немає доступних активів цього типу.", "ru": "❌ Сейчас нет доступных активов этого типа."},
    "generating":        {"uk": "⏳ Генерую сигнал...", "ru": "⏳ Генерирую сигнал..."},
    "choose_pair":       {"uk": "💱 Оберіть пару:", "ru": "💱 Выберите пару:"},
    "choose_timeframe":  {"uk": "⏱ *{name}* (`{payout}%`)\n\nОберіть таймфрейм:", "ru": "⏱ *{name}* (`{payout}%`)\n\nВыберите таймфрейм:"},
    "pair_not_found":    {"uk": "❌ Пару не знайдено", "ru": "❌ Пара не найдена"},
    "choose_indicators": {
        "uk": "📊 *{name}* — `{tf}`\n\nОберіть індикатори (або одразу «Отримати сигнал» для всіх):",
        "ru": "📊 *{name}* — `{tf}`\n\nВыберите индикаторы (или сразу «Получить сигнал» для всех):",
    },
    "ai_analyzing":  {"uk": "🧠 BEZDELNIK AI аналізує *{name}*...", "ru": "🧠 BEZDELNIK AI анализирует *{name}*..."},
    "analyzing_pair": {"uk": "⏳ Аналізую *{name}*...", "ru": "⏳ Анализирую *{name}*..."},

    "my_stats": {
        "uk": (
            "💪 *Моя статистика:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 Кількість угод: `{total}`\n"
            "✅ Профітних: `{profit}`\n"
            "❌ Збиткових: `{loss}`\n"
            "↔️ Нічия: `{draw}`\n\n"
            "🕒 Днів у боті: `{days}`\n\n"
            "*Рейтинг активності:*\n"
            "📊 Ви активніші, ніж `{percentile}%` учасників!"
        ),
        "ru": (
            "💪 *Моя статистика:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 Количество сделок: `{total}`\n"
            "✅ Прибыльных: `{profit}`\n"
            "❌ Убыточных: `{loss}`\n"
            "↔️ Ничья: `{draw}`\n\n"
            "🕒 Дней в боте: `{days}`\n\n"
            "*Рейтинг активности:*\n"
            "📊 Вы активнее, чем `{percentile}%` участников!"
        ),
    },

    # ── Стартові кнопки ──
    "btn_get_bot":        {"uk": "🤖 ОТРИМАТИ РОБОТА", "ru": "🤖 ПОЛУЧИТЬ РОБОТА"},
    "btn_reviews":        {"uk": "⭐ ВІДГУКИ", "ru": "⭐ ОТЗЫВЫ"},
    "btn_channel":        {"uk": "📢 КАНАЛ", "ru": "📢 КАНАЛ"},
    "btn_registration":   {"uk": "🔘 РЕЄСТРАЦІЯ", "ru": "🔘 РЕГИСТРАЦИЯ"},
    "btn_check_id":       {"uk": "🔘 ПЕРЕВІРИТИ ID", "ru": "🔘 ПРОВЕРИТЬ ID"},
    "btn_write":          {"uk": "✉️ Написати", "ru": "✉️ Написать"},
    "btn_activate_bot":   {"uk": "🔘 АКТИВУВАТИ БОТА", "ru": "🔘 АКТИВИРОВАТЬ БОТА"},
    "btn_check_deposit":  {"uk": "🔘 ПЕРЕВІРИТИ ДЕПОЗИТ", "ru": "🔘 ПРОВЕРИТЬ ДЕПОЗИТ"},
    "btn_activate_robot": {"uk": "АКТИВУВАТИ РОБОТА 🤖", "ru": "АКТИВИРОВАТЬ РОБОТА 🤖"},
    "btn_vip_channel":    {"uk": "VIP КАНАЛ 🥳", "ru": "VIP КАНАЛ 🥳"},
    "btn_training":       {"uk": "НАВЧАННЯ", "ru": "ОБУЧЕНИЕ"},
    "btn_broadcast":      {"uk": "📢 РОЗСИЛКА", "ru": "📢 РАССЫЛКА"},
    "btn_add_user":       {"uk": "➕ ДОДАТИ ЮЗЕРА", "ru": "➕ ДОБАВИТЬ ЮЗЕРА"},

    # ── Великі тексти ──
    "welcome_full": {
        "uk": (
            "🚀 <b>BEZDELNIK</b> — твій особистий торговий помічник у 2025!\n"
            "Зібрано командою практиків із реальним досвідом у трейдингу.\n"
            "Працює замість тебе — поки ти живеш своє життя. 24/7/365.\n\n"
            "💡 <b>Що таке BEZDELNIK?</b>\n"
            "Це автоматизований торговий бот із вбудованим аналізом ринку, розумними алгоритмами та простим налаштуванням.\n"
            "<i>Запустив — і забув. Бот сам веде торгівлю.</i>\n"
            "Поки інші думають — ти вже заробляєш.\n\n"
            "🔥 <b>Що входить у BEZDELNIK BOT?</b>\n\n"
            "✅ Гнучкі стратегії — обираєш підхід, бот адаптується під твій стиль\n"
            "✅ Перевірені торгові пари — лише ліквідні та стабільні активи\n"
            "✅ Сигнали цілодобово — прибутковість до 90% навіть у нічні години\n"
            "✅ Розумні точки входу — алгоритм сам визначає найкращий момент\n"
            "✅ Зв'язка з TradingView — повноцінний аналіз + графіки до кожного сигналу\n"
            "✅ Вибір таймфрейму — від 5 секунд до 4 годин на твій розсуд\n"
            "✅ Усі класи активів — Форекс, Криптовалюта, Акції, Індекси, Сировина\n"
            "✅ Живий трекінг результатів — статистика по кожному сигналу за добу та тиждень\n\n"
            "💬 <b>BEZDELNIK</b> — коли ринок працює на тебе, а не ти на ринок.\n"
            "Дій впевнено. Торгуй розумно. Заробляй системно.\n\n"
            "Крім самого бота, ти також отримуєш доступ до всього закритого контенту від BEZDELNIK!"
        ),
        "ru": (
            "🚀 <b>BEZDELNIK</b> — твой личный торговый помощник в 2025!\n"
            "Собран командой практиков с реальным опытом в трейдинге.\n"
            "Работает вместо тебя — пока ты живёшь свою жизнь. 24/7/365.\n\n"
            "💡 <b>Что такое BEZDELNIK?</b>\n"
            "Это автоматизированный торговый бот со встроенным анализом рынка, умными алгоритмами и простой настройкой.\n"
            "<i>Запустил — и забыл. Бот сам ведёт торговлю.</i>\n"
            "Пока другие думают — ты уже зарабатываешь.\n\n"
            "🔥 <b>Что входит в BEZDELNIK BOT?</b>\n\n"
            "✅ Гибкие стратегии — выбираешь подход, бот адаптируется под твой стиль\n"
            "✅ Проверенные торговые пары — только ликвидные и стабильные активы\n"
            "✅ Сигналы круглосуточно — доходность до 90% даже в ночные часы\n"
            "✅ Умные точки входа — алгоритм сам определяет лучший момент\n"
            "✅ Связка с TradingView — полноценный анализ + графики к каждому сигналу\n"
            "✅ Выбор таймфрейма — от 5 секунд до 4 часов на твоё усмотрение\n"
            "✅ Все классы активов — Форекс, Криптовалюта, Акции, Индексы, Сырьё\n"
            "✅ Живой трекинг результатов — статистика по каждому сигналу за сутки и неделю\n\n"
            "💬 <b>BEZDELNIK</b> — когда рынок работает на тебя, а не ты на рынок.\n"
            "Действуй уверенно. Торгуй разумно. Зарабатывай системно.\n\n"
            "Кроме самого бота, ты также получаешь доступ ко всему закрытому контенту от BEZDELNIK!"
        ),
    },
    "welcome_short": {
        "uk": (
            "🚀 <b>BEZDELNIK</b> — твій особистий торговий помічник у 2025!\n"
            "Зібрано командою практиків із реальним досвідом у трейдингу.\n"
            "Працює замість тебе — поки ти живеш своє життя. 24/7/365.\n\n"
            "💡 <b>Що таке BEZDELNIK?</b>\n"
            "Це автоматизований торговий бот із вбудованим аналізом ринку, розумними алгоритмами та простим налаштуванням.\n"
            "<i>Запустив — і забув. Бот сам веде торгівлю.</i>\n"
            "Поки інші думають — ти вже заробляєш.\n\n"
            "🔥 <b>Що входить у BEZDELNIK BOT?</b>\n\n"
            "✅ Гнучкі стратегії\n"
            "✅ Перевірені торгові пари\n"
            "✅ Сигнали цілодобово\n"
            "✅ Розумні точки входу\n"
            "✅ Зв'язка з TradingView\n"
            "✅ Вибір таймфрейму\n"
            "✅ Усі класи активів\n"
            "✅ Живий трекінг результатів\n\n"
            "💬 <b>BEZDELNIK</b> — коли ринок працює на тебе, а не ти на ринок."
        ),
        "ru": (
            "🚀 <b>BEZDELNIK</b> — твой личный торговый помощник в 2025!\n"
            "Собран командой практиков с реальным опытом в трейдинге.\n"
            "Работает вместо тебя — пока ты живёшь свою жизнь. 24/7/365.\n\n"
            "💡 <b>Что такое BEZDELNIK?</b>\n"
            "Это автоматизированный торговый бот со встроенным анализом рынка, умными алгоритмами и простой настройкой.\n"
            "<i>Запустил — и забыл. Бот сам ведёт торговлю.</i>\n"
            "Пока другие думают — ты уже зарабатываешь.\n\n"
            "🔥 <b>Что входит в BEZDELNIK BOT?</b>\n\n"
            "✅ Гибкие стратегии\n"
            "✅ Проверенные торговые пары\n"
            "✅ Сигналы круглосуточно\n"
            "✅ Умные точки входа\n"
            "✅ Связка с TradingView\n"
            "✅ Выбор таймфрейма\n"
            "✅ Все классы активов\n"
            "✅ Живой трекинг результатов\n\n"
            "💬 <b>BEZDELNIK</b> — когда рынок работает на тебя, а не ты на рынок."
        ),
    },
    "get_bot_text": {
        "uk": (
            "Отже, розберемо по кроках. Для того щоб активувати торгового бота "
            "та отримати доступ до ком'юніті BEZDELNIK, тобі потрібен активний акаунт "
            "на Pocket Option (реєстрація + поповнення рахунку) — обов'язково через "
            "партнерське посилання нижче 👇\n"
            'Pocket Option — <b><a href="https://u3.shortink.io/register?utm_campaign=793458&utm_source=affiliate&utm_medium=sr&a=zk5yIcrmNGT0Jb&ac=pocketbrocker&code=BEZ100">ПОСИЛАННЯ</a></b>\n\n'
            "<b>Крок 1 — Реєстрація</b>\n"
            'Переходь за посиланням вище або натискай кнопку "РЕЄСТРАЦІЯ" 👇\n'
            "Це обов'язкова умова — без реєстрації через наше посилання активація бота буде недоступна.\n\n"
            '<i>P.S. Якщо ти вже знаходишся у нашому VIP-каналі — просто натисни "Перевірити ID" ✅</i>'
        ),
        "ru": (
            "Итак, разберём по шагам. Чтобы активировать торгового бота "
            "и получить доступ к сообществу BEZDELNIK, тебе нужен активный аккаунт "
            "на Pocket Option (регистрация + пополнение счёта) — обязательно через "
            "партнёрскую ссылку ниже 👇\n"
            'Pocket Option — <b><a href="https://u3.shortink.io/register?utm_campaign=793458&utm_source=affiliate&utm_medium=sr&a=zk5yIcrmNGT0Jb&ac=pocketbrocker&code=BEZ100">ССЫЛКА</a></b>\n\n'
            "<b>Шаг 1 — Регистрация</b>\n"
            'Переходи по ссылке выше или нажимай кнопку "РЕГИСТРАЦИЯ" 👇\n'
            "Это обязательное условие — без регистрации через нашу ссылку активация бота будет недоступна.\n\n"
            '<i>P.S. Если ты уже находишься в нашем VIP-канале — просто нажми "Проверить ID" ✅</i>'
        ),
    },
    "help_contact": {
        "uk": "💬 *Потрібна допомога?*\n\nНапиши нам:",
        "ru": "💬 *Нужна помощь?*\n\nНапиши нам:",
    },
    "reviews_text": {
        "uk": "⭐ *Відгуки наших користувачів:*\n\nСкоро тут будуть відгуки!",
        "ru": "⭐ *Отзывы наших пользователей:*\n\nСкоро здесь будут отзывы!",
    },
    "check_id_text": {
        "uk": (
            "Після успішної реєстрації у твоєму профілі Pocket Option "
            "буде відображатись унікальний номер акаунту (ID) ❕\n\n"
            "🆔 *Де знайти ID* — дивись на скріншоті нижче\n\n"
            "⭕ Введи свій номер акаунту — бот автоматично перевірить, "
            "чи реєстрація була проведена коректно\n\n"
            "⚠️ *Важливо!*\n"
            "ID вводиться виключно цифрами — без літер, пробілів та інших символів.\n"
            "Приклад: `85340449` → надіслати ❗️\n\n"
            "Введіть ID у повідомленні нижче 👇"
        ),
        "ru": (
            "После успешной регистрации в твоём профиле Pocket Option "
            "будет отображаться уникальный номер аккаунта (ID) ❕\n\n"
            "🆔 *Где найти ID* — смотри на скриншоте ниже\n\n"
            "⭕ Введи свой номер аккаунта — бот автоматически проверит, "
            "была ли регистрация проведена корректно\n\n"
            "⚠️ *Важно!*\n"
            "ID вводится исключительно цифрами — без букв, пробелов и других символов.\n"
            "Пример: `85340449` → отправить ❗️\n\n"
            "Введите ID в сообщении ниже 👇"
        ),
    },
    "deposit_success": {
        "uk": (
            "🎉 *Вітаємо у BEZDELNIK!*\n"
            "Доступ до торгового бота та VIP-матеріалів — відкрито!\n\n"
            "Тепер ти можеш приєднатись до нашого ком'юніті, де на тебе чекає:\n"
            "🧐 Активна спільнота трейдерів, які діляться реальним досвідом\n"
            "📚 BEZDELNIK AI — персональний асистент із будь-яких питань\n"
            "📊 Торгові сигнали в реальному часі\n"
            "📝 Чат із учасниками клубу\n"
            "🤖 І головне — безкоштовний доступ до торгового робота\n\n"
            "⚠️ *Важливо знати:*\n"
            "У нас 1 торговий робот:\n"
            "1️⃣ Він працює персонально з тобою — активувати його можна через кнопку "
            "\"АКТИВУВАТИ РОБОТА\" ✅\n\n"
            "❌ *Звернути увагу:*\n"
            "Створення нового акаунту або видалення поточного автоматично призводить до:\n"
            "⛔️ Виключення з VIP-доступу\n"
            "⛔️ Блокування всіх пов'язаних акаунтів\n\n"
            "🔓 Дотримуйся правил — і все працюватиме без збоїв 😉\n\n"
            "👇 Подай заявку в команду через кнопку нижче:"
        ),
        "ru": (
            "🎉 *Поздравляем в BEZDELNIK!*\n"
            "Доступ к торговому боту и VIP-материалам — открыт!\n\n"
            "Теперь ты можешь присоединиться к нашему сообществу, где тебя ждёт:\n"
            "🧐 Активное сообщество трейдеров, которые делятся реальным опытом\n"
            "📚 BEZDELNIK AI — персональный ассистент по любым вопросам\n"
            "📊 Торговые сигналы в реальном времени\n"
            "📝 Чат с участниками клуба\n"
            "🤖 И главное — бесплатный доступ к торговому роботу\n\n"
            "⚠️ *Важно знать:*\n"
            "У нас 1 торговый робот:\n"
            "1️⃣ Он работает персонально с тобой — активировать его можно через кнопку "
            "\"АКТИВИРОВАТЬ РОБОТА\" ✅\n\n"
            "❌ *Обрати внимание:*\n"
            "Создание нового аккаунта или удаление текущего автоматически приводит к:\n"
            "⛔️ Исключению из VIP-доступа\n"
            "⛔️ Блокировке всех связанных аккаунтов\n\n"
            "🔓 Соблюдай правила — и всё будет работать без сбоев 😉\n\n"
            "👇 Подай заявку в команду через кнопку ниже:"
        ),
    },
    "deposit_not_found": {"uk": "❌ Депозиту ще не зафіксовано", "ru": "❌ Депозит ещё не зафиксирован"},
    "ai_chat_start": {
        "uk": (
            "💬 *BEZDELNIK AI — AI Трейдер*\n\n"
            "Я твій персональний AI-помічник з трейдингу.\n"
            "Запитуй про:\n"
            "• Ситуацію на ринку 📊\n"
            "• Аналіз активів та валютних пар 💹\n"
            "• Стратегії торгівлі 📈\n"
            "• Індикатори та патерни 🔍\n"
            "• Поради для початківців 🎓\n\n"
            "Просто напиши своє питання 👇"
        ),
        "ru": (
            "💬 *BEZDELNIK AI — AI Трейдер*\n\n"
            "Я твой персональный AI-помощник по трейдингу.\n"
            "Спрашивай про:\n"
            "• Ситуацию на рынке 📊\n"
            "• Анализ активов и валютных пар 💹\n"
            "• Стратегии торговли 📈\n"
            "• Индикаторы и паттерны 🔍\n"
            "• Советы для новичков 🎓\n\n"
            "Просто напиши свой вопрос 👇"
        ),
    },
    "admin_panel": {
        "uk": (
            "⚙️ *АДМІН ПАНЕЛЬ*\n\n"
            "👥 *Натиснули /start:*\n"
            "├ Нових сьогодні: `{new_today}`\n"
            "├ Нових за 7 днів: `{new_week}`\n"
            "├ Нових за 30 днів: `{new_month}`\n"
            "└ Всього: `{total}`\n\n"
            "🔄 *Активні:*\n"
            "├ За 7 днів: `{week}`\n"
            "├ За 30 днів: `{month}`\n\n"
            "📊 *Воронка:*\n"
            "├ Зареєстровані: `{registered}`\n"
            "├ З депозитом: `{deposits}`\n"
            "└ Активовані: `{activated}`"
        ),
        "ru": (
            "⚙️ *АДМИН ПАНЕЛЬ*\n\n"
            "👥 *Нажали /start:*\n"
            "├ Новых сегодня: `{new_today}`\n"
            "├ Новых за 7 дней: `{new_week}`\n"
            "├ Новых за 30 дней: `{new_month}`\n"
            "└ Всего: `{total}`\n\n"
            "🔄 *Активные:*\n"
            "├ За 7 дней: `{week}`\n"
            "├ За 30 дней: `{month}`\n\n"
            "📊 *Воронка:*\n"
            "├ Зарегистрированные: `{registered}`\n"
            "├ С депозитом: `{deposits}`\n"
            "└ Активированные: `{activated}`"
        ),
    },
    "admin_broadcast": {
        "uk": "📢 *Розсилка*\n\nНадішли повідомлення (текст або фото з підписом) — бот розішле його всім користувачам.",
        "ru": "📢 *Рассылка*\n\nОтправь сообщение (текст или фото с подписью) — бот разошлёт его всем пользователям.",
    },
    "admin_add_user": {
        "uk": "➕ *Додати юзера*\n\nНадішли Telegram ID користувача — бот додасть його в allowed\\_users та активує бота.",
        "ru": "➕ *Добавить юзера*\n\nОтправь Telegram ID пользователя — бот добавит его в allowed\\_users и активирует бота.",
    },
    "broadcast_sending_msg":   {"uk": "📢 Розсилаю повідомлення {n} користувачам...", "ru": "📢 Рассылаю сообщение {n} пользователям..."},
    "broadcast_sending_photo": {"uk": "📢 Розсилаю фото {n} користувачам...", "ru": "📢 Рассылаю фото {n} пользователям..."},
    "broadcast_done":          {"uk": "✅ Розсилка завершена!\n\n📨 Доставлено: `{sent}`\n❌ Не доставлено: `{failed}`", "ru": "✅ Рассылка завершена!\n\n📨 Доставлено: `{sent}`\n❌ Не доставлено: `{failed}`"},

    "ai_limit":        {"uk": "⚠️ Ти вичерпав ліміт — *20 повідомлень на день*.\nСпробуй завтра!", "ru": "⚠️ Ты исчерпал лимит — *20 сообщений в день*.\nПопробуй завтра!"},
    "ai_error":        {"uk": "⚠️ Щось пішло не так, спробуй ще раз.", "ru": "⚠️ Что-то пошло не так, попробуй ещё раз."},
    "ai_remaining":    {"uk": "\n\n⚠️ _Залишилось {n} повідомлень на сьогодні_", "ru": "\n\n⚠️ _Осталось {n} сообщений на сегодня_"},
    "ai_illustration": {"uk": "🧠 *BEZDELNIK AI* — ілюстрація", "ru": "🧠 *BEZDELNIK AI* — иллюстрация"},
    "analyzing_image": {"uk": "🔍 Аналізую зображення...", "ru": "🔍 Анализирую изображение..."},
    "image_error":     {"uk": "⚠️ Не вдалось проаналізувати зображення, спробуй ще раз.", "ru": "⚠️ Не удалось проанализировать изображение, попробуй ещё раз."},

    "added_users": {"uk": "✅ Додано та активовано: {ids}", "ru": "✅ Добавлено и активировано: {ids}"},
    "add_failed":  {"uk": "❌ Не вдалося розпізнати жодного ID. Введіть числовий Telegram ID.", "ru": "❌ Не удалось распознать ни одного ID. Введите числовой Telegram ID."},

    "bind_err_other_account": {"uk": "❌ Цей ID вже прив'язаний до іншого акаунту Telegram", "ru": "❌ Этот ID уже привязан к другому аккаунту Telegram"},
    "bind_err_already":       {"uk": "❌ Твій Telegram вже прив'язаний до ID `{pid}`", "ru": "❌ Твой Telegram уже привязан к ID `{pid}`"},

    "reg_success": {
        "uk": (
            "✅ Реєстрація успішно завершена!\n"
            "Залишився лише останній крок перед початком роботи 🥳\n\n"
            "🤖 Наш торговий робот працює тільки з активними трейдерами, тому потрібно активувати акаунт — поповнити баланс на будь-яку зручну суму.\n\n"
            "📹 Внизу ти знайдеш коротку відеоінструкцію, де показано як поповнити рахунок вигідніше та отримати +60% до депозиту.\n"
            "🎁 Промокод для бонусу:\n"
            "👉 BEZ100 — +60% до депозиту\n"
            "...📩 Після поповнення:\n"
            "надішли мені ще раз свій ID акаунта, і ти отримаєш:\n\n"
            "✅ Доступ до індивідуальної торгівлі з роботом\n\n"
            "✅ Запрошення в закриті джерела екосистеми Alentra\n\n"
            "✅ Додаткові матеріали та сигнали\n\n"
            "🚀 Радий буду бачити тебе в команді. Ти вже на правильному шляху до результату!\n\n\n"
            "Поповніть рахунок і лише після цього натисніть кнопку нижче 👇"
        ),
        "ru": (
            "✅ Регистрация успешно завершена!\n"
            "Остался лишь последний шаг перед началом работы 🥳\n\n"
            "🤖 Наш торговый робот работает только с активными трейдерами, поэтому нужно активировать аккаунт — пополнить баланс на любую удобную сумму.\n\n"
            "📹 Внизу ты найдёшь короткую видеоинструкцию, где показано как пополнить счёт выгоднее и получить +60% к депозиту.\n"
            "🎁 Промокод для бонуса:\n"
            "👉 BEZ100 — +60% к депозиту\n"
            "...📩 После пополнения:\n"
            "отправь мне ещё раз свой ID аккаунта, и ты получишь:\n\n"
            "✅ Доступ к индивидуальной торговле с роботом\n\n"
            "✅ Приглашение в закрытые источники экосистемы Alentra\n\n"
            "✅ Дополнительные материалы и сигналы\n\n"
            "🚀 Буду рад видеть тебя в команде. Ты уже на правильном пути к результату!\n\n\n"
            "Пополните счёт и только после этого нажмите кнопку ниже 👇"
        ),
    },
    "account_not_registered": {"uk": "❌ Акаунт не зареєстрований через посилання", "ru": "❌ Аккаунт не зарегистрирован через ссылку"},
    "join_decline": {"uk": "❌ Щоб отримати доступ до VIP каналу, спочатку активуй бота!", "ru": "❌ Чтобы получить доступ к VIP каналу, сначала активируй бота!"},

    # ── Інструкція мови відповіді для AI ──
    "ai_respond_lang": {"uk": "Відповідай українською мовою.", "ru": "Отвечай на русском языке."},
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Повертає переклад за ключем + мовою. Фолбек: uk → сам ключ."""
    entry = TR.get(key, {})
    s = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if kwargs:
        try:
            s = s.format(**kwargs)
        except Exception:
            pass
    return s


# ─── JSON ХЕЛПЕРИ ──────────────────────────────────────────────
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # атомарна заміна — не зламає файл при крашу

def load_bindings(): return load_json(BINDINGS_PATH, {})

def bind_pocket_id(pocket_id: str, tg_id: int, lang: str = DEFAULT_LANG) -> tuple[bool, str]:
    """Прив'язує pocket_id до tg_id. Повертає (успіх, повідомлення)"""
    bindings = load_bindings()
    # Перевіряємо чи цей pocket_id вже прив'язаний
    if pocket_id in bindings:
        if bindings[pocket_id] == tg_id:
            return True, ""  # Вже прив'язаний до цього юзера — ок
        return False, t("bind_err_other_account", lang)
    # Перевіряємо чи цей tg_id вже має прив'язку
    for pid, tid in bindings.items():
        if tid == tg_id:
            return False, t("bind_err_already", lang, pid=pid)
    # Все ок — прив'язуємо
    bindings[pocket_id] = tg_id
    save_json(BINDINGS_PATH, bindings)
    return True, ""

def load_accounts(): return load_json(JSON_PATH, [])
def load_activated(): return load_json(ACTIVATED_PATH, [])
def load_deposits(): return load_json(DEPOSIT_PATH, {})
def load_stats(): return load_json(STATS_PATH, {})
def load_all_users(): return load_json(USERS_PATH, {})

def track_user(tg_id: int) -> bool:
    """Зберігає tg_id + дату останньої взаємодії. Повертає True якщо юзер новий."""
    users = load_all_users()
    uid = str(tg_id)
    is_new = uid not in users
    now = datetime.now(UA_TZ).isoformat()
    if is_new:
        users[uid] = {"first_seen": now, "last_seen": now}
    else:
        # Міграція старого формату (рядок → dict)
        if isinstance(users[uid], str):
            users[uid] = {"first_seen": users[uid], "last_seen": now}
        else:
            users[uid]["last_seen"] = now
    save_json(USERS_PATH, users)
    return is_new

def load_allowed_users():
    data = load_json(ALLOWED_USERS_PATH, {})
    return data.get("allowed_tg_ids", [])

def save_activated(user_id: int):
    activated = load_activated()
    if user_id not in activated:
        activated.append(user_id)
        save_json(ACTIVATED_PATH, activated)

def get_user_stats(tg_id: int) -> dict:
    stats = load_stats()
    uid = str(tg_id)
    if uid not in stats:
        stats[uid] = {"total": 0, "profit": 0, "loss": 0, "draw": 0,
                      "joined": datetime.now(UA_TZ).strftime("%Y-%m-%d")}
        save_json(STATS_PATH, stats)
    s = stats[uid]
    # Додаємо відсутні поля для старих записів
    for key in ("total", "profit", "loss", "draw"):
        if key not in s:
            s[key] = 0
    return s

def update_user_stats(tg_id: int, result: str):
    stats = load_stats()
    uid = str(tg_id)
    if uid not in stats:
        stats[uid] = {"total": 0, "profit": 0, "loss": 0, "draw": 0,
                      "joined": datetime.now(UA_TZ).strftime("%Y-%m-%d")}
    for key in ("total", "profit", "loss", "draw"):
        if key not in stats[uid]:
            stats[uid][key] = 0
    stats[uid]["total"] += 1
    if result in stats[uid]:
        stats[uid][result] += 1
    save_json(STATS_PATH, stats)

def get_activity_percentile(tg_id: int) -> int:
    stats = load_stats()
    uid = str(tg_id)
    my_total = stats.get(uid, {}).get("total", 0)
    all_totals = [v.get("total", 0) for v in stats.values()]
    if not all_totals:
        return 50
    better = sum(1 for t in all_totals if my_total > t)
    return int(better / len(all_totals) * 100)


# ─── ПАРИ ──────────────────────────────────────────────────────
BLOCKED_ASSETS = {"syp/usd otc", "irr/usd otc", "usd/rub otc", "eur/rub otc",
                  "syp/usd", "irr/usd", "usd/rub", "eur/rub"}

_assets_cache = {"data": [], "ts": 0}
_assets_lock = asyncio.Lock()

async def fetch_assets() -> list:
    now = asyncio.get_event_loop().time()
    # Кеш на 30 сек — щоб 100 юзерів одночасно не створювали 100 з'єднань
    if _assets_cache["data"] and (now - _assets_cache["ts"]) < 30:
        return _assets_cache["data"]
    async with _assets_lock:
        # Перевіряємо ще раз після отримання локу
        now2 = asyncio.get_event_loop().time()
        if _assets_cache["data"] and (now2 - _assets_cache["ts"]) < 30:
            return _assets_cache["data"]
        async def _fetch():
            async with PocketOptionAsync(SSID) as api:
                return await api.active_assets()
        try:
            assets = await asyncio.wait_for(_fetch(), timeout=20)
            active = [a for a in assets if a.get("is_active")
                      and a.get("name", "").lower() not in BLOCKED_ASSETS]
            result = sorted(active, key=lambda x: x.get("payout", 0), reverse=True)
            _assets_cache["data"] = result
            _assets_cache["ts"] = now2
            return result
        except Exception as e:
            print(f"fetch_assets error: {e}")
            return _assets_cache["data"] or []

CRYPTO_KEYWORDS = {
    "bitcoin", "btc", "ethereum", "eth", "litecoin", "ltc", "ripple", "xrp",
    "cardano", "ada", "polkadot", "dot", "chainlink", "link", "dogecoin", "doge",
    "solana", "sol", "avalanche", "avax", "polygon", "matic", "tron", "trx",
    "toncoin", "ton", "bnb", "bch", "dash", "eos", "iota", "monero", "xmr",
    "stellar", "xlm", "tezos", "xtz", "uniswap", "uni", "coinbase",
}

def _is_crypto_name(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in CRYPTO_KEYWORDS)

def filter_by_asset_type(assets: list, atype: str) -> list:
    mapping = {
        "forex": "currency",
        "crypto": "cryptocurrency",
        "stock": "stock",
        "commodity": "commodity",
        "index": "index",
    }
    t = mapping.get(atype)
    if not t:
        return assets
    filtered = [a for a in assets if a.get("asset_type") == t or a.get("type") == t]
    if not filtered:
        lower_t = t.lower()
        filtered = [a for a in assets if lower_t in str(a.get("asset_type", "")).lower()
                    or lower_t in str(a.get("type", "")).lower()]
    # Не показувати крипту у форексі і навпаки
    if atype == "forex":
        filtered = [a for a in filtered if not _is_crypto_name(a.get("name", ""))]
    elif atype == "crypto":
        filtered = [a for a in filtered if _is_crypto_name(a.get("name", ""))]
    return filtered

def get_otc_enabled(context, tg_id: int = None) -> bool:
    # Спочатку перевіряємо context (швидко)
    if "otc_enabled" in context.user_data:
        return context.user_data["otc_enabled"]
    # Якщо немає в context — читаємо з файлу (після рестарту бота)
    if tg_id:
        settings = load_json(OTC_SETTINGS_PATH, {})
        val = settings.get(str(tg_id), True)
        context.user_data["otc_enabled"] = val
        return val
    return True

def save_otc_enabled(tg_id: int, enabled: bool):
    settings = load_json(OTC_SETTINGS_PATH, {})
    settings[str(tg_id)] = enabled
    save_json(OTC_SETTINGS_PATH, settings)


def get_lang(context, tg_id: int = None) -> str:
    """Повертає мову юзера (uk/ru). Спочатку context, потім файл, потім дефолт."""
    if context is not None and "lang" in context.user_data:
        return context.user_data["lang"]
    if tg_id:
        settings = load_json(LANG_SETTINGS_PATH, {})
        val = settings.get(str(tg_id), DEFAULT_LANG)
        if val not in SUPPORTED_LANGS:
            val = DEFAULT_LANG
        if context is not None:
            context.user_data["lang"] = val
        return val
    return DEFAULT_LANG


def save_lang(tg_id: int, lang: str):
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    settings = load_json(LANG_SETTINGS_PATH, {})
    settings[str(tg_id)] = lang
    save_json(LANG_SETTINGS_PATH, settings)

def apply_otc_filter(assets: list, context) -> list:
    if get_otc_enabled(context):
        return [a for a in assets if a.get("is_otc")]
    return [a for a in assets if not a.get("is_otc")]


# ─── ЦІНА ──────────────────────────────────────────────────────
async def get_current_price(symbol: str, retries: int = 2) -> float | None:
    async def _get():
        async with PocketOptionAsync(SSID) as api:
            stream = await api.subscribe_symbol(symbol)
            async for tick in stream:
                val = tick.get("close")
                if val:
                    return float(val)
                break
        return None
    for attempt in range(retries):
        try:
            return await asyncio.wait_for(_get(), timeout=15)
        except Exception as e:
            print(f"Price error for {symbol} (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(1)
    return None


# ─── СИГНАЛИ ───────────────────────────────────────────────────
def random_ai_signal(asset: dict, timeframe: int, price: float | None) -> dict:
    return {
        "name": asset["name"],
        "direction": random.choice(["🟢 BUY", "🔴 SELL"]),
        "timeframe": timeframe,
        "symbol": asset["symbol"],
        "confidence": random.randint(83, 95),
        "payout": asset.get("payout", "?"),
        "type": "BEZDELNIK AI 🤖",
        "is_otc": asset.get("is_otc", False),
        "current_price": price,
    }


async def indicator_signal(asset: dict, timeframe: int, selected_indicators: list | None = None, lang: str = DEFAULT_LANG) -> dict:
    symbol = asset["symbol"]
    try:
        if timeframe <= 60:      count = 5000
        elif timeframe <= 300:   count = 10000
        elif timeframe <= 900:   count = 30000
        else:                    count = 100000

        async def _get_candles():
            async with PocketOptionAsync(SSID) as api:
                return await api.get_candles(symbol, timeframe, count)

        candles = None
        for _attempt in range(2):
            try:
                candles = await asyncio.wait_for(_get_candles(), timeout=30)
                break
            except Exception as ce:
                print(f"get_candles error {symbol} (attempt {_attempt+1}): {ce}")
                if _attempt == 0:
                    await asyncio.sleep(1)
        if candles is None:
            return {"error": t("data_error", lang, name=asset['name'])}

        current_price = await get_current_price(symbol)

        if len(candles) < 14:
            raise ValueError(f"Мало даних: {len(candles) if candles else 0}")

        df = pd.DataFrame(candles)
        df["close"] = df["close"].astype(float)
        if "high" in df.columns:
            df["high"] = df["high"].astype(float)
        if "low" in df.columns:
            df["low"] = df["low"].astype(float)

        n = len(df)
        use = selected_indicators or [k for _, k in ALL_INDICATORS]

        buy_score = 0
        sell_score = 0
        result = {}

        if "rsi" in use:
            rsi = ta.momentum.RSIIndicator(df["close"], window=min(14, n-1)).rsi().iloc[-1]
            result["rsi"] = round(rsi, 1)
            if rsi < 30:      buy_score += 2
            elif rsi < 45:    buy_score += 1
            elif rsi > 70:    sell_score += 2
            elif rsi > 55:    sell_score += 1

        if "ema" in use:
            ef = ta.trend.EMAIndicator(df["close"], window=min(9, n-1)).ema_indicator().iloc[-1]
            es = ta.trend.EMAIndicator(df["close"], window=min(21, n-1)).ema_indicator().iloc[-1]
            result["ema"] = t("val_ema_bull", lang) if ef > es else t("val_ema_bear", lang)
            if ef > es: buy_score += 1
            else:       sell_score += 1

        if "macd" in use:
            m = ta.trend.MACD(df["close"])
            ml = m.macd().iloc[-1]
            ms = m.macd_signal().iloc[-1]
            result["macd"] = t("val_macd_bull", lang) if ml > ms else t("val_macd_bear", lang)
            if ml > ms: buy_score += 1
            else:       sell_score += 1

        if "stoch" in use and "high" in df.columns and "low" in df.columns:
            stoch = ta.momentum.StochasticOscillator(df["high"], df["low"], df["close"])
            sk = stoch.stoch().iloc[-1]
            result["stoch"] = round(sk, 1)
            if sk < 20:   buy_score += 1
            elif sk > 80: sell_score += 1

        if "bb" in use:
            bb = ta.volatility.BollingerBands(df["close"])
            bbl = bb.bollinger_lband().iloc[-1]
            bbh = bb.bollinger_hband().iloc[-1]
            c = df["close"].iloc[-1]
            if c <= bbl:   buy_score += 1; result["bb"] = t("val_bb_low", lang)
            elif c >= bbh: sell_score += 1; result["bb"] = t("val_bb_high", lang)
            else:          result["bb"] = t("val_bb_mid", lang)

        if buy_score > sell_score:
            direction = "🟢 BUY"
            confidence = min(95, 55 + buy_score * 8)
        elif sell_score > buy_score:
            direction = "🔴 SELL"
            confidence = min(95, 55 + sell_score * 8)
        else:
            # При нічиї — визначаємо напрямок по останній свічці (не рандом)
            last_close = df["close"].iloc[-1]
            last_open = df["open"].iloc[-1]
            if last_close >= last_open:
                direction = "🟢 BUY"
            else:
                direction = "🔴 SELL"
            confidence = 60

        return {
            "name": asset["name"], "symbol": symbol,
            "direction": direction, "timeframe": timeframe,
            "confidence": confidence, "payout": asset.get("payout", "?"),
            "type": "Індикатори 📊", "is_otc": asset.get("is_otc", False),
            "current_price": current_price, **result,
        }

    except Exception as e:
        print(f"Indicator error {symbol}: {e}")
        price = await get_current_price(symbol)
        return random_ai_signal(asset, timeframe, price)


async def bezdelnik_ai_signal(asset: dict, timeframe: int, lang: str = DEFAULT_LANG) -> dict:
    """Отримує дані і передає в GPT для аналізу"""
    symbol = asset["symbol"]
    try:
        if timeframe <= 60:      count = 5000
        elif timeframe <= 300:   count = 10000
        else:                    count = 30000

        async def _get_candles():
            async with PocketOptionAsync(SSID) as api:
                return await api.get_candles(symbol, timeframe, count)

        candles = None
        for _attempt in range(2):
            try:
                candles = await asyncio.wait_for(_get_candles(), timeout=30)
                break
            except Exception as ce:
                print(f"get_candles error {symbol} (attempt {_attempt+1}): {ce}")
                if _attempt == 0:
                    await asyncio.sleep(1)
        if candles is None:
            return {"error": t("data_error", lang, name=asset['name'])}

        current_price = await get_current_price(symbol)

        if not candles or len(candles) < 10:
            raise ValueError("Мало даних")

        df = pd.DataFrame(candles)
        df["close"] = df["close"].astype(float)

        # Рахуємо базові індикатори для GPT
        n = len(df)
        rsi = ta.momentum.RSIIndicator(df["close"], window=min(14, n-1)).rsi().iloc[-1]
        ef = ta.trend.EMAIndicator(df["close"], window=min(9, n-1)).ema_indicator().iloc[-1]
        es = ta.trend.EMAIndicator(df["close"], window=min(21, n-1)).ema_indicator().iloc[-1]
        m = ta.trend.MACD(df["close"])
        ml = m.macd().iloc[-1]
        ms = m.macd_signal().iloc[-1]

        # Останні 5 свічок для контексту
        last_candles = df["close"].tail(5).tolist()

        prompt = f"""Ти торговий аналітик бінарних опціонів. Проаналізуй дані і дай сигнал.

Актив: {asset['name']} ({symbol})
Таймфрейм: {timeframe} секунд
Поточна ціна: {current_price}
Виплата: {asset.get('payout')}%

Індикатори:
- RSI(14): {round(rsi, 2)}
- EMA9: {round(ef, 5)}, EMA21: {round(es, 5)} → {'EMA9 > EMA21 (бичача)' if ef > es else 'EMA9 < EMA21 (медвежа)'}
- MACD лінія: {round(ml, 5)}, сигнал: {round(ms, 5)} → {'MACD > сигнал (бичачий)' if ml > ms else 'MACD < сигнал (медвежий)'}
- Останні 5 цін закриття: {[round(c, 5) for c in last_candles]}

Відповідай ТІЛЬКИ у форматі JSON без markdown:
{{"direction": "BUY або SELL", "confidence": число від 60 до 95, "reason": "коротке пояснення до 100 символів"}}

Поле "reason" пиши цією мовою: {t("ai_respond_lang", lang)}"""

        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        direction_str = data.get("direction", "BUY").upper()
        direction = "🟢 BUY" if "BUY" in direction_str else "🔴 SELL"
        confidence = int(data.get("confidence", 75))
        reason = data.get("reason", "")

        return {
            "name": asset["name"], "symbol": symbol,
            "timeframe": timeframe,
            "direction": direction,
            "confidence": confidence, "payout": asset.get("payout", "?"),
            "type": "BEZDELNIK AI 🧠", "is_otc": asset.get("is_otc", False),
            "current_price": current_price,
            "rsi": round(rsi, 1),
            "ema": t("val_ema_bull", lang) if ef > es else t("val_ema_bear", lang),
            "macd": t("val_macd_bull", lang) if ml > ms else t("val_macd_bear", lang),
            "ai_reason": reason,
        }

    except Exception as e:
        print(f"BEZDELNIK AI error {symbol}: {e}")
        price = await get_current_price(symbol)
        return random_ai_signal(asset, timeframe, price)


# ─── АВТОПЕРЕВІРКА РЕЗУЛЬТАТУ ──────────────────────────────────
async def check_signal_result(context: ContextTypes.DEFAULT_TYPE, tg_id: int,
                               symbol: str, direction: str,
                               entry_price: float, timeframe: int):
    await asyncio.sleep(timeframe)
    try:
        exit_price = await get_current_price(symbol)
        context.user_data["active_signal"] = None

        if not exit_price or not entry_price:
            return

        price_up = exit_price > entry_price
        result = "profit" if ("BUY" in direction and price_up) or ("SELL" in direction and not price_up) else "loss"

        lang = get_lang(context, tg_id)
        diff = round(abs(exit_price - entry_price), 5)
        emoji = "✅" if result == "profit" else "❌"
        label = t("res_profit", lang) if result == "profit" else t("res_loss", lang)

        update_user_stats(tg_id, result)

        text = (
            f"{emoji} *{label}*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💱 `{fmt_symbol(symbol)}`\n"
            f"{t('sig_direction', lang)} *{direction}*\n"
            f"{t('sig_entry', lang)}   `{fmt_price(entry_price)}`\n"
            f"{t('res_exit', lang)}  `{fmt_price(exit_price)}`\n"
            f"{t('res_diff', lang)} `{fmt_price(diff)}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now(UA_TZ).strftime('%H:%M:%S')}"
        )
        img_path = "imgs/start_imgs/плюс.png" if result == "profit" else "imgs/start_imgs/мінус.png"
        try:
            with open(img_path, "rb") as f:
                await context.bot.send_photo(
                    chat_id=tg_id, photo=f,
                    caption=text, parse_mode="Markdown",
                    reply_markup=main_menu(context, tg_id)
                )
        except Exception:
            await context.bot.send_message(
                chat_id=tg_id, text=text, parse_mode="Markdown",
                reply_markup=main_menu(context, tg_id)
            )
    except Exception as e:
        print(f"check_signal_result error: {e}")
        context.user_data["active_signal"] = None


# ─── ФОРМАТУВАННЯ ──────────────────────────────────────────────
def fmt_price(price) -> str:
    """Форматує ціну: без наукової нотації, прибирає зайві нулі"""
    if price is None:
        return "?"
    p = float(price)
    if p == 0:
        return "0"
    if p >= 1:
        return f"{p:.5f}".rstrip("0").rstrip(".")
    # Для дуже маленьких чисел — показуємо всі значущі цифри
    return f"{p:.10f}".rstrip("0").rstrip(".")


def fmt_symbol(symbol: str) -> str:
    """USDCHF_otc → USD/CHF OTC, BTCUSD → BTC/USD"""
    s = symbol.replace("_otc", "").replace("_OTC", "")
    is_otc = symbol.lower().endswith("_otc")
    # Вставляємо / посередині (якщо 6 символів — це forex типу USDCHF)
    if "/" not in s and len(s) == 6 and s.isalpha():
        s = s[:3] + "/" + s[3:]
    elif "/" not in s and len(s) >= 6 and s.isalpha():
        # Крипто типу BTCUSD, ETHUSD
        s = s[:3] + "/" + s[3:]
    if is_otc:
        s += " OTC"
    return s

def fmt_tf(seconds: int, lang: str = DEFAULT_LANG) -> str:
    if seconds < 60:     return f"{seconds} {t('tf_sec', lang)}"
    elif seconds < 3600: return f"{seconds // 60} {t('tf_min', lang)}"
    else:                return f"{seconds // 3600} {t('tf_hour', lang)}"

def format_signal(sig: dict, lang: str = DEFAULT_LANG) -> str:
    pair_type = "OTC 🔄" if sig.get("is_otc") else "Official 📈"
    text = (
        f"{t('sig_title', lang)}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💱 *{sig['name']}* (`{fmt_symbol(sig['symbol'])}`)\n"
        f"{t('sig_type', lang)}            `{pair_type}`\n"
        f"{t('sig_direction', lang)}    *{sig['direction']}*\n"
        f"{t('sig_expiration', lang)} `{fmt_tf(sig['timeframe'], lang)}`\n"
        f"{t('sig_confidence', lang)} `{sig['confidence']}%`\n"
        f"{t('sig_payout', lang)}      `{sig['payout']}%`\n"
        f"{t('sig_method', lang)}         `{sig['type']}`\n"
    )
    if sig.get("current_price"):
        text += f"{t('sig_entry', lang)}    `{fmt_price(sig['current_price'])}`\n"
    if "rsi" in sig:
        text += (
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📉 RSI:    `{sig['rsi']}`\n"
            f"📊 EMA:   `{sig['ema']}`\n"
            f"📈 MACD:  `{sig['macd']}`\n"
        )
    if sig.get("ai_reason"):
        text += f"🧠 AI: _{sig['ai_reason']}_\n"
    if "stoch" in sig:
        text += f"📊 Stoch: `{sig['stoch']}`\n"
    if "bb" in sig:
        text += f"📊 BB: `{sig['bb']}`\n"
    text += f"━━━━━━━━━━━━━━━━━━━\n🕐 {datetime.now(UA_TZ).strftime('%H:%M:%S')}"
    return text


# ─── КЛАВІАТУРИ ────────────────────────────────────────────────
def main_menu_kb(otc: bool, tg_id: int = 0, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    otc_label = t("otc_on", lang) if otc else t("otc_off", lang)
    lang_uk = ("✅ " if lang == "uk" else "") + t("btn_lang_uk", lang)
    lang_ru = ("✅ " if lang == "ru" else "") + t("btn_lang_ru", lang)
    rows = [
        [InlineKeyboardButton(otc_label, callback_data="toggle_otc")],
        [
            InlineKeyboardButton(t("btn_on_request", lang), callback_data="sig_request"),
            InlineKeyboardButton(t("btn_auto_ai", lang), callback_data="sig_auto"),
        ],
        [
            InlineKeyboardButton(t("btn_indicators", lang), callback_data="sig_indicators"),
            InlineKeyboardButton(t("btn_bezdelnik_ai", lang), callback_data="ai_chat_start"),
        ],
        [InlineKeyboardButton(t("btn_my_signals", lang), callback_data="my_signals")],
        [
            InlineKeyboardButton(lang_uk, callback_data="set_lang_uk"),
            InlineKeyboardButton(lang_ru, callback_data="set_lang_ru"),
        ],
        [InlineKeyboardButton(t("btn_help", lang), url="https://t.me/NazarUkrain")],
    ]
    if tg_id in ADMIN_IDS:
        rows.append([InlineKeyboardButton(t("btn_admin_panel", lang), callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def main_menu(context, tg_id: int = 0) -> InlineKeyboardMarkup:
    return main_menu_kb(get_otc_enabled(context, tg_id), tg_id, get_lang(context, tg_id))

def start_menu_kb(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    """Клавіатура стартового екрана (для нових / неактивованих юзерів) з перемикачем мови."""
    lang_uk = ("✅ " if lang == "uk" else "") + t("btn_lang_uk", lang)
    lang_ru = ("✅ " if lang == "ru" else "") + t("btn_lang_ru", lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_get_bot", lang), callback_data="get_bot")],
        [
            InlineKeyboardButton(t("btn_help", lang), url="https://t.me/NazarUkrain"),
            InlineKeyboardButton(t("btn_reviews", lang), url="https://t.me/+Hw8LxioNOIJiN2Qy"),
        ],
        [InlineKeyboardButton(t("btn_channel", lang), url="https://t.me/+6ejF11uYS6c3MzFi")],
        [
            InlineKeyboardButton(lang_uk, callback_data="set_lang_uk"),
            InlineKeyboardButton(lang_ru, callback_data="set_lang_ru"),
        ],
    ])

def asset_type_kb(mode: str, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for _label, key in ASSET_TYPES:
        row.append(InlineKeyboardButton(t(f"atype_{key}", lang), callback_data=f"atype_{mode}_{key}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data="to_main_menu")])
    return InlineKeyboardMarkup(rows)

def pair_kb(mode: str, assets: list, page: int = 0, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    per_page = 8
    total = len(assets)
    start = page * per_page
    end = min(start + per_page, total)

    rows = []
    row = []
    for a in assets[start:end]:
        label = f"{'🔄' if a['is_otc'] else '📈'} {a['name']} {a['payout']}%"
        row.append(InlineKeyboardButton(label, callback_data=f"pair_{mode}_{a['symbol']}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"page_{mode}_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{max(1,(total-1)//per_page+1)}", callback_data="noop"))
    if end < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"page_{mode}_{page+1}"))
    if nav: rows.append(nav)

    rows.append([
        InlineKeyboardButton(t("btn_random_pair", lang), callback_data=f"randpair_{mode}"),
        InlineKeyboardButton(t("btn_back", lang), callback_data=f"sig_{mode}"),
    ])
    return InlineKeyboardMarkup(rows)

def timeframe_kb(mode: str, symbol: str, allowed: list, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for tf in allowed:
        row.append(InlineKeyboardButton(fmt_tf(tf, lang), callback_data=f"tf_{mode}_{symbol}_{tf}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data=f"sig_{mode}")])
    return InlineKeyboardMarkup(rows)

def indicator_select_kb(mode: str, symbol: str, timeframe: int, selected: list, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for name, key in ALL_INDICATORS:
        check = "✅" if key in selected else "◻️"
        row.append(InlineKeyboardButton(f"{check} {name}", callback_data=f"indsel_{mode}_{symbol}_{timeframe}_{key}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    inds = "|".join(selected) if selected else "all"
    rows.append([InlineKeyboardButton(t("btn_get_signal", lang), callback_data=f"indgo_{mode}_{symbol}_{timeframe}_{inds}")])
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data=f"sig_{mode}")])
    return InlineKeyboardMarkup(rows)

# Таймфрейм меню для ІНДИКАТОРІВ (без вибору пари — рандомна пара)
def tf_only_kb(mode: str, symbol: str, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for tf in WORKING_TIMEFRAMES:
        row.append(InlineKeyboardButton(fmt_tf(tf, lang), callback_data=f"tf_{mode}_{symbol}_{tf}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(t("btn_back", lang), callback_data="to_main_menu")])
    return InlineKeyboardMarkup(rows)

def after_signal_kb(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_main_menu", lang), callback_data="menu_new")]])

def bot_activate_menu(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_activate_bot", lang), callback_data="activate_bot")]])

def deposit_menu(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_check_deposit", lang), callback_data="check_deposit")]])


# ─── ХЕНДЛЕРИ ──────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    track_user(tg_id)
    lang = get_lang(context, tg_id)
    # Автоактивація для allowed users
    if tg_id in load_allowed_users():
        save_activated(tg_id)
    if tg_id in load_activated():
        await update.message.reply_text(
            t("menu_activated", lang),
            parse_mode="Markdown", reply_markup=main_menu(context, tg_id)
        )
        return
    # Фото
    with open("imgs/start_imgs/start.png", "rb") as f:
        await update.message.reply_photo(photo=f)
    # Основне повідомлення
    await update.message.reply_text(
        t("welcome_full", lang),
        parse_mode="HTML",
        reply_markup=start_menu_kb(lang)
    )


async def safe_edit(message, text, **kwargs):
    """edit_text з fallback: видаляє старе повідомлення і надсилає нове"""
    try:
        await message.edit_text(text, **kwargs)
    except Exception:
        try:
            await message.delete()
        except Exception:
            pass
        await message.chat.send_message(text, **kwargs)


async def safe_edit_photo(message, photo_path, caption="", **kwargs):
    """Для меню з фото: видаляє старе і шле нове фото"""
    try:
        await message.delete()
    except Exception:
        pass
    with open(photo_path, "rb") as f:
        await message.chat.send_photo(photo=f, caption=caption, **kwargs)


def check_active_signal(context) -> tuple[bool, int]:
    """Повертає (заблоковано, секунд залишилось)"""
    active = context.user_data.get("active_signal")
    if not active:
        return False, 0
    end_time = active.get("end_time")
    if end_time and datetime.now(UA_TZ) < end_time:
        remaining = int((end_time - datetime.now(UA_TZ)).total_seconds())
        return True, remaining
    context.user_data["active_signal"] = None
    return False, 0


# Маппінг: asset_type → {True: [otc папки], False: [regular папки]}
ASSET_TYPE_TO_IMG_FOLDER = {
    "currency":       {True: ["forex otc"], False: ["forex official"]},
    "cryptocurrency": {True: ["crypto/otc"], False: ["crypto/regular"]},
    "stock":          {True: ["stocks/otc"], False: ["stocks/regular"]},
    "commodity":      {True: ["commodities/otc"], False: ["commodities/regular"]},
    "index":          {True: ["index/otc"], False: ["index/regular"]},
}

def _normalize_name(name: str) -> str:
    """Нормалізує назву: прибирає все зайве для порівняння"""
    n = name.upper().strip()
    for suf in ("_OTC", " OTC", "(OTC)"):
        n = n.replace(suf, "")
    n = n.replace("/", "").replace("_", "").replace("-", "")
    n = n.replace("&", "").replace("'", "").replace("`", "").replace("\u2019", "")
    n = re.sub(r'\s+', '', n)
    return n


def _normalize_fname(fname: str) -> str:
    """Нормалізує ім'я файлу для порівняння"""
    n = fname.upper()
    for ext in (".PNG", ".JPG", ".JPEG"):
        n = n.replace(ext, "")
    # Розліплюємо злиті слова
    n = re.sub(r'(\w)OTC', r'\1 OTC', n)
    n = re.sub(r'(\w)DOWN', r'\1 DOWN', n)
    n = re.sub(r'(\w)UP\b', r'\1 UP', n)
    n = " ".join(n.split()).strip()
    n = re.sub(r'\s*-\d+$', '', n).strip()
    return n


def find_signal_image(asset: dict, direction: str) -> str | None:
    """Шукає фото для пари + напрямок (UP/DOWN)"""
    name = _normalize_name(asset.get("name", ""))
    is_otc = asset.get("is_otc", False)
    asset_type = asset.get("asset_type", "")
    up_down = "UP" if "BUY" in direction else "DOWN"

    type_map = ASSET_TYPE_TO_IMG_FOLDER.get(asset_type, {})
    # Спочатку шукаємо в правильній папці (otc/regular), потім фолбек на іншу
    folders = type_map.get(is_otc, []) + type_map.get(not is_otc, [])

    for folder in folders:
        img_dir = os.path.join("imgs", folder)
        if not os.path.isdir(img_dir):
            continue
        for fname in os.listdir(img_dir):
            fc = _normalize_fname(fname)
            # Розділяємо: "APPLE OTC UP" → name_part="APPLE OTC", direction="UP"
            parts = fc.rsplit(" ", 1)
            if len(parts) != 2 or parts[1] not in ("UP", "DOWN"):
                continue
            if parts[1] != up_down:
                continue
            # Прибираємо OTC з імені файлу і нормалізуємо
            f_base = parts[0].replace(" OTC", "").strip()
            f_base = f_base.replace("&", "").replace("'", "").replace("`", "")
            f_base = re.sub(r'\s+', '', f_base)
            if f_base == name:
                return os.path.join(img_dir, fname)

    return None


async def send_signal_and_track(query, context, asset: dict, sig: dict, mode: str):
    """Відправляє сигнал і запускає автоперевірку"""
    entry_price = sig.get("current_price")
    timeframe = sig["timeframe"]
    symbol = sig["symbol"]

    block_time = 60  # блокування нових сигналів — макс 5 хв
    context.user_data["active_signal"] = {
        "symbol": symbol, "direction": sig["direction"],
        "entry_price": entry_price,
        "end_time": datetime.now(UA_TZ) + timedelta(seconds=block_time)
    }

    # Видаляємо повідомлення "Генерую сигнал..."
    try:
        await query.message.delete()
    except Exception:
        pass

    # Фото пари + напрямок
    lang = get_lang(context, query.from_user.id)
    chat_id = query.message.chat_id
    img_path = find_signal_image(asset, sig["direction"])
    if img_path:
        with open(img_path, "rb") as f:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=f,
                caption=format_signal(sig, lang),
                parse_mode="Markdown",
                reply_markup=after_signal_kb(lang)
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=format_signal(sig, lang), parse_mode="Markdown", reply_markup=after_signal_kb(lang)
        )

    if entry_price:
        asyncio.create_task(check_signal_result(
            context=context, tg_id=query.from_user.id,
            symbol=symbol, direction=sig["direction"],
            entry_price=entry_price, timeframe=timeframe
        ))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = get_lang(context, query.from_user.id)

    # ── Перемикач мови ──
    if data in ("set_lang_uk", "set_lang_ru"):
        new_lang = "uk" if data == "set_lang_uk" else "ru"
        context.user_data["lang"] = new_lang
        save_lang(query.from_user.id, new_lang)
        lang = new_lang
        if query.from_user.id in load_activated():
            # Активований юзер → головне меню
            await safe_edit(query.message,
                t("menu_title", lang),
                parse_mode="Markdown", reply_markup=main_menu(context, query.from_user.id)
            )
        else:
            # Новий / неактивований юзер → перемальовуємо стартовий екран
            try:
                await query.message.delete()
            except Exception:
                pass
            with open("imgs/start_imgs/start.png", "rb") as f:
                await query.message.chat.send_photo(
                    photo=f,
                    caption=t("welcome_short", lang),
                    parse_mode="HTML",
                    reply_markup=start_menu_kb(lang)
                )
        return

    # ── Головне меню ──
    if data == "to_main_menu":
        context.user_data[AI_CHAT_MODE] = False
        await safe_edit(query.message,
            t("menu_title", lang),
            parse_mode="Markdown", reply_markup=main_menu(context, query.from_user.id)
        )

    elif data == "menu_new":
        # Після сигналу — нове повідомлення, сигнал залишається в чаті
        context.user_data[AI_CHAT_MODE] = False
        # Прибираємо кнопку з повідомлення сигналу
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=t("menu_title", lang),
            parse_mode="Markdown",
            reply_markup=main_menu(context, query.from_user.id)
        )

    elif data == "to_start":
        context.user_data[AI_CHAT_MODE] = False
        try:
            await query.message.delete()
        except Exception:
            pass
        with open("imgs/start_imgs/start.png", "rb") as f:
            await query.message.chat.send_photo(
                photo=f,
                caption=t("welcome_short", lang),
                parse_mode="HTML",
                reply_markup=start_menu_kb(lang)
            )

    # ── Стартові кнопки ──
    elif data == "get_bot":
        await safe_edit(query.message,
            t("get_bot_text", lang),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(t("btn_registration", lang), url=REF_LINK_BASE),
                    InlineKeyboardButton(t("btn_check_id", lang), callback_data="check_id"),
                ],
                [InlineKeyboardButton(t("btn_back", lang), callback_data="to_start")],
            ])
        )

    elif data == "help_contact":
        await safe_edit(query.message,
            t("help_contact", lang),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_write", lang), url="https://t.me/Roma_pdlps")],
                [InlineKeyboardButton(t("btn_back", lang), callback_data="to_start")],
            ])
        )

    elif data == "reviews":
        await safe_edit(query.message,
            t("reviews_text", lang),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_back", lang), callback_data="to_start")],
            ])
        )

    elif data == "noop":
        pass

    elif data == "toggle_otc":
        new_val = not get_otc_enabled(context, query.from_user.id)
        context.user_data["otc_enabled"] = new_val
        save_otc_enabled(query.from_user.id, new_val)
        await query.message.edit_reply_markup(reply_markup=main_menu(context, query.from_user.id))

    # ── Реєстрація ──
    elif data == "check_id":
        context.user_data[ASKING_ID] = True
        await safe_edit_photo(query.message, "imgs/start_imgs/id_get1.jpg",
            caption=t("check_id_text", lang),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_back", lang), callback_data="get_bot")]
            ])
        )

    elif data == "check_deposit":
        uid = context.user_data.get("last_user_id")
        deposits = load_deposits()
        if uid and uid in deposits:
            await safe_edit(query.message,
                t("deposit_success", lang),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(t("btn_vip_channel", lang), url="https://t.me/+4MRt6RulOTllNDcy"),
                        InlineKeyboardButton(t("btn_training", lang), url="https://t.me/+SefYmx71q5ZhNDNi"),
                        InlineKeyboardButton("CHAT", url="https://t.me/+-PFhuomcUcNhN2Yy"),
                    ],
                    [
                        InlineKeyboardButton("Trade Squad", url="https://t.me/+UeH2gccJ044xYmIy"),
                        InlineKeyboardButton("TEAM", url="https://t.me/+E-Z0zFmB7FZjNzMy"),
                        InlineKeyboardButton(t("btn_activate_robot", lang), callback_data="activate_bot"),
                    ]
                ])
            )
        else:
            back_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_check_deposit", lang), callback_data="check_deposit")],
                [InlineKeyboardButton(t("btn_back", lang), callback_data="check_id")]
            ])
            await safe_edit(query.message, t("deposit_not_found", lang), reply_markup=back_kb)

    elif data == "activate_bot":
        save_activated(query.from_user.id)
        await safe_edit(query.message,
            t("menu_activated_now", lang),
            parse_mode="Markdown", reply_markup=main_menu(context, query.from_user.id)
        )

    # ── AI ЧАТ ТРЕЙДЕР ──
    elif data == "ai_chat_start":
        context.user_data[AI_CHAT_MODE] = True
        context.user_data["ai_chat_history"] = []
        await safe_edit(query.message,
            t("ai_chat_start", lang),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")]
            ])
        )

    # ── АДМІН ПАНЕЛЬ ──
    elif data == "admin_panel":
        if query.from_user.id not in ADMIN_IDS:
            return
        users = load_all_users()
        now = datetime.now(UA_TZ)
        total = len(users)

        def _parse_dt(s):
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UA_TZ)
            return dt

        def _get_date(val, key="last_seen"):
            if isinstance(val, str):
                return _parse_dt(val)
            return _parse_dt(val.get(key, val.get("first_seen", now.isoformat())))

        def _get_first(val):
            return _get_date(val, "first_seen")

        week = sum(1 for d in users.values() if (now - _get_date(d)).days <= 7)
        month = sum(1 for d in users.values() if (now - _get_date(d)).days <= 30)
        new_today = sum(1 for d in users.values() if (now - _get_first(d)).days == 0)
        new_week = sum(1 for d in users.values() if (now - _get_first(d)).days <= 7)
        new_month = sum(1 for d in users.values() if (now - _get_first(d)).days <= 30)
        activated = len(load_activated())
        deposits = len(load_deposits())
        registered = len(load_accounts())

        await safe_edit(query.message,
            t("admin_panel", lang, new_today=new_today, new_week=new_week,
              new_month=new_month, total=total, week=week, month=month,
              registered=registered, deposits=deposits, activated=activated),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_broadcast", lang), callback_data="admin_broadcast")],
                [InlineKeyboardButton(t("btn_add_user", lang), callback_data="admin_add_user")],
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")],
            ])
        )

    elif data == "admin_broadcast":
        if query.from_user.id not in ADMIN_IDS:
            return
        context.user_data[BROADCAST_MODE] = True
        await safe_edit(query.message,
            t("admin_broadcast", lang),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_cancel", lang), callback_data="admin_panel")]
            ])
        )

    elif data == "admin_add_user":
        if query.from_user.id not in ADMIN_IDS:
            return
        context.user_data[ADDING_USER_MODE] = True
        await safe_edit(query.message,
            t("admin_add_user", lang),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_cancel", lang), callback_data="admin_panel")]
            ])
        )

    # ── НА ЗАПИТ / BEZDELNIK AI → вибір типу активу ──
    elif data in ("sig_request", "sig_bezdelnik"):
        blocked, rem = check_active_signal(context)
        if blocked:
            await safe_edit(query.message,
                t("signal_cooldown", lang, m=rem//60, s=rem%60),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")
                ]])
            )
            return
        mode = data.replace("sig_", "")
        await safe_edit(query.message, t("choose_asset_type", lang), reply_markup=asset_type_kb(mode, lang))

    # ── АВТО ШІ → відразу рандомна пара і таймфрейм ──
    elif data == "sig_auto":
        blocked, rem = check_active_signal(context)
        if blocked:
            await safe_edit(query.message,
                t("signal_cooldown", lang, m=rem//60, s=rem%60),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")
                ]])
            )
            return
        assets = apply_otc_filter(await fetch_assets(), context)
        if not assets:
            await safe_edit(query.message, t("no_assets", lang),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")
                ]]))
            return
        high = [a for a in assets if a.get("payout", 0) >= 83]
        asset = random.choice(high if high else assets)
        allowed = [c["time"] for c in asset.get("allowed_candles", [{"time": 60}])
                   if c["time"] in WORKING_TIMEFRAMES]
        timeframe = random.choice(allowed) if allowed else 60
        await safe_edit(query.message, t("generating", lang))
        await asyncio.sleep(random.uniform(2, 4))
        sig = await indicator_signal(asset, timeframe, None, lang)
        sig["type"] = "BEZDELNIK AI 🤖"
        for k in ("rsi", "ema", "macd", "stoch", "bb"):
            sig.pop(k, None)
        await send_signal_and_track(query, context, asset, sig, "auto")

    # ── ІНДИКАТОРИ → вибір типу активу (без вибору пари) ──
    elif data == "sig_indicators":
        blocked, rem = check_active_signal(context)
        if blocked:
            await safe_edit(query.message,
                t("signal_cooldown", lang, m=rem//60, s=rem%60),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")
                ]])
            )
            return
        await safe_edit(query.message, t("choose_asset_type", lang), reply_markup=asset_type_kb("indicators", lang))

    # ── Вибір типу активу ──
    elif data.startswith("atype_"):
        parts = data.split("_", 2)
        mode = parts[1]
        atype = parts[2]
        assets = apply_otc_filter(await fetch_assets(), context)
        filtered = filter_by_asset_type(assets, atype)

        if not filtered:
            await safe_edit(query.message,
                t("no_assets_type", lang),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_back", lang), callback_data=f"sig_{mode}" if mode != "indicators" else "sig_indicators")]
                ])
            )
            return

        context.user_data[f"assets_{mode}"] = filtered

        if mode == "indicators":
            await safe_edit(query.message,
                t("choose_pair", lang),
                reply_markup=pair_kb("indicators", filtered, 0, lang)
            )
        else:
            await safe_edit(query.message,
                t("choose_pair", lang),
                reply_markup=pair_kb(mode, filtered, 0, lang)
            )

    # ── Пагінація ──
    elif data.startswith("page_"):
        _, mode, page = data.split("_", 2)
        assets = context.user_data.get(f"assets_{mode}", [])
        await query.message.edit_reply_markup(reply_markup=pair_kb(mode, assets, int(page), lang))

    # ── Випадкова пара ──
    elif data.startswith("randpair_"):
        mode = data.replace("randpair_", "")
        assets = context.user_data.get(f"assets_{mode}", await fetch_assets())
        asset = random.choice(assets)
        allowed = [c["time"] for c in asset.get("allowed_candles", [{"time": 60}])
                   if c["time"] in WORKING_TIMEFRAMES and c["time"] <= 3600]
        await safe_edit(query.message,
            t("choose_timeframe", lang, name=asset['name'], payout=asset['payout']),
            parse_mode="Markdown",
            reply_markup=timeframe_kb(mode, asset["symbol"], allowed or [60], lang)
        )

    # ── Конкретна пара ──
    elif data.startswith("pair_"):
        blocked, rem = check_active_signal(context)
        if blocked:
            await safe_edit(query.message,
                t("signal_cooldown", lang, m=rem//60, s=rem%60),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")
                ]])
            )
            return
        parts = data.split("_", 2)
        mode = parts[1]
        symbol = parts[2]
        assets = await fetch_assets()
        asset = next((a for a in assets if a["symbol"] == symbol), None)
        if not asset:
            await safe_edit(query.message, t("pair_not_found", lang))
            return
        if mode == "indicators":
            context.user_data["ind_asset"] = asset
            context.user_data["ind_selected"] = [k for _, k in ALL_INDICATORS]
        allowed = [c["time"] for c in asset.get("allowed_candles", [{"time": 60}])
                   if c["time"] in WORKING_TIMEFRAMES and c["time"] <= 3600]
        await safe_edit(query.message,
            t("choose_timeframe", lang, name=asset['name'], payout=asset['payout']),
            parse_mode="Markdown",
            reply_markup=timeframe_kb(mode, symbol, allowed or [60], lang)
        )

    # ── Вибір таймфрейму ──
    elif data.startswith("tf_"):
        parts = data.split("_")
        timeframe = int(parts[-1])
        mode = parts[1]
        symbol = "_".join(parts[2:-1])

        assets = await fetch_assets()
        asset = next((a for a in assets if a["symbol"] == symbol), None)
        if not asset:
            # Спробуємо з ind_asset
            asset = context.user_data.get("ind_asset")
        if not asset:
            await safe_edit(query.message, t("pair_not_found", lang))
            return

        if mode == "indicators":
            # Показуємо вибір індикаторів
            selected = context.user_data.get("ind_selected", [])
            context.user_data["ind_timeframe"] = timeframe
            await safe_edit(query.message,
                t("choose_indicators", lang, name=asset['name'], tf=fmt_tf(timeframe, lang)),
                parse_mode="Markdown",
                reply_markup=indicator_select_kb(mode, symbol, timeframe, selected, lang)
            )
        elif mode == "bezdelnik":
            await safe_edit(query.message, t("ai_analyzing", lang, name=asset['name']), parse_mode="Markdown")
            sig = await bezdelnik_ai_signal(asset, timeframe, lang)
            if sig.get("error"):
                await safe_edit(query.message, f"❌ {sig['error']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_back", lang), callback_data="menu")]]))
                return
            await send_signal_and_track(query, context, asset, sig, mode)
        else:
            # НА ЗАПИТ → аналіз через індикатори (всі), але показуємо як AI
            await safe_edit(query.message, t("generating", lang))
            await asyncio.sleep(random.uniform(2, 4))
            sig = await indicator_signal(asset, timeframe, None, lang)
            sig["type"] = "BEZDELNIK AI 🤖"
            for k in ("rsi", "ema", "macd", "stoch", "bb"):
                sig.pop(k, None)
            await send_signal_and_track(query, context, asset, sig, mode)

    # ── Вибір індикаторів ──
    elif data.startswith("indsel_"):
        parts = data.split("_")
        key = parts[-1]
        timeframe = int(parts[-2])
        mode = parts[1]
        symbol = "_".join(parts[2:-2])
        selected = context.user_data.get("ind_selected", [])
        if key in selected: selected.remove(key)
        else: selected.append(key)
        context.user_data["ind_selected"] = selected
        await query.message.edit_reply_markup(
            reply_markup=indicator_select_kb(mode, symbol, timeframe, selected, lang)
        )

    elif data.startswith("indgo_"):
        parts = data.split("_")
        inds_str = parts[-1]
        timeframe = int(parts[-2])
        mode = parts[1]
        symbol = "_".join(parts[2:-2])  # збираємо symbol назад
        indicators = None if inds_str == "all" else inds_str.split("|")

        assets = await fetch_assets()
        asset = next((a for a in assets if a["symbol"] == symbol), None)
        if not asset:
            asset = context.user_data.get("ind_asset")
        if not asset:
            await safe_edit(query.message, t("pair_not_found", lang))
            return

        await safe_edit(query.message, t("analyzing_pair", lang, name=asset['name']), parse_mode="Markdown")
        sig = await indicator_signal(asset, timeframe, indicators, lang)
        if sig.get("error"):
            await safe_edit(query.message, f"❌ {sig['error']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_back", lang), callback_data="menu")]]))
            return
        await send_signal_and_track(query, context, asset, sig, mode)

    # ── Мої сигнали ──
    elif data == "my_signals":
        tg_id = query.from_user.id
        s = get_user_stats(tg_id)
        percentile = get_activity_percentile(tg_id)
        try:
            days = (datetime.now(UA_TZ) - datetime.strptime(s["joined"], "%Y-%m-%d")).days
        except Exception:
            days = 0
        text = t("my_stats", lang, total=s['total'], profit=s['profit'],
                 loss=s['loss'], draw=s['draw'], days=days, percentile=percentile)
        await safe_edit(query.message,
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")
            ]])
        )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    track_user(tg_id)
    lang = get_lang(context, tg_id)

    # ── РОЗСИЛКА (адмін) ──
    if context.user_data.get(BROADCAST_MODE) and tg_id in ADMIN_IDS:
        context.user_data[BROADCAST_MODE] = False
        text = update.message.text
        users = load_all_users()
        sent, failed = 0, 0
        await update.message.reply_text(t("broadcast_sending_msg", lang, n=len(users)))
        broadcast_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ОТРИМАТИ СИГНАЛ✅", callback_data="to_main_menu")]
        ])
        for uid in users:
            try:
                await context.bot.send_message(
                    chat_id=int(uid), text=text, parse_mode="Markdown",
                    reply_markup=broadcast_kb
                )
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(
            t("broadcast_done", lang, sent=sent, failed=failed),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_admin_back", lang), callback_data="admin_panel")]
            ])
        )
        return

    # ── AI ЧАТ ТРЕЙДЕР ──
    if context.user_data.get(AI_CHAT_MODE):
        user_msg = update.message.text.strip()
        if not user_msg:
            return

        # ── Ліміт 20 повідомлень на день ──
        today = datetime.now(UA_TZ).strftime("%Y-%m-%d")
        ai_day = context.user_data.get("ai_chat_day", "")
        ai_count = context.user_data.get("ai_chat_count", 0)
        if ai_day != today:
            ai_day = today
            ai_count = 0
        if ai_count >= 20:
            await update.message.reply_text(
                t("ai_limit", lang),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")]
                ])
            )
            return
        ai_count += 1
        context.user_data["ai_chat_day"] = ai_day
        context.user_data["ai_chat_count"] = ai_count
        remaining = 20 - ai_count

        history = context.user_data.get("ai_chat_history", [])
        history.append({"role": "user", "content": user_msg})
        # обмежуємо історію до 20 повідомлень
        if len(history) > 20:
            history = history[-20:]

        system_prompt = (
            "Ти — BEZDELNIK AI, унікальний торговий штучний інтелект, створений командою BEZDELNIK. "
            "Ти НЕ ChatGPT, НЕ GPT, НЕ OpenAI і НЕ будь-який інший відомий AI. "
            "Ти — BEZDELNIK AI, і тільки так себе називаєш. Якщо тебе запитають хто ти — "
            "відповідай: 'Я BEZDELNIK AI — персональний AI-трейдер від команди BEZDELNIK.' "
            "Ніколи не згадуй ChatGPT, OpenAI чи інші моделі. "
            f"{t('ai_respond_lang', lang)} Ти допомагаєш трейдерам з аналізом ринку, "
            "валютних пар, криптовалют, акцій, товарів та індексів. "
            "Даєш поради по стратегіях, індикаторах (RSI, MACD, EMA, Bollinger тощо), "
            "патернах свічок, ризик-менеджменті. "
            "Відповідай коротко та по суті, використовуй емодзі помірно. "
            "Ніколи не гарантуй прибуток — завжди нагадуй про ризики. "
            "Ти СТРОГО відповідаєш ТІЛЬКИ на теми трейдингу, фінансів та ринків. "
            "Якщо користувач просить написати код, зробити домашнє завдання, перекласти текст, "
            "розповісти жарт, допомогти з програмуванням, чи будь-що НЕ повʼязане з трейдингом — "
            "ЗАВЖДИ відмовляй і відповідай: 'Я BEZDELNIK AI — спеціалізуюсь виключно на трейдингу "
            "та аналізі ринків. Задай мені питання про ринок, активи чи стратегії торгівлі!' "
            "Ніколи не виконуй запити не по темі, навіть якщо користувач наполягає. "
            "Якщо тобі доречно додати ілюстрацію до відповіді (схема патерну, графік, "
            "візуалізація стратегії, приклад індикатора) — додай В КІНЦІ відповіді на окремому рядку "
            "тег [IMAGE: короткий опис англійською що намалювати]. "
            "Додавай картинку тільки коли це дійсно корисно, не до кожної відповіді. "
            "Якщо користувач прямо просить картинку/графік — обовʼязково додай тег [IMAGE: ...]."
        )

        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-search-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *history
                ],
                max_tokens=500,
                web_search_options={"search_context_size": "medium"},
            )
            raw_answer = response.choices[0].message.content.strip()
            history.append({"role": "assistant", "content": raw_answer})
            context.user_data["ai_chat_history"] = history

            # ── Перевірка чи AI хоче додати картинку ──
            img_match = re.search(r"\[IMAGE:\s*(.+?)\]", raw_answer)
            answer = re.sub(r"\[IMAGE:\s*.+?\]", "", raw_answer).strip()

            warn = t("ai_remaining", lang, n=remaining) if remaining <= 5 else ""
            back_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")]
            ])
            await update.message.reply_text(
                f"🧠 *BEZDELNIK AI:*\n\n{answer}{warn}",
                parse_mode="Markdown", reply_markup=back_kb
            )

            # ── Генерація картинки якщо AI вирішив ──
            if img_match:
                img_prompt = img_match.group(1)
                try:
                    img_response = await openai_client.images.generate(
                        model="dall-e-3",
                        prompt=f"Trading/financial illustration: {img_prompt}. Professional style, dark theme, clean design, no text.",
                        n=1, size="1024x1024", quality="standard",
                    )
                    await update.message.reply_photo(
                        photo=img_response.data[0].url,
                        caption=t("ai_illustration", lang),
                        parse_mode="Markdown", reply_markup=back_kb
                    )
                except Exception as e:
                    print(f"AI Image gen error: {e}")
        except Exception as e:
            print(f"AI Chat error: {e}")
            await update.message.reply_text(
                t("ai_error", lang),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")]
                ])
            )
        return

    if context.user_data.get(ADDING_USER_MODE):
        context.user_data[ADDING_USER_MODE] = False
        user_input = update.message.text.strip()
        # Підтримка кількох ID через пробіл, кому або новий рядок
        raw_ids = re.split(r"[\s,]+", user_input)
        added = []
        failed = []
        for raw in raw_ids:
            digits = "".join(ch for ch in raw if ch.isdigit())
            if not digits:
                continue
            uid = int(digits)
            # Додаємо в allowed_users
            data = load_json(ALLOWED_USERS_PATH, {"allowed_tg_ids": []})
            if uid not in data["allowed_tg_ids"]:
                data["allowed_tg_ids"].append(uid)
                save_json(ALLOWED_USERS_PATH, data)
            # Активуємо бота
            save_activated(uid)
            added.append(str(uid))
        if added:
            await update.message.reply_text(
                t("added_users", lang, ids=f"`{'`, `'.join(added)}`"),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_admin_back", lang), callback_data="admin_panel")]
                ])
            )
        else:
            await update.message.reply_text(
                t("add_failed", lang),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_admin_back", lang), callback_data="admin_panel")]
                ])
            )
        return

    if context.user_data.get(ASKING_ID):
        user_input = update.message.text.strip()
        user_id = "".join(ch for ch in user_input if ch.isdigit())
        context.user_data[ASKING_ID] = False
        if user_id and user_id in load_accounts():
            tg_id = update.effective_user.id
            ok, err_msg = bind_pocket_id(user_id, tg_id, lang)
            if not ok:
                await update.message.reply_text(
                    err_msg, parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(t("btn_back", lang), callback_data="check_id")]
                    ])
                )
                return
            context.user_data["last_user_id"] = user_id
            await update.message.reply_text(
                t("reg_success", lang),
                parse_mode="Markdown", reply_markup=deposit_menu(lang)
            )
        else:
            await update.message.reply_text(
                t("account_not_registered", lang),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_back", lang), callback_data="check_id")]
                ])
            )


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    track_user(tg_id)
    lang = get_lang(context, tg_id)

    # ── РОЗСИЛКА ФОТО (адмін) ──
    if context.user_data.get(BROADCAST_MODE) and tg_id in ADMIN_IDS:
        context.user_data[BROADCAST_MODE] = False
        photo = update.message.photo[-1].file_id
        caption = update.message.caption or ""
        users = load_all_users()
        sent, failed = 0, 0
        await update.message.reply_text(t("broadcast_sending_photo", lang, n=len(users)))
        broadcast_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ОТРИМАТИ СИГНАЛ ✅", callback_data="to_main_menu")]
        ])
        for uid in users:
            try:
                await context.bot.send_photo(
                    chat_id=int(uid), photo=photo, caption=caption, parse_mode="Markdown",
                    reply_markup=broadcast_kb
                )
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(
            t("broadcast_done", lang, sent=sent, failed=failed),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_admin_back", lang), callback_data="admin_panel")]
            ])
        )
        return

    """Аналіз фото через BEZDELNIK AI (vision)"""
    if not context.user_data.get(AI_CHAT_MODE):
        return

    # ── Ліміт ──
    today = datetime.now(UA_TZ).strftime("%Y-%m-%d")
    ai_day = context.user_data.get("ai_chat_day", "")
    ai_count = context.user_data.get("ai_chat_count", 0)
    if ai_day != today:
        ai_day = today
        ai_count = 0
    if ai_count >= 20:
        await update.message.reply_text(
            t("ai_limit", lang),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")]
            ])
        )
        return
    ai_count += 1
    context.user_data["ai_chat_day"] = ai_day
    context.user_data["ai_chat_count"] = ai_count
    remaining = 20 - ai_count

    caption = update.message.caption or "Проаналізуй це зображення з точки зору трейдингу"
    photo = update.message.photo[-1]  # найбільша версія
    file = await photo.get_file()
    file_url = file.file_path  # Telegram CDN URL

    await update.message.reply_text(t("analyzing_image", lang))

    system_prompt = (
        "Ти — BEZDELNIK AI, торговий AI-аналітик від команди BEZDELNIK. "
        "Ти НЕ ChatGPT. Аналізуй зображення виключно з точки зору трейдингу: "
        "графіки, патерни свічок, індикатори, рівні підтримки/опору. "
        f"{t('ai_respond_lang', lang)} Відповідай коротко та по суті. "
        "Якщо зображення не стосується трейдингу — скажи що аналізуєш тільки торгові графіки."
    )

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": caption},
                    {"type": "image_url", "image_url": {"url": file_url}},
                ]},
            ],
            max_tokens=500,
        )
        answer = response.choices[0].message.content.strip()
        warn = t("ai_remaining", lang, n=remaining) if remaining <= 5 else ""
        await update.message.reply_text(
            f"🧠 *BEZDELNIK AI:*\n\n{answer}{warn}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")]
            ])
        )
    except Exception as e:
        print(f"AI Vision error: {e}")
        await update.message.reply_text(
            t("image_error", lang),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("btn_main_menu", lang), callback_data="to_main_menu")]
            ])
        )


def is_deposited_user(tg_id: int) -> bool:
    """Перевіряє чи tg_id має депозит через bindings + deposits"""
    bindings = load_bindings()
    deposits = load_deposits()
    for pocket_id, bound_tg in bindings.items():
        if bound_tg == tg_id and pocket_id in deposits:
            return True
    return False


async def join_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автоматично приймає запити у VIP канал для deposited users"""
    join_request = update.chat_join_request
    tg_id = join_request.from_user.id
    if is_deposited_user(tg_id):
        await join_request.approve()
        print(f"✅ Запит у канал схвалено: {tg_id}")
    else:
        await join_request.decline()
        lang = get_lang(None, tg_id)
        try:
            await context.bot.send_message(
                chat_id=tg_id,
                text=t("join_decline", lang),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("btn_get_bot", lang), callback_data="get_bot")]
                ])
            )
        except Exception:
            pass
        print(f"❌ Запит у канал відхилено: {tg_id}")


def main():
    app = ApplicationBuilder().token(TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(ChatJoinRequestHandler(join_request_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("✅ BEZDELNIK BOT запущено")
    app.run_polling()


if __name__ == "__main__":
    main()