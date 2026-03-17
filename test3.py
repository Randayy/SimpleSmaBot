import json
import os
import re
import random
import asyncio
from datetime import datetime, timedelta
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

ADMIN_IDS = [452052752,8337970493,6704855261]
ALLOWED_USERS_PATH = "allowed_users_bezdelnik.json"

ASKING_ID = "asking_id"
BROADCAST_MODE = "broadcast_mode"
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_bindings(): return load_json(BINDINGS_PATH, {})

def bind_pocket_id(pocket_id: str, tg_id: int) -> tuple[bool, str]:
    """Прив'язує pocket_id до tg_id. Повертає (успіх, повідомлення)"""
    bindings = load_bindings()
    # Перевіряємо чи цей pocket_id вже прив'язаний
    if pocket_id in bindings:
        if bindings[pocket_id] == tg_id:
            return True, ""  # Вже прив'язаний до цього юзера — ок
        return False, "❌ Цей ID вже прив'язаний до іншого акаунту Telegram"
    # Перевіряємо чи цей tg_id вже має прив'язку
    for pid, tid in bindings.items():
        if tid == tg_id:
            return False, f"❌ Твій Telegram вже прив'язаний до ID `{pid}`"
    # Все ок — прив'язуємо
    bindings[pocket_id] = tg_id
    save_json(BINDINGS_PATH, bindings)
    return True, ""

def load_accounts(): return load_json(JSON_PATH, [])
def load_activated(): return load_json(ACTIVATED_PATH, [])
def load_deposits(): return load_json(DEPOSIT_PATH, {})
def load_stats(): return load_json(STATS_PATH, {})
def load_all_users(): return load_json(USERS_PATH, {})

def track_user(tg_id: int):
    """Зберігає tg_id + дату останньої взаємодії"""
    users = load_all_users()
    users[str(tg_id)] = datetime.now().isoformat()
    save_json(USERS_PATH, users)

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
                      "joined": datetime.now().strftime("%Y-%m-%d")}
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
                      "joined": datetime.now().strftime("%Y-%m-%d")}
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
        try:
            async with PocketOptionAsync(SSID) as api:
                assets = await api.active_assets()
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

def get_otc_enabled(context) -> bool:
    return context.user_data.get("otc_enabled", True)

def apply_otc_filter(assets: list, context) -> list:
    if get_otc_enabled(context):
        return [a for a in assets if a.get("is_otc")]
    return [a for a in assets if not a.get("is_otc")]


# ─── ЦІНА ──────────────────────────────────────────────────────
async def get_current_price(symbol: str) -> float | None:
    try:
        async with PocketOptionAsync(SSID) as api:
            stream = await api.subscribe_symbol(symbol)
            async for tick in stream:
                val = tick.get("close")
                if val:
                    return float(val)
                break
    except Exception as e:
        print(f"Price error for {symbol}: {e}")
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


async def indicator_signal(asset: dict, timeframe: int, selected_indicators: list | None = None) -> dict:
    symbol = asset["symbol"]
    try:
        if timeframe <= 60:      count = 5000
        elif timeframe <= 300:   count = 10000
        elif timeframe <= 900:   count = 30000
        else:                    count = 100000

        async with PocketOptionAsync(SSID) as api:
            try:
                candles = await api.get_candles(symbol, timeframe, count)
            except Exception as ce:
                print(f"get_candles error {symbol}: {ce}")
                return {"error": f"Помилка отримання даних для {asset['name']}"}
            current_price = None
            try:
                stream = await api.subscribe_symbol(symbol)
                async for tick in stream:
                    val = tick.get("close")
                    if val:
                        current_price = float(val)
                    break
            except Exception as pe:
                print(f"Price error {symbol}: {pe}")

        if not candles or len(candles) < 14:
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
            result["ema"] = "Бичача ↑" if ef > es else "Медвежа ↓"
            if ef > es: buy_score += 1
            else:       sell_score += 1

        if "macd" in use:
            m = ta.trend.MACD(df["close"])
            ml = m.macd().iloc[-1]
            ms = m.macd_signal().iloc[-1]
            result["macd"] = "Бичачий ↑" if ml > ms else "Медвежий ↓"
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
            if c <= bbl:   buy_score += 1; result["bb"] = "Нижня межа 📉"
            elif c >= bbh: sell_score += 1; result["bb"] = "Верхня межа 📈"
            else:          result["bb"] = "Середина ➡️"

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


async def bezdelnik_ai_signal(asset: dict, timeframe: int) -> dict:
    """Отримує дані і передає в GPT для аналізу"""
    symbol = asset["symbol"]
    try:
        if timeframe <= 60:      count = 5000
        elif timeframe <= 300:   count = 10000
        else:                    count = 30000

        async with PocketOptionAsync(SSID) as api:
            try:
                candles = await api.get_candles(symbol, timeframe, count)
            except Exception as ce:
                print(f"get_candles error {symbol}: {ce}")
                return {"error": f"Помилка отримання даних для {asset['name']}"}
            current_price = None
            try:
                stream = await api.subscribe_symbol(symbol)
                async for tick in stream:
                    val = tick.get("close")
                    if val:
                        current_price = float(val)
                    break
            except Exception:
                pass

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
{{"direction": "BUY або SELL", "confidence": число від 60 до 95, "reason": "коротке пояснення до 100 символів"}}"""

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
            "ema": "Бичача ↑" if ef > es else "Медвежа ↓",
            "macd": "Бичачий ↑" if ml > ms else "Медвежий ↓",
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
    await asyncio.sleep(min(timeframe, 300))  # макс 5 хв
    try:
        exit_price = await get_current_price(symbol)
        context.user_data["active_signal"] = None

        if not exit_price or not entry_price:
            return

        price_up = exit_price > entry_price
        result = "profit" if ("BUY" in direction and price_up) or ("SELL" in direction and not price_up) else "loss"

        diff = round(abs(exit_price - entry_price), 5)
        emoji = "✅" if result == "profit" else "❌"
        label = "ПРОФІТ" if result == "profit" else "ЗБИТОК"

        update_user_stats(tg_id, result)

        text = (
            f"{emoji} *{label}*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💱 `{symbol}`\n"
            f"📈 Напрямок: *{direction}*\n"
            f"💲 Ціна входу:   `{fmt_price(entry_price)}`\n"
            f"💲 Ціна виходу:  `{fmt_price(exit_price)}`\n"
            f"📊 Різниця: `{fmt_price(diff)}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        img_path = "imgs/start_imgs/плюс.png" if result == "profit" else "imgs/start_imgs/мінус.png"
        try:
            await context.bot.send_photo(
                chat_id=tg_id, photo=open(img_path, "rb"),
                caption=text, parse_mode="Markdown",
                reply_markup=main_menu_kb(True, tg_id)
            )
        except Exception:
            await context.bot.send_message(
                chat_id=tg_id, text=text, parse_mode="Markdown",
                reply_markup=main_menu_kb(True, tg_id)
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


def fmt_tf(seconds: int) -> str:
    if seconds < 60:    return f"{seconds} сек"
    elif seconds < 3600: return f"{seconds // 60} хв"
    else:               return f"{seconds // 3600} год"

def format_signal(sig: dict) -> str:
    pair_type = "OTC 🔄" if sig.get("is_otc") else "Official 📈"
    text = (
        f"📊 *СИГНАЛ BEZDELNIK*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💱 *{sig['name']}* (`{sig['symbol']}`)\n"
        f"🏷 Тип:            `{pair_type}`\n"
        f"📈 Напрямок:    *{sig['direction']}*\n"
        f"⏱ Таймфрейм:  `{fmt_tf(sig['timeframe'])}`\n"
        f"💯 Впевненість: `{sig['confidence']}%`\n"
        f"💰 Виплата:      `{sig['payout']}%`\n"
        f"🤖 Метод:         `{sig['type']}`\n"
    )
    if sig.get("current_price"):
        text += f"💲 Ціна входу:    `{fmt_price(sig['current_price'])}`\n"
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
    text += f"━━━━━━━━━━━━━━━━━━━\n🕐 {datetime.now().strftime('%H:%M:%S')}"
    return text


# ─── КЛАВІАТУРИ ────────────────────────────────────────────────
def main_menu_kb(otc: bool, tg_id: int = 0) -> InlineKeyboardMarkup:
    otc_label = "OTC ✅ АКТИВОВАНО" if otc else "OTC ❌ НЕ АКТИВОВАНО"
    rows = [
        [InlineKeyboardButton(otc_label, callback_data="toggle_otc")],
        [
            InlineKeyboardButton("📲 НА ЗАПИТ", callback_data="sig_request"),
            InlineKeyboardButton("⚡ АВТО ШІ", callback_data="sig_auto"),
        ],
        [
            InlineKeyboardButton("📊 ІНДИКАТОРИ", callback_data="sig_indicators"),
            InlineKeyboardButton("🧠 BEZDELNIK AI", callback_data="ai_chat_start"),
        ],
        [InlineKeyboardButton("📋 МОЇ СИГНАЛИ", callback_data="my_signals")],
        [InlineKeyboardButton("💬 ДОПОМОГА", url="https://t.me/NazarUkrain")],
    ]
    if tg_id in ADMIN_IDS:
        rows.append([InlineKeyboardButton("⚙️ АДМІН ПАНЕЛЬ", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def main_menu(context, tg_id: int = 0) -> InlineKeyboardMarkup:
    return main_menu_kb(get_otc_enabled(context), tg_id)

def asset_type_kb(mode: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for label, key in ASSET_TYPES:
        row.append(InlineKeyboardButton(label, callback_data=f"atype_{mode}_{key}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="to_main_menu")])
    return InlineKeyboardMarkup(rows)

def pair_kb(mode: str, assets: list, page: int = 0) -> InlineKeyboardMarkup:
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
        InlineKeyboardButton("🎲 Випадкова пара", callback_data=f"randpair_{mode}"),
        InlineKeyboardButton("⬅️ Назад", callback_data=f"sig_{mode}"),
    ])
    return InlineKeyboardMarkup(rows)

def timeframe_kb(mode: str, symbol: str, allowed: list) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for tf in allowed:
        row.append(InlineKeyboardButton(fmt_tf(tf), callback_data=f"tf_{mode}_{symbol}_{tf}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"sig_{mode}")])
    return InlineKeyboardMarkup(rows)

def indicator_select_kb(mode: str, symbol: str, timeframe: int, selected: list) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for name, key in ALL_INDICATORS:
        check = "✅" if key in selected else "◻️"
        row.append(InlineKeyboardButton(f"{check} {name}", callback_data=f"indsel_{mode}_{symbol}_{timeframe}_{key}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    inds = "|".join(selected) if selected else "all"
    rows.append([InlineKeyboardButton("🚀 Отримати сигнал", callback_data=f"indgo_{mode}_{symbol}_{timeframe}_{inds}")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"sig_{mode}")])
    return InlineKeyboardMarkup(rows)

# Таймфрейм меню для ІНДИКАТОРІВ (без вибору пари — рандомна пара)
def tf_only_kb(mode: str, symbol: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for tf in WORKING_TIMEFRAMES:
        row.append(InlineKeyboardButton(fmt_tf(tf), callback_data=f"tf_{mode}_{symbol}_{tf}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="to_main_menu")])
    return InlineKeyboardMarkup(rows)

def after_signal_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")]])

def bot_activate_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔘 АКТИВУВАТИ БОТА", callback_data="activate_bot")]])

def deposit_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔘 ПЕРЕВІРИТИ ДЕПОЗИТ", callback_data="check_deposit")]])


# ─── ХЕНДЛЕРИ ──────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    track_user(tg_id)
    # Автоактивація для allowed users
    if tg_id in load_allowed_users():
        save_activated(tg_id)
    if tg_id in load_activated():
        await update.message.reply_text(
            "✅ Бот активований\n\n*BEZDELNIK BOT* — Головне меню:",
            parse_mode="Markdown", reply_markup=main_menu(context, tg_id)
        )
        return
    # Фото
    await update.message.reply_photo(
        photo=open("imgs/start_imgs/start.png", "rb"),
    )
    # Основне повідомлення
    await update.message.reply_text(
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
        "Крім самого бота, ти також отримуєш доступ до всього закритого контенту від BEZDELNIK!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 ОТРИМАТИ РОБОТА", callback_data="get_bot")],
            [
                InlineKeyboardButton("💬 ДОПОМОГА", url="https://t.me/NazarUkrain"),
                InlineKeyboardButton("⭐ ВІДГУКИ", url="https://t.me/+Hw8LxioNOIJiN2Qy"),
            ],
            [InlineKeyboardButton("📢 КАНАЛ", url="https://t.me/+6ejF11uYS6c3MzFi")],
        ])
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
    await message.chat.send_photo(photo=open(photo_path, "rb"), caption=caption, **kwargs)


def check_active_signal(context) -> tuple[bool, int]:
    """Повертає (заблоковано, секунд залишилось)"""
    active = context.user_data.get("active_signal")
    if not active:
        return False, 0
    end_time = active.get("end_time")
    if end_time and datetime.now() < end_time:
        remaining = int((end_time - datetime.now()).total_seconds())
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

    timeout = min(timeframe, 300)  # макс 5 хв
    context.user_data["active_signal"] = {
        "symbol": symbol, "direction": sig["direction"],
        "entry_price": entry_price,
        "end_time": datetime.now() + timedelta(seconds=timeout)
    }

    # Видаляємо повідомлення "Генерую сигнал..."
    try:
        await query.message.delete()
    except Exception:
        pass

    # Фото пари + напрямок
    chat_id = query.message.chat_id
    img_path = find_signal_image(asset, sig["direction"])
    if img_path:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=open(img_path, "rb"),
            caption=format_signal(sig),
            parse_mode="Markdown",
            reply_markup=after_signal_kb()
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=format_signal(sig), parse_mode="Markdown", reply_markup=after_signal_kb()
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

    # ── Головне меню ──
    if data == "to_main_menu":
        context.user_data[AI_CHAT_MODE] = False
        await safe_edit(query.message,
            "🏠 *BEZDELNIK BOT* — Головне меню:",
            parse_mode="Markdown", reply_markup=main_menu(context, query.from_user.id)
        )

    elif data == "to_start":
        context.user_data[AI_CHAT_MODE] = False
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.chat.send_photo(
            photo=open("imgs/start_imgs/start.png", "rb"),
            caption=(
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
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🤖 ОТРИМАТИ РОБОТА", callback_data="get_bot")],
                [
                    InlineKeyboardButton("💬 ДОПОМОГА", url="https://t.me/NazarUkrain"),
                    InlineKeyboardButton("⭐ ВІДГУКИ", url="https://t.me/+Hw8LxioNOIJiN2Qy"),
                ],
                [InlineKeyboardButton("📢 КАНАЛ", url="https://t.me/+6ejF11uYS6c3MzFi")],
            ])
        )

    # ── Стартові кнопки ──
    elif data == "get_bot":
        await safe_edit(query.message,
            "Отже, розберемо по кроках. Для того щоб активувати торгового бота "
            "та отримати доступ до ком'юніті BEZDELNIK, тобі потрібен активний акаунт "
            "на Pocket Option (реєстрація + поповнення рахунку) — обов'язково через "
            "партнерське посилання нижче 👇\n"
            'Pocket Option — <b><a href="https://u3.shortink.io/register?utm_campaign=793458&utm_source=affiliate&utm_medium=sr&a=zk5yIcrmNGT0Jb&ac=pocketbrocker&code=BEZ100">ПОСИЛАННЯ</a></b>\n\n'
            "<b>Крок 1 — Реєстрація</b>\n"
            'Переходь за посиланням вище або натискай кнопку "РЕЄСТРАЦІЯ" 👇\n'
            "Це обов'язкова умова — без реєстрації через наше посилання активація бота буде недоступна.\n\n"
            '<i>P.S. Якщо ти вже знаходишся у нашому VIP-каналі — просто натисни "Перевірити ID" ✅</i>',
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔘 РЕЄСТРАЦІЯ", url=REF_LINK_BASE),
                    InlineKeyboardButton("🔘 ПЕРЕВІРИТИ ID", callback_data="check_id"),
                ],
                [InlineKeyboardButton("⬅️ Назад", callback_data="to_start")],
            ])
        )

    elif data == "help_contact":
        await safe_edit(query.message,
            "💬 *Потрібна допомога?*\n\nНапиши нам:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✉️ Написати", url="https://t.me/Roma_pdlps")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="to_start")],
            ])
        )

    elif data == "reviews":
        await safe_edit(query.message,
            "⭐ *Відгуки наших користувачів:*\n\nСкоро тут будуть відгуки!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="to_start")],
            ])
        )

    elif data == "noop":
        pass

    elif data == "toggle_otc":
        context.user_data["otc_enabled"] = not get_otc_enabled(context)
        await query.message.edit_reply_markup(reply_markup=main_menu(context, query.from_user.id))

    # ── Реєстрація ──
    elif data == "check_id":
        context.user_data[ASKING_ID] = True
        await safe_edit_photo(query.message, "imgs/start_imgs/id_get1.jpg",
            caption=(
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
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="get_bot")]
            ])
        )

    elif data == "check_deposit":
        uid = context.user_data.get("last_user_id")
        deposits = load_deposits()
        if uid and uid in deposits:
            await safe_edit(query.message,
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
                "👇 Подай заявку в команду через кнопку нижче:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("VIP КАНАЛ 🥳", url="https://t.me/+4MRt6RulOTllNDcy"),
                        InlineKeyboardButton("НАВЧАННЯ", url="https://t.me/+SefYmx71q5ZhNDNi"),
                        InlineKeyboardButton("CHAT", url="https://t.me/+-PFhuomcUcNhN2Yy"),
                    ],
                    [
                        InlineKeyboardButton("Trade Squad", url="https://t.me/+UeH2gccJ044xYmIy"),
                        InlineKeyboardButton("TEAM", url="https://t.me/+E-Z0zFmB7FZjNzMy"),
                        InlineKeyboardButton("АКТИВУВАТИ РОБОТА 🤖", callback_data="activate_bot"),
                    ]
                ])
            )
        else:
            back_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔘 ПЕРЕВІРИТИ ДЕПОЗИТ", callback_data="check_deposit")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="check_id")]
            ])
            await safe_edit(query.message, "❌ Депозиту ще не зафіксовано", reply_markup=back_kb)

    elif data == "activate_bot":
        save_activated(query.from_user.id)
        await safe_edit(query.message,
            "🎉 Бот активовано!\n\n*BEZDELNIK BOT* — Головне меню:",
            parse_mode="Markdown", reply_markup=main_menu(context, query.from_user.id)
        )

    # ── AI ЧАТ ТРЕЙДЕР ──
    elif data == "ai_chat_start":
        context.user_data[AI_CHAT_MODE] = True
        context.user_data["ai_chat_history"] = []
        await safe_edit(query.message,
            "💬 *BEZDELNIK AI — AI Трейдер*\n\n"
            "Я твій персональний AI-помічник з трейдингу.\n"
            "Запитуй про:\n"
            "• Ситуацію на ринку 📊\n"
            "• Аналіз активів та валютних пар 💹\n"
            "• Стратегії торгівлі 📈\n"
            "• Індикатори та патерни 🔍\n"
            "• Поради для початківців 🎓\n\n"
            "Просто напиши своє питання 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")]
            ])
        )

    # ── АДМІН ПАНЕЛЬ ──
    elif data == "admin_panel":
        if query.from_user.id not in ADMIN_IDS:
            return
        users = load_all_users()
        now = datetime.now()
        total = len(users)
        week = sum(1 for d in users.values() if (now - datetime.fromisoformat(d)).days <= 7)
        month = sum(1 for d in users.values() if (now - datetime.fromisoformat(d)).days <= 30)
        activated = len(load_activated())
        deposits = len(load_deposits())
        registered = len(load_accounts())

        await safe_edit(query.message,
            f"⚙️ *АДМІН ПАНЕЛЬ*\n\n"
            f"👥 *Статистика користувачів:*\n"
            f"├ За 7 днів: `{week}`\n"
            f"├ За 30 днів: `{month}`\n"
            f"└ Всього: `{total}`\n\n"
            f"📊 *Воронка:*\n"
            f"├ Зареєстровані: `{registered}`\n"
            f"├ З депозитом: `{deposits}`\n"
            f"└ Активовані: `{activated}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 РОЗСИЛКА", callback_data="admin_broadcast")],
                [InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")],
            ])
        )

    elif data == "admin_broadcast":
        if query.from_user.id not in ADMIN_IDS:
            return
        context.user_data[BROADCAST_MODE] = True
        await safe_edit(query.message,
            "📢 *Розсилка*\n\nНадішли повідомлення (текст або фото з підписом) — "
            "бот розішле його всім користувачам.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Скасувати", callback_data="admin_panel")]
            ])
        )

    # ── НА ЗАПИТ / BEZDELNIK AI → вибір типу активу ──
    elif data in ("sig_request", "sig_bezdelnik"):
        blocked, rem = check_active_signal(context)
        if blocked:
            await safe_edit(query.message,
                f"⏳ *У вас є активний сигнал!*\n\nПочекайте ще `{rem//60}хв {rem%60}сек` поки він завершиться.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")
                ]])
            )
            return
        mode = data.replace("sig_", "")
        await safe_edit(query.message, "📂 Оберіть тип активу:", reply_markup=asset_type_kb(mode))

    # ── АВТО ШІ → відразу рандомна пара і таймфрейм ──
    elif data == "sig_auto":
        blocked, rem = check_active_signal(context)
        if blocked:
            await safe_edit(query.message,
                f"⏳ *У вас є активний сигнал!*\n\nПочекайте ще `{rem//60}хв {rem%60}сек` поки він завершиться.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")
                ]])
            )
            return
        assets = apply_otc_filter(await fetch_assets(), context)
        high = [a for a in assets if a.get("payout", 0) >= 83]
        asset = random.choice(high if high else assets)
        allowed = [c["time"] for c in asset.get("allowed_candles", [{"time": 60}])
                   if c["time"] in WORKING_TIMEFRAMES]
        timeframe = random.choice(allowed) if allowed else 60
        await safe_edit(query.message, "⏳ Генерую сигнал...")
        await asyncio.sleep(random.uniform(2, 4))
        sig = await indicator_signal(asset, timeframe, None)
        sig["type"] = "BEZDELNIK AI 🤖"
        for k in ("rsi", "ema", "macd", "stoch", "bb"):
            sig.pop(k, None)
        await send_signal_and_track(query, context, asset, sig, "auto")

    # ── ІНДИКАТОРИ → вибір типу активу (без вибору пари) ──
    elif data == "sig_indicators":
        blocked, rem = check_active_signal(context)
        if blocked:
            await safe_edit(query.message,
                f"⏳ *У вас є активний сигнал!*\n\nПочекайте ще `{rem//60}хв {rem%60}сек` поки він завершиться.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")
                ]])
            )
            return
        await safe_edit(query.message, "📂 Оберіть тип активу:", reply_markup=asset_type_kb("indicators"))

    # ── Вибір типу активу ──
    elif data.startswith("atype_"):
        parts = data.split("_", 2)
        mode = parts[1]
        atype = parts[2]
        assets = apply_otc_filter(await fetch_assets(), context)
        filtered = filter_by_asset_type(assets, atype)

        if not filtered:
            await safe_edit(query.message,
                "❌ Наразі немає доступних активів цього типу.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад", callback_data=f"sig_{mode}" if mode != "indicators" else "sig_indicators")]
                ])
            )
            return

        context.user_data[f"assets_{mode}"] = filtered

        if mode == "indicators":
            await safe_edit(query.message,
                "💱 Оберіть пару:",
                reply_markup=pair_kb("indicators", filtered, 0)
            )
        else:
            await safe_edit(query.message,
                "💱 Оберіть пару:",
                reply_markup=pair_kb(mode, filtered, 0)
            )

    # ── Пагінація ──
    elif data.startswith("page_"):
        _, mode, page = data.split("_", 2)
        assets = context.user_data.get(f"assets_{mode}", [])
        await query.message.edit_reply_markup(reply_markup=pair_kb(mode, assets, int(page)))

    # ── Випадкова пара ──
    elif data.startswith("randpair_"):
        mode = data.replace("randpair_", "")
        assets = context.user_data.get(f"assets_{mode}", await fetch_assets())
        asset = random.choice(assets)
        allowed = [c["time"] for c in asset.get("allowed_candles", [{"time": 60}])
                   if c["time"] in WORKING_TIMEFRAMES and c["time"] <= 3600]
        await safe_edit(query.message,
            f"⏱ *{asset['name']}* (`{asset['payout']}%`)\n\nОберіть таймфрейм:",
            parse_mode="Markdown",
            reply_markup=timeframe_kb(mode, asset["symbol"], allowed or [60])
        )

    # ── Конкретна пара ──
    elif data.startswith("pair_"):
        blocked, rem = check_active_signal(context)
        if blocked:
            await safe_edit(query.message,
                f"⏳ *У вас є активний сигнал!*\n\nПочекайте ще `{rem//60}хв {rem%60}сек` поки він завершиться.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")
                ]])
            )
            return
        parts = data.split("_", 2)
        mode = parts[1]
        symbol = parts[2]
        assets = await fetch_assets()
        asset = next((a for a in assets if a["symbol"] == symbol), None)
        if not asset:
            await safe_edit(query.message, "❌ Пару не знайдено")
            return
        if mode == "indicators":
            context.user_data["ind_asset"] = asset
            context.user_data["ind_selected"] = []
        allowed = [c["time"] for c in asset.get("allowed_candles", [{"time": 60}])
                   if c["time"] in WORKING_TIMEFRAMES and c["time"] <= 3600]
        await safe_edit(query.message,
            f"⏱ *{asset['name']}* (`{asset['payout']}%`)\n\nОберіть таймфрейм:",
            parse_mode="Markdown",
            reply_markup=timeframe_kb(mode, symbol, allowed or [60])
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
            await safe_edit(query.message,"❌ Пару не знайдено")
            return

        if mode == "indicators":
            # Показуємо вибір індикаторів
            selected = context.user_data.get("ind_selected", [])
            context.user_data["ind_timeframe"] = timeframe
            await safe_edit(query.message,
                f"📊 *{asset['name']}* — `{fmt_tf(timeframe)}`\n\n"
                f"Оберіть індикатори (або одразу «Отримати сигнал» для всіх):",
                parse_mode="Markdown",
                reply_markup=indicator_select_kb(mode, symbol, timeframe, selected)
            )
        elif mode == "bezdelnik":
            await safe_edit(query.message,f"🧠 BEZDELNIK AI аналізує *{asset['name']}*...", parse_mode="Markdown")
            sig = await bezdelnik_ai_signal(asset, timeframe)
            if sig.get("error"):
                await safe_edit(query.message, f"❌ {sig['error']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]))
                return
            await send_signal_and_track(query, context, asset, sig, mode)
        else:
            # НА ЗАПИТ → аналіз через індикатори (всі), але показуємо як AI
            await safe_edit(query.message,"⏳ Генерую сигнал...")
            await asyncio.sleep(random.uniform(2, 4))
            sig = await indicator_signal(asset, timeframe, None)
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
            reply_markup=indicator_select_kb(mode, symbol, timeframe, selected)
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
            await safe_edit(query.message,"❌ Пару не знайдено")
            return

        await safe_edit(query.message,f"⏳ Аналізую *{asset['name']}*...", parse_mode="Markdown")
        sig = await indicator_signal(asset, timeframe, indicators)
        if sig.get("error"):
            await safe_edit(query.message, f"❌ {sig['error']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu")]]))
            return
        await send_signal_and_track(query, context, asset, sig, mode)

    # ── Мої сигнали ──
    elif data == "my_signals":
        tg_id = query.from_user.id
        s = get_user_stats(tg_id)
        percentile = get_activity_percentile(tg_id)
        try:
            days = (datetime.now() - datetime.strptime(s["joined"], "%Y-%m-%d")).days
        except Exception:
            days = 0
        text = (
            f"💪 *Моя статистика:*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Кількість угод: `{s['total']}`\n"
            f"✅ Профітних: `{s['profit']}`\n"
            f"❌ Збиткових: `{s['loss']}`\n"
            f"↔️ Нічия: `{s['draw']}`\n\n"
            f"🕒 Днів у боті: `{days}`\n\n"
            f"*Рейтинг активності:*\n"
            f"📊 Ви активніші, ніж `{percentile}%` учасників!"
        )
        await safe_edit(query.message,
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")
            ]])
        )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    track_user(tg_id)

    # ── РОЗСИЛКА (адмін) ──
    if context.user_data.get(BROADCAST_MODE) and tg_id in ADMIN_IDS:
        context.user_data[BROADCAST_MODE] = False
        text = update.message.text
        users = load_all_users()
        sent, failed = 0, 0
        await update.message.reply_text(f"📢 Розсилаю повідомлення {len(users)} користувачам...")
        for uid in users:
            try:
                await context.bot.send_message(chat_id=int(uid), text=text, parse_mode="Markdown")
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(
            f"✅ Розсилка завершена!\n\n📨 Доставлено: `{sent}`\n❌ Не доставлено: `{failed}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Адмін панель", callback_data="admin_panel")]
            ])
        )
        return

    # ── AI ЧАТ ТРЕЙДЕР ──
    if context.user_data.get(AI_CHAT_MODE):
        user_msg = update.message.text.strip()
        if not user_msg:
            return

        # ── Ліміт 20 повідомлень на день ──
        today = datetime.now().strftime("%Y-%m-%d")
        ai_day = context.user_data.get("ai_chat_day", "")
        ai_count = context.user_data.get("ai_chat_count", 0)
        if ai_day != today:
            ai_day = today
            ai_count = 0
        if ai_count >= 20:
            await update.message.reply_text(
                "⚠️ Ти вичерпав ліміт — *20 повідомлень на день*.\nСпробуй завтра!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")]
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
            "Відповідай українською мовою. Ти допомагаєш трейдерам з аналізом ринку, "
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

            warn = f"\n\n⚠️ _Залишилось {remaining} повідомлень на сьогодні_" if remaining <= 5 else ""
            back_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")]
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
                        caption="🧠 *BEZDELNIK AI* — ілюстрація",
                        parse_mode="Markdown", reply_markup=back_kb
                    )
                except Exception as e:
                    print(f"AI Image gen error: {e}")
        except Exception as e:
            print(f"AI Chat error: {e}")
            await update.message.reply_text(
                "⚠️ Щось пішло не так, спробуй ще раз.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")]
                ])
            )
        return

    if context.user_data.get(ASKING_ID):
        user_input = update.message.text.strip()
        user_id = "".join(ch for ch in user_input if ch.isdigit())
        context.user_data[ASKING_ID] = False
        if user_id and user_id in load_accounts():
            tg_id = update.effective_user.id
            ok, err_msg = bind_pocket_id(user_id, tg_id)
            if not ok:
                await update.message.reply_text(
                    err_msg, parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Назад", callback_data="check_id")]
                    ])
                )
                return
            context.user_data["last_user_id"] = user_id
            await update.message.reply_text(
                """✅ Реєстрація успішно завершена!
Залишився лише останній крок перед початком роботи 🥳

🤖 Наш торговий робот працює тільки з активними трейдерами, тому потрібно активувати акаунт — поповнити баланс на будь-яку зручну суму.

📹 Внизу ти знайдеш коротку відеоінструкцію, де показано як поповнити рахунок вигідніше та отримати +60% до депозиту.
🎁 Промокод для бонусу:
👉 BEZ100 — +60% до депозиту
...📩 Після поповнення:
надішли мені ще раз свій ID акаунта, і ти отримаєш:

✅ Доступ до індивідуальної торгівлі з роботом

✅ Запрошення в закриті джерела екосистеми Alentra

✅ Додаткові матеріали та сигнали

🚀 Радий буду бачити тебе в команді. Ти вже на правильному шляху до результату!


Поповніть рахунок і лише після цього натисніть кнопку нижче 👇""",
                parse_mode="Markdown", reply_markup=deposit_menu()
            )
        else:
            await update.message.reply_text(
                "❌ Акаунт не зареєстрований через посилання",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад", callback_data="check_id")]
                ])
            )


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    track_user(tg_id)

    # ── РОЗСИЛКА ФОТО (адмін) ──
    if context.user_data.get(BROADCAST_MODE) and tg_id in ADMIN_IDS:
        context.user_data[BROADCAST_MODE] = False
        photo = update.message.photo[-1].file_id
        caption = update.message.caption or ""
        users = load_all_users()
        sent, failed = 0, 0
        await update.message.reply_text(f"📢 Розсилаю фото {len(users)} користувачам...")
        for uid in users:
            try:
                await context.bot.send_photo(chat_id=int(uid), photo=photo, caption=caption, parse_mode="Markdown")
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(
            f"✅ Розсилка завершена!\n\n📨 Доставлено: `{sent}`\n❌ Не доставлено: `{failed}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Адмін панель", callback_data="admin_panel")]
            ])
        )
        return

    """Аналіз фото через BEZDELNIK AI (vision)"""
    if not context.user_data.get(AI_CHAT_MODE):
        return

    # ── Ліміт ──
    today = datetime.now().strftime("%Y-%m-%d")
    ai_day = context.user_data.get("ai_chat_day", "")
    ai_count = context.user_data.get("ai_chat_count", 0)
    if ai_day != today:
        ai_day = today
        ai_count = 0
    if ai_count >= 20:
        await update.message.reply_text(
            "⚠️ Ти вичерпав ліміт — *20 повідомлень на день*.\nСпробуй завтра!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")]
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

    await update.message.reply_text("🔍 Аналізую зображення...")

    system_prompt = (
        "Ти — BEZDELNIK AI, торговий AI-аналітик від команди BEZDELNIK. "
        "Ти НЕ ChatGPT. Аналізуй зображення виключно з точки зору трейдингу: "
        "графіки, патерни свічок, індикатори, рівні підтримки/опору. "
        "Відповідай українською, коротко та по суті. "
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
        warn = f"\n\n⚠️ _Залишилось {remaining} повідомлень на сьогодні_" if remaining <= 5 else ""
        await update.message.reply_text(
            f"🧠 *BEZDELNIK AI:*\n\n{answer}{warn}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")]
            ])
        )
    except Exception as e:
        print(f"AI Vision error: {e}")
        await update.message.reply_text(
            "⚠️ Не вдалось проаналізувати зображення, спробуй ще раз.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Головне меню", callback_data="to_main_menu")]
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
        try:
            await context.bot.send_message(
                chat_id=tg_id,
                text="❌ Щоб отримати доступ до VIP каналу, спочатку активуй бота!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🤖 ОТРИМАТИ РОБОТА", callback_data="get_bot")]
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