import time
import random
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
#from binance.enums import FuturesSymbol
from binance.client import Client
#API_KEY = '5fyW0DEXWVCPOoCBRATcUsl44USDtBCovYCVNNv6LjBCjEwuH06W2L4Rc2YVwuUh'
#API_SECRET = 'C3HhLwDM88KLJlBirAVq1Yn94cP9Qu1HRGkI2qZ5ApN4sdcF1dlvHctPvAITxJkD'

API_KEY = '5fyW0DEXWVCPOoCBRATcUsl44USDtBCovYCVNNv6LjBCjEwuH06W2L4Rc2YVwuUh'
API_SECRET = 'C3HhLwDM88KLJlBirAVq1Yn94cP9Qu1HRGkI2qZ5ApN4sdcF1dlvHctPvAITxJkD'

client = Client(API_KEY, API_SECRET)

# Replace with your own Telegram Bot API token
TELEGRAM_API_TOKEN = '6655743456:AAGGwfcD5Haosk9v9z_G78GN-wsh5ILYFZI'

bot = Bot(token=TELEGRAM_API_TOKEN)
updater = Updater(token=TELEGRAM_API_TOKEN)
user_prices = {}  # Dictionary to store user's price messages
welcome_messages = [
    "Welcome to the bot! How can I assist you today?",
    "Hello! Feel free to explore the bot's features.",
    "Greetings! What can I do for you?",
]

user_alerts = {}  # Store user alerts: {'chat_id': [alert_type, trading_pair, price, interval]}
trading_pairs = []
def random_welcome_message():
    return random.choice(welcome_messages)


def get_all_trading_pairs():
    exchange_info = client.get_exchange_info()
    trading_pairs = [symbol['symbol'] for symbol in exchange_info['symbols']]
    return trading_pairs


trading_pairs = get_all_trading_pairs()
trading_pairs = [pair[:-len('USDT')] for pair in trading_pairs if pair.endswith('USDT')]
SELECT_COIN, MONITORING = range(2)

def start(update: Update, context):
    update.message.reply_text(random_welcome_message())

def price(update: Update, context):
    keyboard = []
    for i in range(0, len(trading_pairs), 10):
        pairs_group = trading_pairs[i:i+10]
        keyboard.append([InlineKeyboardButton(pair, callback_data=pair) for pair in pairs_group])
    keyboard.append([InlineKeyboardButton("Back", callback_data="price_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select a trading pair:", reply_markup=reply_markup)

def alert(update: Update, context):
    chat_id = update.message.chat_id
    keyboard = [
        [
            InlineKeyboardButton("One Time Alert", callback_data=f'alert_one_time:{chat_id}'),
            InlineKeyboardButton("Repeated Alert", callback_data=f'alert_repeated:{chat_id}'),
            InlineKeyboardButton("Timely Alert", callback_data=f'alert_timely:{chat_id}'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select an alert type:", reply_markup=reply_markup)

def button_click(update: Update, context):
    query = update.callback_query
    query.answer()
    callback_data = query.data

    chat_id = str(query.message.chat_id)  # Convert chat_id to string for dictionary key

    if callback_data in trading_pairs:
        user_alerts[chat_id] = ["price", f"{callback_data}USDT"]  # Store user's selected trading pair with 'USDT'
        trading_pair = user_alerts[chat_id][1]
        price = get_price(trading_pair)
        # Send the initial price message and store the message ID
        price_message = query.message.reply_text(f"Selected trading pair: {trading_pair}\nCurrent price: {price}\nEnter the price to check:")
        user_prices[chat_id] = {"trading_pair": trading_pair, "message_id": price_message.message_id}
        # Schedule the update_price function to run periodically
        context.job_queue.run_repeating(update_price, interval=0.1, context=chat_id)


        
    elif callback_data.startswith("alert_one_time"):
        user_alerts[chat_id] = ["one_time"]
        query.edit_message_text(text="Provide the trading pair for the alert:")
    elif callback_data.startswith("alert_repeated"):
        user_alerts[chat_id] = ["repeated"]
        query.edit_message_text(text="Provide the trading pair for the alert:")
    elif callback_data.startswith("alert_timely"):
        user_alerts[chat_id] = ["timely"]
        query.edit_message_text(text="Provide the trading pair for the alert:")
    else:
        query.edit_message_text(text="Invalid selection. Please choose from the provided options.")
        return

def handle_user_input(update: Update, context):
    chat_id = str(update.message.chat_id)
    user_input = update.message.text

    if chat_id in user_alerts:
        alert_type = user_alerts[chat_id][0]
        if alert_type in ["one_time", "repeated", "timely"]:
            if 'trading_pair' not in user_alerts[chat_id]:
                user_alerts[chat_id].append(user_input)  # Store the trading pair
                update.message.reply_text(f"Trading pair for the alert: {user_input}USDT\nNow, enter the price for the alert:")
                return
            elif 'price' not in user_alerts[chat_id]:
                user_alerts[chat_id].append(user_input)  # Store the price
                trading_pair = user_alerts[chat_id][1]
                price = get_price(trading_pair)
                update.message.reply_text(f"Trading pair: {trading_pair}\nCurrent price: {price}\nAlert price set to: {user_input}\nYour alert is active now.")
                user_alerts.pop(chat_id)  # Clear the stored alert data
                return
        # Handle other cases
        user_alerts.pop(chat_id)  # Clear the stored alert data
    elif user_input in trading_pairs:
        trading_pair = f"{user_input}USDT"  # Append 'USDT' to the selected trading pair

        # Send the initial price message and store the message ID
        price_message = update.message.reply_text(f"Price of {trading_pair}: {get_price(trading_pair)}")
        user_prices[chat_id] = {"trading_pair": trading_pair, "message_id": price_message.message_id}

        # Schedule the update_price function to run periodically
        context.job_queue.run_repeating(update_price, interval=60, context=chat_id)
    else:
        update.message.reply_text("Invalid input. Please use the provided buttons or commands.")


def handle_one_time_alert(chat_id, price):
    user_alerts[chat_id].extend(["one_time", float(price)])
    bot.send_message(chat_id, f"One-time alert set at price {price}")

def handle_repeated_alert(chat_id, price):
    user_alerts[chat_id].extend(["repeated", float(price)])
    bot.send_message(chat_id, f"Repeated alert set at price {price}")

def handle_timely_alert(chat_id, interval):
    user_alerts[chat_id].extend(["timely", int(interval)])
    trading_pair = user_alerts[chat_id][1]
    bot.send_message(chat_id, f"Timely alert set for {trading_pair} with interval {interval} minutes")

def check_alerts(context):
    for chat_id, alert_data in user_alerts.items():
        alert_type = alert_data[0]
        trading_pair = alert_data[1]
        if alert_type == "one_time":
            price_threshold = alert_data[2]
            current_price = get_price(trading_pair)
            if current_price >= price_threshold:
                bot.send_message(chat_id, f"Price of {trading_pair} exceeded {price_threshold}.")
                user_alerts.pop(chat_id)  # Remove the one-time alert

        elif alert_type == "repeated":
            price_threshold = alert_data[2]
            current_price = get_price(trading_pair)
            if current_price >= price_threshold:
                bot.send_message(chat_id, f"Price of {trading_pair} exceeded {price_threshold}.")

        elif alert_type == "timely":
            interval = alert_data[2]
            last_check_time = alert_data[3] if len(alert_data) > 3 else 0
            current_time = int(time.time())
            if current_time - last_check_time >= interval * 60:
                current_price = get_price(trading_pair)
                bot.send_message(chat_id, f"Price of {trading_pair}: {current_price}")
                user_alerts[chat_id][3] = current_time  # Update last_check_time

    # Schedule the next alert check after 60 seconds
    context.job_queue.run_once(check_alerts, when=60)

def get_price(trading_pair):
    #trading_pair = f"{trading_pair}USDT"
    ticker = client.get_ticker(symbol=trading_pair)  # Use the Binance Client to fetch the price
    price = ticker['lastPrice']
    return price

def get_mark_price(trading_pair):
    #symbol_info = client.get_symbol_info(trading_pair)
    #if symbol_info["contractType"] == FuturesSymbol.PERPETUAL:
    mark_price = client.futures_mark_price(symbol=trading_pair)
    return mark_price["markPrice"]
    #else:
        #ticker = client.get_ticker(symbol=trading_pair)
        #return ticker['lastPrice']
    
def positions(update: Update, context):
    chat_id = str(update.message.chat_id)
    
    # Get the user's account information
    account_info = client.futures_account()
    positions = account_info['positions']

    message = "Current Positions and Unrealized PNL:\n"
    
    for position in positions:
        if float(position['positionAmt']) != 0:
            symbol = position['symbol']
            position_amt = float(position['positionAmt'])
            entry_price = float(position['entryPrice'])
            mark_price = get_mark_price(symbol)
            unrealized_pnl = (mark_price - entry_price) * position_amt

            message += f"\nSymbol: {symbol}\nPosition Amount: {position_amt:.4f}\nEntry Price: {entry_price:.4f}\nMark Price: {mark_price:.4f}\nUnrealized PNL: {unrealized_pnl:.4f} USDT\n"

    update.message.reply_text(message)

    
    
def update_price(context):
    chat_id = context.job.context
    user_data = user_prices.get(chat_id)
    
    if user_data:
        trading_pair = user_data["trading_pair"]
        price = get_price(trading_pair)
        small_random_number = random.uniform(0.00001, 0.0001)
        
        markPrice = get_mark_price(trading_pair)
        lastPrice = float(price) + small_random_number
        
        context.bot.edit_message_text(chat_id=chat_id, message_id=user_data["message_id"], text=f"Last Price of {trading_pair}: {lastPrice}\n Mark Price : {markPrice}")
        user_data["last_mark_price"] = price
        
        # Edit the previously sent message to update the price


def main():
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("price", price))
    dispatcher.add_handler(CommandHandler("alert", alert))
    dispatcher.add_handler(CallbackQueryHandler(button_click))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_user_input))
    dispatcher.add_handler(CommandHandler("positions", positions))

    job_queue = updater.job_queue
    job_queue.run_once(check_alerts, when=60)  # Schedule the first alert check after 60 seconds
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
