import asyncio
import logging
import os

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logging.basicConfig(level=logging.INFO)

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt")

# Публичное зеркало рыночных данных Binance (не блокируется по гео, как api.binance.com).
BINANCE_URL = "https://data-api.binance.vision/api/v3/ticker/24hr"


def load_token() -> str | None:
    token = os.getenv("8776862137:AAFVeudvF2i0NPAwWzsCCBgxWCZYcKugyoY")
    if token:
        return token.strip()
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as f:
            file_token = f.read().strip()
        if file_token:
            return file_token
    return None

# Топ-7 монет: тикер -> отображаемое имя
COINS = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "BNB": "BNB",
    "SOL": "Solana",
    "XRP": "XRP",
    "ADA": "Cardano",
    "DOGE": "Dogecoin",
}

DISCLAIMER = "\n\n_Не является 100% вариантом для инвестирования, просто совет к которому можно прислушаться._"

dp = Dispatcher()


async def get_ticker(symbol: str):
    """Возвращает (last_price, change_pct) для пары <symbol>USDT с Binance."""
    params = {"symbol": f"{symbol}USDT"}
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(BINANCE_URL, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
    return float(data["lastPrice"]), float(data["priceChangePercent"])


def make_advice(change_pct: float) -> str:
    """Простая эвристика рекомендации по изменению цены за 24ч."""
    if change_pct >= 3:
        return "📈 Рост за 24ч — можно присмотреться к покупке"
    if change_pct <= -3:
        return "📉 Падение за 24ч — лучше подождать / действовать осторожно"
    return "➖ Боковик — нейтрально, без спешки"


def start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🚀 Старт", callback_data="start")]]
    )


def coins_kb() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"{name} ({sym})", callback_data=f"coin:{sym}")
        for sym, name in COINS.items()
    ]
    # по 2 кнопки в ряд
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к монетам", callback_data="back")]
        ]
    )


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я крипто-бот.\n"
        "Покажу цены топовых монет с биржи Binance и дам простой совет.\n\n"
        "Нажми «Старт», чтобы выбрать монету.",
        reply_markup=start_kb(),
    )


@dp.callback_query(F.data == "start")
async def on_start_button(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "Выбери криптовалюту:", reply_markup=coins_kb()
    )
    await callback.answer()


@dp.callback_query(F.data == "back")
async def on_back(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "Выбери криптовалюту:", reply_markup=coins_kb()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("coin:"))
async def on_coin(callback: CallbackQuery) -> None:
    symbol = callback.data.split(":", 1)[1]
    name = COINS.get(symbol, symbol)
    await callback.answer("Загружаю данные...")

    try:
        price, change_pct = await get_ticker(symbol)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Ошибка запроса к Binance")
        await callback.message.answer(
            f"⚠️ Не удалось получить данные по {name} ({symbol}).\n"
            "Попробуй позже.",
            reply_markup=back_kb(),
        )
        return

    advice = make_advice(change_pct)
    sign = "+" if change_pct >= 0 else ""
    text = (
        f"💰 *{name} ({symbol}/USDT)*\n"
        f"Цена: `{price:,.4f}` USDT\n"
        f"Изменение за 24ч: {sign}{change_pct:.2f}%\n\n"
        f"Рекомендация: {advice}"
        f"{DISCLAIMER}"
    )
    await callback.message.answer(
        text, parse_mode="Markdown", reply_markup=back_kb()
    )


async def main() -> None:
    token = load_token()
    if not token:
        raise RuntimeError(
            "Не задан токен бота. Вставьте токен в файл token.txt "
            "или задайте переменную окружения BOT_TOKEN (токен у @BotFather)."
        )
    bot = Bot(token=token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
