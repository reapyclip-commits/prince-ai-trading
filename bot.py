import os
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TWELVE_KEY = os.getenv("TWELVE_KEY")

PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY"]
chat_ids = set()
last_signals = {}

def get_signal(pair):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": pair,
        "interval": "1min",
        "outputsize": 60,
        "apikey": TWELVE_KEY
    }

    data = requests.get(url, params=params, timeout=15).json()

    if "values" not in data:
        return None

    prices = [
        float(x["close"])
        for x in reversed(data["values"])
    ]

    def ema(values, period):
        alpha = 2 / (period + 1)
        result = values[0]
        for price in values[1:]:
            result = price * alpha + result * (1 - alpha)
        return result

    fast_now = ema(prices[-30:], 9)
    slow_now = ema(prices[-30:], 21)
    fast_prev = ema(prices[-31:-1], 9)
    slow_prev = ema(prices[-31:-1], 21)

    changes = [
        prices[i] - prices[i-1]
        for i in range(len(prices)-14, len(prices))
    ]
    gains = sum(max(x, 0) for x in changes) / 14
    losses = sum(max(-x, 0) for x in changes) / 14

    rsi = 100 if losses == 0 else 100 - (100 / (1 + gains/losses))

    if fast_prev <= slow_prev and fast_now > slow_now and 50 < rsi < 70:
        return "BUY 🟢"

    if fast_prev >= slow_prev and fast_now < slow_now and 30 < rsi < 50:
        return "SELL 🔴"

    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_ids.add(update.effective_chat.id)
    await update.message.reply_text(
        "👑 PRINCE AI TRADING BOT\n\n"
        "Bot connected successfully!\n"
        "/signal - Check signals\n"
        "/status - Bot status\n\n"
        "Signals are educational, not guaranteed."
    )


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Checking market...")
    for pair in PAIRS:
        try:
            result = get_signal(pair)
            message = f"{pair}: {result or 'WAIT ⚪'}"
        except Exception:
            message = f"{pair}: Data unavailable"
        await update.message.reply_text(message)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🟢 PRINCE AI is running.\n"
        "Mode: Signal alerts only\n"
        "Market: 1-minute FX data"
    )


async def automatic_signals(context: ContextTypes.DEFAULT_TYPE):
    for pair in PAIRS:
        try:
            result = get_signal(pair)
            if result:
                key = f"{pair}_{result}"
                if last_signals.get(pair) != key:
                    last_signals[pair] = key
                    message = (
                        f"👑 PRINCE AI SIGNAL\n\n"
                        f"Pair: {pair}\n"
                        f"Signal: {result}\n"
                        f"Timeframe: 1 minute\n"
                        f"⚠️ Confirm on demo before trading."
                    )
                    for chat_id in list(chat_ids):
                        await context.bot.send_message(
                            chat_id=chat_id, text=message
                        )
        except Exception:
            continue


def main():
    if not BOT_TOKEN or not TWELVE_KEY:
        raise RuntimeError("BOT_TOKEN or TWELVE_KEY is missing")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("status", status))

    app.job_queue.run_repeating(
        automatic_signals, interval=60, first=10
    )
    app.run_polling()


if __name__ == "__main__":
    main()
