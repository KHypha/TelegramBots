from telegram import Bot, Update, InlineKeyboardMarkup, ReplyKeyboardMarkup,InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram.ext import ConversationHandler
from binance.client import Client

API_KEY = '5fyW0DEXWVCPOoCBRATcUsl44USDtBCovYCVNNv6LjBCjEwuH06W2L4Rc2YVwuUh'
API_SECRET = 'C3HhLwDM88KLJlBirAVq1Yn94cP9Qu1HRGkI2qZ5ApN4sdcF1dlvHctPvAITxJkD'

client = Client(API_KEY, API_SECRET)

# Replace with your own Telegram Bot API token
TELEGRAM_API_TOKEN = '6655743456:AAGGwfcD5Haosk9v9z_G78GN-wsh5ILYFZI'
bot = Bot(token=TELEGRAM_API_TOKEN)
updater = Updater(token=TELEGRAM_API_TOKEN)

chat_id = None
is_monitoring = False

trading_pairs = []  # List to store all trading pairs
current_page = 0
pairs_per_page = 10

def get_all_trading_pairs():
    exchange_info = client.get_exchange_info()
    trading_pairs = [symbol['symbol'] for symbol in exchange_info['symbols']]
    return trading_pairs


trading_pairs = get_all_trading_pairs()
COIN_LIST = [pair[:-len('USDT')] for pair in trading_pairs if pair.endswith('USDT')]
SELECT_COIN, MONITORING = range(2)

def display_page(update: Update, context, page):
    global current_page
    current_page = page
    start_index = page * pairs_per_page
    end_index = start_index + pairs_per_page
    pairs_to_display = trading_pairs[start_index:end_index]

    keyboard = [[InlineKeyboardButton(f"{i + 1}", callback_data=str(i + 1))] for i in range(len(pairs_to_display))]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"Trading Pairs:\n\n"
    for i, pair in enumerate(pairs_to_display):
        message += f"{i + 1}. {pair}\n"
    
    if page > 0:
        reply_markup.inline_keyboard.append([InlineKeyboardButton("<< Previous", callback_data="prev")])
    if end_index < len(trading_pairs):
        reply_markup.inline_keyboard.append([InlineKeyboardButton("Next >>", callback_data="next")])
    
    context.bot.send_message(chat_id=update.effective_chat.id, text=message, reply_markup=reply_markup)


def start(update: Update, context):
    global chat_id, is_monitoring
    chat_id = update.message.chat_id
    context.bot.send_message(chat_id=chat_id, text="Welcome! Select a coin to monitor from the list below:",
                             reply_markup=ReplyKeyboardMarkup([COIN_LIST], one_time_keyboard=True))
    return SELECT_COIN

def select_coin(update: Update, context):
    selected_coin = update.message.text
    context.user_data['selected_coin'] = selected_coin
    context.bot.send_message(chat_id=chat_id, text=f"You've selected {selected_coin}. Monitoring started. Send /stop to stop monitoring.")
    
    context.job_queue.run_repeating(check_price_and_alert, interval=60, first=0, context=selected_coin)
    
    return MONITORING

def stop(update: Update, context):
    global is_monitoring
    is_monitoring = False
    context.bot.send_message(chat_id=chat_id, text="Monitoring stopped.")
    return ConversationHandler.END

def check_price_and_alert(context):
    selected_coin = context.job.context
    coin_pair = f"{selected_coin}USDT"
    ticker = client.get_ticker(symbol=coin_pair)
    price = ticker['lastPrice']
    context.bot.send_message(chat_id=chat_id, text=f"Current {coin_pair} price: {price}")

def main():
    dispatcher = updater.dispatcher
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_COIN: [MessageHandler(Filters.text & ~Filters.command, select_coin)],
            MONITORING: [CommandHandler('stop', stop)]
        },
        fallbacks=[],
    )
    dispatcher.add_handler(conv_handler)
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
