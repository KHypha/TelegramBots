import time
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
from binance.client import Client

# Replace with your own Telegram Bot API token
TELEGRAM_API_TOKEN = '6655743456:AAGGwfcD5Haosk9v9z_G78GN-wsh5ILYFZI'

API_KEY = '5fyW0DEXWVCPOoCBRATcUsl44USDtBCovYCVNNv6LjBCjEwuH06W2L4Rc2YVwuUh'
API_SECRET = 'C3HhLwDM88KLJlBirAVq1Yn94cP9Qu1HRGkI2qZ5ApN4sdcF1dlvHctPvAITxJkD'

client = Client(API_KEY, API_SECRET)

bot = Bot(token=TELEGRAM_API_TOKEN)
updater = Updater(token=TELEGRAM_API_TOKEN)

is_monitoring = False
chat_id = None

def get_ltcusdt_price():
    ticker = client.get_ticker(symbol='LTCUSDT')
    return float(ticker['lastPrice'])

def start(update: Update, context):
    global is_monitoring, chat_id
    is_monitoring = True
    chat_id = update.message.chat_id
    context.bot.send_message(chat_id=chat_id, text="Monitoring LTCUSDT price. Use /stop to stop monitoring.")

def stop(update: Update, context):
    global is_monitoring
    is_monitoring = False
    context.bot.send_message(chat_id=chat_id, text="Monitoring stopped.")

def update_price(update: Update, context):
    ltcusdt_price = get_ltcusdt_price()
    message = f'Current LTCUSDT price: {ltcusdt_price}'
    context.bot.send_message(chat_id=chat_id, text=message)

def check_price_and_alert(context):
    if is_monitoring and chat_id:
        ltcusdt_price = get_ltcusdt_price()
        threshold = 83.3  # Define your threshold price here

        if ltcusdt_price > threshold:
            message = f'LTCUSDT price alert: {ltcusdt_price}'
            context.bot.send_message(chat_id=chat_id, text=message)

def main():
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("stop", stop))
    dispatcher.add_handler(CommandHandler("update", update_price))
    
    job_queue = updater.job_queue
    job_queue.run_repeating(check_price_and_alert, interval=60)  # Run every 60 seconds
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
