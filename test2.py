import json
import os
import random
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
import pandas as pd
import ta
from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

# ─── КОНФІГ ────────────────────────────────────────────────────
TOKEN = "8578407218:AAGE5kM5El_nw0j8O83ErH4VJgMvxbm7rBc"
SSID = '42["auth",{"session":"0dc1s5l5704vapvmm8oh57nmtm","isDemo":1,"uid":125727409,"platform":1,"isFastHistory":true,"isOptimized":true}]'
REF_LINK_BASE = "https://u3.shortink.io/register?utm_campaign=793458&utm_source=affiliate&utm_medium=sr&a=zk5yIcrmNGT0Jb&ac=pocketbrocker&code=BEZ100"

JSON_PATH = "registered_accounts.json"
ACTIVATED_PATH = "activated_accounts.json"
DEPOSIT_PATH = "deposited_accounts.json"

ASKING_ID = "asking_id"
CHAT_GPT_MODE = "chat_gpt_mode"

# Кеш пар щоб не підключатись кожен раз
_cached_assets = []


# ─── ПАРИ ──────────────────────────────────────────────────────
async def fetch_assets() -> list:
    """Отримати всі активні пари з PocketOption без кешу"""
    try:
        async with PocketOptionAsync(SSID) as api:
            assets = await api.active_assets()
            return [a for a in assets if a.get("is_active")]
    except Exception as e:
        print(f"Помилка отримання пар: {e}")
        return []


def filter_assets(assets: list, mode: str) -> list:
    """Фільтр пар: otc / regular / all"""
    if mode == "otc":
        return [a for a in assets if a.get("is_otc")]
    elif mode == "regular":
        return [a for a in assets if not a.get("is_otc")]
    return assets


def get_user_mode(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Отримати поточний режим пар юзера (otc/regular/all)"""
    return context.user_data.get("pair_mode", "all")


# ─── JSON ХЕЛПЕРИ ──────────────────────────────────────────────
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def load_accounts(): return load_json(JSON_PATH, [])
def load_activated(): return load_json(ACTIVATED_PATH, [])
def load_deposits(): return load_json(DEPOSIT_PATH, {})

def random_signal_with_tf(asset: dict, timeframe: int) -> dict:
    return {
        "name": asset["name"],
        "symbol": asset["symbol"],
        "direction": random.choice(["🟢 BUY", "🔴 SELL"]),
        "timeframe": timeframe,
        "confidence": random.randint(60, 95),
        "payout": asset.get("payout", "?"),
        "type": "Рандомний",
        "is_otc": asset.get("is_otc", False),
    }

async def indicator_signal_with_tf(asset: dict, timeframe: int) -> dict:
    symbol = asset["symbol"]
    try:
        async with PocketOptionAsync(SSID) as api:
            if timeframe <= 60:
                count = 5000
            elif timeframe <= 300:
                count = 10000
            elif timeframe <= 900:
                count = 30000
            else:
                count = 100000
            candles = await api.get_candles(symbol, timeframe, count)
            
        async with PocketOptionAsync(SSID) as api:
            # Отримуємо свічки
            candles = await api.get_candles(symbol, timeframe, count)
            
            # Отримуємо актуальну ціну
            current_price = None
            try:
                stream = await api.subscribe_symbol(symbol)
                async for tick in stream:
                    current_price = tick.get("close")
                    break
            except Exception:
                pass

        if len(candles) < 14:
            raise ValueError("Мало даних")

        df = pd.DataFrame(candles)
        df["close"] = df["close"].astype(float)

        rsi = ta.momentum.RSIIndicator(df["close"], window=min(14, len(df)-1)).rsi().iloc[-1]
        ema_fast = ta.trend.EMAIndicator(df["close"], window=min(9, len(df)-1)).ema_indicator().iloc[-1]
        ema_slow = ta.trend.EMAIndicator(df["close"], window=min(21, len(df)-1)).ema_indicator().iloc[-1]
        macd = ta.trend.MACD(df["close"])
        macd_line = macd.macd().iloc[-1]
        macd_signal = macd.macd_signal().iloc[-1]

        buy_score = 0
        sell_score = 0

        if rsi < 30:   buy_score += 2
        elif rsi < 45: buy_score += 1
        elif rsi > 70: sell_score += 2
        elif rsi > 55: sell_score += 1

        if ema_fast > ema_slow: buy_score += 1
        else: sell_score += 1

        if macd_line > macd_signal: buy_score += 1
        else: sell_score += 1

        if buy_score > sell_score:
            direction = "🟢 BUY"
            confidence = min(95, 55 + buy_score * 10)
        elif sell_score > buy_score:
            direction = "🔴 SELL"
            confidence = min(95, 55 + sell_score * 10)
        else:
            direction = random.choice(["🟢 BUY", "🔴 SELL"])
            confidence = 60

        return {
            "name": asset["name"],
            "symbol": symbol,
            "direction": direction,
            "timeframe": timeframe,
            "confidence": confidence,
            "payout": asset.get("payout", "?"),
            "type": "Індикатори",
            "is_otc": asset.get("is_otc", False),
            "rsi": round(rsi, 1),
            "current_price": current_price,
            "ema": "Бичача ↑" if ema_fast > ema_slow else "Медвежа ↓",
            "macd": "Бичачий ↑" if macd_line > macd_signal else "Медвежий ↓",
        }

    except Exception as e:
        print(f"Indicator error for {symbol}: {e}")
        sig = random_signal_with_tf(asset, timeframe)
        sig["type"] = "Рандомний (немає даних)"
        return sig


def save_activated(user_id: int):
    activated = load_activated()
    if user_id not in activated:
        activated.append(user_id)
        with open(ACTIVATED_PATH, "w", encoding="utf-8") as f:
            json.dump(activated, f, indent=2)


# ─── СИГНАЛИ ───────────────────────────────────────────────────
def random_signal(asset: dict) -> dict:
    timeframe = random.choice(asset.get("allowed_candles", [{"time": 60}]))["time"]
    return {
        "name": asset["name"],
        "symbol": asset["symbol"],
        "direction": random.choice(["🟢 BUY", "🔴 SELL"]),
        "timeframe": timeframe,
        "confidence": random.randint(60, 95),
        "payout": asset.get("payout", "?"),
        "type": "Рандомний",
        "is_otc": asset.get("is_otc", False),
    }


async def indicator_signal(asset: dict) -> dict:
    symbol = asset["symbol"]
    # Пробуємо від найменшого таймфрейму
    try_timeframes = [5, 10, 15, 30, 60, 120, 300]

    try:
        candles = []
        used_timeframe = 60

        async with PocketOptionAsync(SSID) as api:
            for tf in [60, 120, 300]:
                candles = await api.get_candles(symbol, tf, 5000)
                if len(candles) >= 30:
                    used_timeframe = tf
                    break

        if len(candles) < 14:
            raise ValueError("Мало даних")

        df = pd.DataFrame(candles)
        df["close"] = df["close"].astype(float)

        rsi = ta.momentum.RSIIndicator(df["close"], window=min(14, len(df)-1)).rsi().iloc[-1]
        ema_fast = ta.trend.EMAIndicator(df["close"], window=min(9, len(df)-1)).ema_indicator().iloc[-1]
        ema_slow = ta.trend.EMAIndicator(df["close"], window=min(21, len(df)-1)).ema_indicator().iloc[-1]
        macd = ta.trend.MACD(df["close"])
        macd_line = macd.macd().iloc[-1]
        macd_signal = macd.macd_signal().iloc[-1]

        buy_score = 0
        sell_score = 0

        if rsi < 30:   buy_score += 2
        elif rsi < 45: buy_score += 1
        elif rsi > 70: sell_score += 2
        elif rsi > 55: sell_score += 1

        if ema_fast > ema_slow: buy_score += 1
        else: sell_score += 1

        if macd_line > macd_signal: buy_score += 1
        else: sell_score += 1

        if buy_score > sell_score:
            direction = "🟢 BUY"
            confidence = min(95, 55 + buy_score * 10)
        elif sell_score > buy_score:
            direction = "🔴 SELL"
            confidence = min(95, 55 + sell_score * 10)
        else:
            direction = random.choice(["🟢 BUY", "🔴 SELL"])
            confidence = 60

        return {
            "name": asset["name"],
            "symbol": symbol,
            "direction": direction,
            "timeframe": used_timeframe,
            "confidence": confidence,
            "payout": asset.get("payout", "?"),
            "type": "Індикатори",
            "is_otc": asset.get("is_otc", False),
            "rsi": round(rsi, 1),
            "ema": "Бичача ↑" if ema_fast > ema_slow else "Медвежа ↓",
            "macd": "Бичачий ↑" if macd_line > macd_signal else "Медвежий ↓",
        }

    except Exception as e:
        print(f"Indicator error for {symbol}: {e}")
        sig = random_signal(asset)
        sig["type"] = "Рандомний (немає даних)"
        return sig
    

def format_timeframe(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        return f"{seconds // 60} хв"
    else:
        return f"{seconds // 3600} год"


def format_signal(sig: dict) -> str:
    pair_type = "OTC 🔄" if sig.get("is_otc") else "Regular 📈"
    
    text = (
        f"📊 *СИГНАЛ*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💱 *{sig['name']}* (`{sig['symbol']}`)\n"
        f"🏷 Тип:           `{pair_type}`\n"
        f"📈 Напрямок:   *{sig['direction']}*\n"
        f"⏱ Таймфрейм: `{format_timeframe(sig['timeframe'])}`\n"
        f"💯 Впевненість:`{sig['confidence']}%`\n"
        f"💰 Виплата:     `{sig['payout']}%`\n"
        f"🤖 Метод:        `{sig['type']}`\n"
    )
    if sig.get("current_price"):
        text += f"💲 Ціна:          `{sig['current_price']}`\n"
    if "rsi" in sig:
        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📉 RSI:    `{sig['rsi']}`\n"
            f"📊 EMA:   `{sig['ema']}`\n"
            f"📈 MACD:  `{sig['macd']}`\n"
        )
    text += f"━━━━━━━━━━━━━━━━━━━━\n🕐 {datetime.now().strftime('%H:%M:%S')}"
    return text


# ─── МЕНЮ ──────────────────────────────────────────────────────
def main_menu(mode: str = "all") -> InlineKeyboardMarkup:
    mode_labels = {"all": "🌐 Всі пари", "otc": "🔄 OTC пари", "regular": "📈 Звичайні"}
    mode_label = mode_labels.get(mode, "🌐 Всі пари")
    next_mode = {"all": "otc", "otc": "regular", "regular": "all"}[mode]

    keyboard = [
        [InlineKeyboardButton(f"Режим пар: {mode_label} →", callback_data=f"switch_mode_{next_mode}")],
        [InlineKeyboardButton("🎲 РАНДОМНИЙ СИГНАЛ", callback_data="sig_random")],
        [InlineKeyboardButton("📊 СИГНАЛ ПО ІНДИКАТОРАХ", callback_data="sig_indicators")],
        [InlineKeyboardButton("🧠 ChatGPT", callback_data="chat_gpt")],
        [InlineKeyboardButton("📋 МОЇ СИГНАЛИ", callback_data="signals")],
        [InlineKeyboardButton("⚙️ НАЛАШТУВАННЯ", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


def pair_select_menu(signal_mode: str, assets: list, page: int = 0) -> InlineKeyboardMarkup:
    """Меню вибору конкретної пари (по 8 штук з пагінацією)"""
    per_page = 8
    total = len(assets)
    start = page * per_page
    end = min(start + per_page, total)
    page_assets = assets[start:end]

    keyboard = []
    for asset in page_assets:
        label = f"{'🔄' if asset['is_otc'] else '📈'} {asset['name']} ({asset['payout']}%)"
        callback = f"pair_{signal_mode}_{asset['symbol']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    # Навігація
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"page_{signal_mode}_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{(total-1)//per_page+1}", callback_data="noop"))
    if end < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"page_{signal_mode}_{page+1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("🎲 Рандомна пара", callback_data=f"random_{signal_mode}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="to_main_menu")])
    return InlineKeyboardMarkup(keyboard)


def after_signal_menu(signal_mode: str, symbol: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔁 Ще сигнал для цієї пари", callback_data=f"pair_{signal_mode}_{symbol}")],
        [InlineKeyboardButton("📋 Інша пара", callback_data=f"sig_{signal_mode}")],
        [InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def settings_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🌐 МОВА", callback_data="language")],
        [InlineKeyboardButton("🔔 СПОВІЩЕННЯ", callback_data="notifications")],
        [InlineKeyboardButton("⬅️ Вийти в меню", callback_data="to_main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def bot_activate_check_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔘 АКТИВУВАТИ БОТА", callback_data="activate_bot")]])

def deposit_check_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔘 ПЕРЕВІРИТИ ДЕПОЗИТ", callback_data="check_deposit")]])

def chat_gpt_exit_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Вийти в меню", callback_data="exit_chat_gpt")]])


# ─── ХЕНДЛЕРИ ──────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if tg_id in load_activated():
        mode = get_user_mode(context)
        await update.message.reply_text("✅ Бот активований\n\nГоловне меню:", reply_markup=main_menu(mode))
        return

    keyboard = [[
        InlineKeyboardButton("🔘 РЕЄСТРАЦІЯ", url=REF_LINK_BASE),
        InlineKeyboardButton("🔘 ПЕРЕВІРИТИ ID", callback_data="check_id"),
    ]]
    await update.message.reply_photo(
        photo="https://picsum.photos/600/400",
        caption="👋 *Вітаю!*\n\nНатисни *РЕЄСТРАЦІЯ* і зареєструйся.\nПісля цього натисни *ПЕРЕВІРИТИ ID* ✅",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    mode = get_user_mode(context)

    # ── Головне меню ──
    if data == "to_main_menu":
        await query.message.reply_text("Головне меню:", reply_markup=main_menu(mode))

    elif data == "noop":
        pass

    # ── Перемикач режиму пар ──
    elif data.startswith("switch_mode_"):
        new_mode = data.replace("switch_mode_", "")
        context.user_data["pair_mode"] = new_mode
        mode_names = {"all": "Всі пари 🌐", "otc": "OTC пари 🔄", "regular": "Звичайні 📈"}
        await query.message.reply_text(
            f"✅ Режим змінено: *{mode_names[new_mode]}*",
            parse_mode="Markdown",
            reply_markup=main_menu(new_mode)
        )

    # ── Реєстрація ──
    elif data == "check_id":
        context.user_data[ASKING_ID] = True
        await query.message.reply_text("Введи свій Pocket Option ID:")

    elif data == "check_deposit":
        user_id = context.user_data.get("last_user_id")
        if not user_id:
            await query.message.reply_text("Спочатку введи свій ID.")
            return
        deposits = load_deposits()
        if user_id in deposits:
            await query.message.reply_photo(
                photo="https://picsum.photos/600/400",
                caption=f"🎉 Депозит підтверджено ✅\nСума: {deposits[user_id]}",
                parse_mode="Markdown",
                reply_markup=bot_activate_check_menu()
            )
        else:
            await query.message.reply_text("❌ Депозиту ще не зафіксовано")

    elif data == "activate_bot":
        save_activated(query.from_user.id)
        await query.message.reply_text("🎉 Бот активовано!\n\nГоловне меню:", reply_markup=main_menu(mode))

    # ── Вибір типу сигналу → список пар ──
    elif data in ("sig_random", "sig_indicators"):
        signal_mode = data.replace("sig_", "")
        assets = await fetch_assets()
        filtered = filter_assets(assets, mode)

        if not filtered:
            await query.message.reply_text("⚠️ Немає доступних пар")
            return

        context.user_data[f"assets_{signal_mode}"] = filtered
        context.user_data[f"page_{signal_mode}"] = 0

        mode_label = {"random": "Рандомний 🎲", "indicators": "По індикаторах 📊"}[signal_mode]
        await query.message.reply_text(
            f"*{mode_label}*\n\nОберіть пару або натисніть «Рандомна»:",
            parse_mode="Markdown",
            reply_markup=pair_select_menu(signal_mode, filtered, 0)
        )

    # ── Пагінація ──
    elif data.startswith("page_"):
        _, signal_mode, page = data.split("_", 2)
        page = int(page)
        assets = context.user_data.get(f"assets_{signal_mode}", [])
        context.user_data[f"page_{signal_mode}"] = page
        await query.message.edit_reply_markup(
            reply_markup=pair_select_menu(signal_mode, assets, page)
        )

    # ── Рандомна пара ──
    elif data.startswith("random_"):
        signal_mode = data.replace("random_", "")
        assets = context.user_data.get(f"assets_{signal_mode}", [])
        if not assets:
            assets = filter_assets(await fetch_assets(), mode)

        asset = random.choice(assets)
        await _send_signal(query, context, signal_mode, asset)

    # ── Конкретна пара ──
    elif data.startswith("pair_"):
        parts = data.split("_", 2)
        signal_mode = parts[1]
        symbol = parts[2]
        assets = await fetch_assets()
        asset = next((a for a in assets if a["symbol"] == symbol), None)
        if not asset:
            await query.message.reply_text("❌ Пару не знайдено")
            return
        await _send_signal(query, context, signal_mode, asset)
        
    elif data.startswith("tf_"):
        # tf_{signal_mode}_{symbol}_{timeframe}
        # Беремо останній елемент як timeframe, все між першим і останнім як symbol
        parts = data.split("_")
        timeframe = int(parts[-1])
        signal_mode = parts[1]
        symbol = "_".join(parts[2:-1])  # збираємо symbol назад
        
        assets = await fetch_assets()
        asset = next((a for a in assets if a["symbol"] == symbol), None)
        if not asset:
            await query.message.reply_text("❌ Пару не знайдено")
            return
        
        if signal_mode == "indicators":
            await query.message.reply_text(f"⏳ Аналізую *{asset['name']}*...", parse_mode="Markdown")
            sig = await indicator_signal_with_tf(asset, timeframe)
        else:
            sig = random_signal_with_tf(asset, timeframe)
        
        await query.message.reply_text(
            format_signal(sig),
            parse_mode="Markdown",
            reply_markup=after_signal_menu(signal_mode, symbol)
        )

    # ── ChatGPT ──
    elif data == "chat_gpt":
        context.user_data[CHAT_GPT_MODE] = True
        context.user_data["chat_history"] = []
        await query.message.reply_text(
            "🧠 ChatGPT режим\n\nПишіть питання 👇",
            reply_markup=chat_gpt_exit_menu()
        )

    elif data == "exit_chat_gpt":
        context.user_data[CHAT_GPT_MODE] = False
        await query.message.reply_text("Головне меню:", reply_markup=main_menu(mode))

    # ── Налаштування ──
    elif data == "settings":
        await query.message.reply_text("⚙️ Налаштування:", reply_markup=settings_menu())


async def _send_signal(query, context, signal_mode: str, asset: dict):
    WORKING_TIMEFRAMES = [60, 120, 180, 300, 600, 900, 1800, 3600]
    allowed = [c["time"] for c in asset.get("allowed_candles", [{"time": 60}])]
    allowed = [tf for tf in allowed if tf in WORKING_TIMEFRAMES]
    
    # Фільтруємо тільки до 1 години (3600 сек)
    allowed = [tf for tf in allowed if tf <= 3600]
    
    context.user_data["pending_asset"] = asset
    context.user_data["pending_mode"] = signal_mode
    
    keyboard = []
    for tf in allowed:
        label = format_timeframe(tf)
        keyboard.append([InlineKeyboardButton(
            f"⏱ {label}", 
            callback_data=f"tf_{signal_mode}_{asset['symbol']}_{tf}"
        )])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"sig_{signal_mode}")])
    
    await query.message.reply_text(
        f"📊 *{asset['name']}*\n\nОберіть таймфрейм:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = get_user_mode(context)

    # ChatGPT режим
    if context.user_data.get(CHAT_GPT_MODE):
        user_text = update.message.text
        history = context.user_data.get("chat_history", [])
        history.append({"role": "user", "content": user_text})
        # Підключи свій OpenAI клієнт тут
        answer = "ChatGPT відповідь (підключи OpenAI клієнт)"
        history.append({"role": "assistant", "content": answer})
        context.user_data["chat_history"] = history[-10:]
        await update.message.reply_text(answer, reply_markup=chat_gpt_exit_menu())
        return

    # Перевірка ID
    if context.user_data.get(ASKING_ID):
        user_input = update.message.text.strip()
        user_id = "".join(ch for ch in user_input if ch.isdigit())
        context.user_data[ASKING_ID] = False

        if user_id and user_id in load_accounts():
            context.user_data["last_user_id"] = user_id
            await update.message.reply_photo(
                photo="https://picsum.photos/600/400",
                caption="🎉 Акаунт знайдено ✅\nПеревір депозит:",
                parse_mode="Markdown",
                reply_markup=deposit_check_menu()
            )
        else:
            await update.message.reply_text("❌ Акаунт не зареєстрований через посилання")


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("✅ Бот запущено")
    app.run_polling()


if __name__ == "__main__":
    main()