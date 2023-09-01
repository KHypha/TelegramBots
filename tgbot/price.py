
from datetime import datetime
import requests

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from binance.client import Client
API_KEY = '5fyW0DEXWVCPOoCBRATcUsl44USDtBCovYCVNNv6LjBCjEwuH06W2L4Rc2YVwuUh'
API_SECRET = 'C3HhLwDM88KLJlBirAVq1Yn94cP9Qu1HRGkI2qZ5ApN4sdcF1dlvHctPvAITxJkD'

client = Client(API_KEY, API_SECRET)

# Replace with your own Telegram Bot API token
TELEGRAM_API_TOKEN = '6655743456:AAGGwfcD5Haosk9v9z_G78GN-wsh5ILYFZI'

bot = Bot(token=TELEGRAM_API_TOKEN)
updater = Updater(token=TELEGRAM_API_TOKEN)
user_prices = {}
trading_pairs = []
def get_all_trading_pairs():
    exchange_info = client.get_exchange_info()
    trading_pairs = [symbol['symbol'] for symbol in exchange_info['symbols']]
    return [pair[:-len('USDT')] for pair in trading_pairs if pair.endswith('USDT')]

trading_pairs = get_all_trading_pairs()


def get_prices(trading_pair):
    ticker = client.get_ticker(symbol=trading_pair)
    last_price = float(ticker['lastPrice'])
    price_info = client.futures_mark_price(symbol=trading_pair)
    mark_price = float(price_info["markPrice"])
    return last_price, mark_price

def get_ohlc_data(trading_pair):
    klines = client.futures_klines(symbol=trading_pair, interval=Client.KLINE_INTERVAL_1HOUR, limit=1)
    if klines:
        kline = klines[0]
        open_price = float(kline[1])
        high_price = float(kline[2])
        low_price = float(kline[3])
        close_price = float(kline[4])
        return open_price, high_price, low_price, close_price
    else:
        return None

def update_price(context: CallbackContext):
    chat_id = context.job.context
    user_data = user_prices.get(chat_id)
    
    if user_data:
        trading_pair = user_data["trading_pair"]
        last_price, mark_price = get_prices(trading_pair)
        ohlc_data = get_ohlc_data(trading_pair)
        
        last_updated_time = datetime.now().strftime("%H:%M:%S")
        
        if ohlc_data:
            open_price, high_price, low_price, close_price = ohlc_data

            if close_price > open_price:
                candle_color = "🟩"  # Green candlestick
            elif close_price < open_price:
                candle_color = "🟥"  # Red candlestick
            else:
                candle_color = "⬜"  # Neutral candlestick (Yellow or other color)

            price_message = f"Mark Price  of {trading_pair}: {mark_price}\n" \
                            f"Last Price: {last_price} \n" \
                            f"OHLC(1 Hour){candle_color}:\n" \
                            f"Open: {open_price} Close: {close_price}\n" \
                            f"High: {high_price} Low: {low_price}\n" \
                            f"Last Updated Time: {last_updated_time}"
        else:
            price_message = f"Last Price of {trading_pair}: {last_price}\n" \
                            f"Mark Price: {mark_price}\n" \
                            f"OHLC Data: Not available\n" \
                            f"Last Updated Time: {last_updated_time}"
        
        context.bot.edit_message_text(chat_id=chat_id, message_id=user_data["message_id"], text=price_message)
        user_data["last_updated_time"] = last_updated_time

def get_top_movers():
    # Define the endpoint URL
    url = 'https://fapi.binance.com/fapi/v1/ticker/24hr'

    # Make a GET request to fetch the 24-hour ticker data for all trading pairs
    response = requests.get(url)
    data = response.json()

    # Filter the data to get only USD-M futures pairs
    usd_m_futures_pairs = [pair for pair in data if pair['symbol'].endswith('USDT')]
    
    # Sort the pairs by their price change percentage (gainers and losers)
    top_gainers = sorted(usd_m_futures_pairs, key=lambda x: float(x['priceChangePercent']), reverse=True)[:10]
    top_losers = sorted(usd_m_futures_pairs, key=lambda x: float(x['priceChangePercent']))[:10]

    return top_gainers, top_losers

def display_top_movers(update: Update, context: CallbackContext):
    top_gainers, top_losers = get_top_movers()

    message = "🚀 Top Gainers:\n"
    for gainer in top_gainers:
        symbol = gainer['symbol']

        price_change_percent = gainer['priceChangePercent']
        emoji = "🔥" if float(price_change_percent) > 20 else ""

        mark_price = float(get_mark_price(symbol))
        message += f"🔼#{symbol}: {mark_price:.4f} {price_change_percent}%{emoji} \n"

    message += "\n📉 Top Losers:\n"
    for loser in top_losers:
        symbol = loser['symbol']

        price_change_percent = loser['priceChangePercent']
        emoji = "🔥" if float(price_change_percent) < -20 else ""

        mark_price = float(get_mark_price(symbol))
        message += f"🔻#{symbol}: {mark_price:.4f} {price_change_percent}%{emoji} \n"

    update.message.reply_text(message)

def get_mark_price(symbol):
    # Use the Binance API to fetch the mark price for the given symbol
    mark_price_info = client.futures_mark_price(symbol=symbol)
    mark_price = mark_price_info["markPrice"]
    return mark_price


def price(update: Update, context):
    keyboard = []
    start_index = context.user_data.get("start_index", 0)
    end_index = start_index + 10 * 3  # Display 3 rows of 10 pairs each
    pairs_to_display = trading_pairs[start_index:end_index]

    for i in range(0, len(pairs_to_display), 3):
        pairs_group = pairs_to_display[i:i+3]
        keyboard.append([InlineKeyboardButton(pair, callback_data=pair) for pair in pairs_group])

    if end_index < len(trading_pairs):
        keyboard.append([InlineKeyboardButton("Next 10", callback_data="next_10")])

    if start_index > 0:
        keyboard.append([InlineKeyboardButton("Previous 10", callback_data="prev_10")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        query = update.callback_query
        query.answer()
        query.message.edit_reply_markup(reply_markup)
    else:
        update.message.reply_text("Select a trading pair:", reply_markup=reply_markup)

def button_click(update: Update, context):
    query = update.callback_query
    query.answer()
    callback_data = query.data

    chat_id = str(query.message.chat_id)

    if callback_data in trading_pairs:
        user_prices[chat_id] = {"trading_pair": f"{callback_data}USDT"}
        last_price, mark_price = get_prices(f"{callback_data}USDT")
        last_updated_time = datetime.now().strftime("%H:%M:%S")
        
        price_message = f"Mark Price of {callback_data}USDT: {mark_price}\nMark Price: {last_price}\nLast Updated Time: {last_updated_time}"
        
        price_message = query.message.reply_text(price_message)
        
        user_prices[chat_id]["message_id"] = price_message.message_id
        
        context.job_queue.run_repeating(update_price, interval=2, first=0, context=chat_id)
    elif callback_data == "next_10":
        start_index = context.user_data.get("start_index", 0)
        context.user_data["start_index"] = start_index + 10
        price(update, context)

    elif callback_data == "prev_10":
        start_index = context.user_data.get("start_index", 0)
        context.user_data["start_index"] = start_index - 10
        price(update, context)

def main():
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("price", price))
    dispatcher.add_handler(CallbackQueryHandler(button_click))
    dispatcher.add_handler(CommandHandler("topmovers", display_top_movers))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
