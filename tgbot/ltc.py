from binance.client import Client
import time
from telegram import Bot
from telegram.ext import Updater
# Replace with your own Binance API keys
API_KEY = '5fyW0DEXWVCPOoCBRATcUsl44USDtBCovYCVNNv6LjBCjEwuH06W2L4Rc2YVwuUh'
API_SECRET = 'C3HhLwDM88KLJlBirAVq1Yn94cP9Qu1HRGkI2qZ5ApN4sdcF1dlvHctPvAITxJkD'

client = Client(API_KEY, API_SECRET)

def get_ltcusdt_price():
    ticker = client.get_ticker(symbol='LTCUSDT')
    return float(ticker['lastPrice'])


# Replace with your own Telegram Bot API token
TELEGRAM_API_TOKEN = '6655743456:AAGGwfcD5Haosk9v9z_G78GN-wsh5ILYFZI'
CHAT_ID = 'your_chat_id'

bot = Bot(token=TELEGRAM_API_TOKEN)
updater = Updater(token=TELEGRAM_API_TOKEN)

def check_price_and_alert(context):
    ltcusdt_price = get_ltcusdt_price()
    threshold = 200.0  # Define your threshold price here

    if ltcusdt_price > threshold:
        message = f'LTCUSDT price alert: {ltcusdt_price}'
        bot.send_message(chat_id=CHAT_ID, text=message)

updater.job_queue.run_repeating(check_price_and_alert, interval=60)  # Run every 60 seconds
updater.start_polling()
