import os
import json
import logging
from binance.client import Client
from telegram import Bot
from telegram.ext import Updater, CommandHandler
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv
import threading
import time
from datetime import datetime, timedelta

# Flag to control email fetching
is_fetching_signals = True


# Load environment variables from .env file
load_dotenv()
chat_id = '1068035728'

# Set up logging
logging.basicConfig(filename='trading_bot.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# API Keys
BINANCE_API_KEY = os.getenv('TRADING_API_KEY')
BINANCE_API_SECRET = os.getenv('TRADING_API_SECRET')
TELEGRAM_API_TOKEN = os.getenv('PRICE_TOKEN')

# Set up Binance client
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

# Set up Telegram bot
bot = Bot(token=TELEGRAM_API_TOKEN)
updater = Updater(token=TELEGRAM_API_TOKEN, use_context=True)

# Gmail API setup
def authenticate_gmail():
    creds = None
    token_path = 'token.json'
    creds_path = 'credentials.json'

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/gmail.modify'])

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, ['https://www.googleapis.com/auth/gmail.modify'])
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

# Function to send messages to the user
def send_message_to_user(chat_id, message, parse_mode=None):
    try:
        if parse_mode:
            bot.send_message(chat_id=chat_id, text=message, parse_mode=parse_mode)
        else:
            bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logging.error(f"Error sending message to user: {e}")


# Function to log messages
def log_message(message):
    logging.info(message)

# Function to fetch current market price for the given symbol
def get_market_price(symbol):
    try:
        ticker = client.futures_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        log_message(f"Error fetching market price for {symbol}: {e}")
        return None

# Function to mark the email as read after processing
def mark_email_as_read(service, msg_id):
    try:
        service.users().messages().modify(userId='me', id=msg_id, body={'removeLabelIds': ['UNREAD']}).execute()
        log_message(f"Email {msg_id} marked as read.")
    except Exception as e:
        log_message(f"Error marking email as read: {e}")
# Function to send formatted order details
def send_order_summary(chat_id, order, take_profit_order):
    try:
        # Extract relevant details from the orders
        symbol = order['symbol']
        side = order['side']
        quantity = order['origQty']
        entry_price = order['price']
        take_profit_price = take_profit_order['price']

        # Format the message with the order details
        message = (
            f"Order Summary for {symbol}\n\n"
            f"📊 *Side*: {side}\n"
            f"📊 *Quantity*: {quantity}\n"
            f"📊 *Entry Price*: `{entry_price}`\n"
            f"📊 *Take-Profit Price*: `{take_profit_price}`\n\n"
            f"💡 *Copy Details*: Tap and hold the price to copy.\n\n"
            f"Entry Price: `{entry_price}`\n"
            f"Take-Profit Price: `{take_profit_price}`"
        )

        # Send the message with click-to-copy feature (backticks around the price values for easy copying)
        send_message_to_user(chat_id, message, parse_mode='Markdown')
    
    except Exception as e:
        log_message(f"Error sending order summary: {e}")
        send_message_to_user(chat_id, f"Error sending order summary: {e}")

def round_price_to_tick_size(price, tick_size):
    return round(price / tick_size) * tick_size
def round_quantity_to_step_size(quantity, step_size):
    return round(quantity / step_size) * step_size

# Function to place limit order on Binance with quantity based on available USDT and leverage
def place_limit_order(symbol, side):
    try:
        # Fetch symbol info (precision, tick size, step size)
        symbol_info = get_symbol_info(symbol)
        if not symbol_info:
            log_message(f"Error: Could not fetch symbol info for {symbol}")
            return

        price_precision = symbol_info['price_precision']
        quantity_precision = symbol_info['quantity_precision']
        tick_size = symbol_info['tick_size']
        step_size = symbol_info['step_size']

        # Fetch market price (entry price)
        entry_price = get_market_price(symbol)
        if not entry_price:
            log_message(f"Error: Could not fetch market price for {symbol}")
            return

        # Get available USDT balance
        account_info = client.futures_account_balance()
        usdt_balance = next(item for item in account_info if item['asset'] == 'USDT')['balance']
        usdt_balance = float(usdt_balance)

        # Calculate quantity based on 10x leverage of available USDT
        leverage = 10
        total_capital = usdt_balance * leverage
        quantity = total_capital / entry_price

        # Round quantity to match precision and step size
        quantity = round(quantity, quantity_precision)
        quantity = round_quantity_to_step_size(quantity, step_size)

        # Calculate take-profit price (1% target)
        if side == 'BUY':
            take_profit_price = entry_price * 1.0077  # 1% higher for long positions
        elif side == 'SELL':
            take_profit_price = entry_price * 0.992  # 1% lower for short positions
        else:
            log_message(f"Invalid side: {side}")
            return

        # Adjust prices to match tick size
        entry_price = round_price_to_tick_size(entry_price, tick_size)
        take_profit_price = round_price_to_tick_size(take_profit_price, tick_size)

        # Round prices according to the symbol's precision
        entry_price = round(entry_price, price_precision)
        take_profit_price = round(take_profit_price, price_precision)

        position_side = 'LONG' if side == 'BUY' else 'SHORT'

        # Place the entry limit order
        send_message_to_user(chat_id, f"Placing {side} order for {quantity} {symbol} at {entry_price}.")
        log_message(f"Placing {side} order for {quantity} {symbol} at {entry_price}.")
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=entry_price,  # Rounded market price for entry
            type=Client.ORDER_TYPE_LIMIT,
            timeInForce=Client.TIME_IN_FORCE_GTC,
            positionSide=position_side
        )

        # Check if the entry order is filled
        while True:
            order_status = client.futures_get_order(symbol=symbol, orderId=order['orderId'])
            if order_status['status'] == 'FILLED':
                log_message(f"Entry order for {symbol} is filled.")
                send_message_to_user(chat_id, f"✅ Entry order for {quantity} {symbol} at {entry_price} has been filled!")
                break
            else:
                log_message(f"Waiting for entry order to be filled... Current status: {order_status['status']}")
                time.sleep(5)  # Wait for 5 seconds before checking again

        # Define trailing stop parameters
        trailing_delta = 0.25  # 0.25% trailing delta (adjust as needed)
        activation_price = take_profit_price  # Activation price set to the original take-profit price

        # Place the trailing stop order
        log_message(f"Placing trailing stop order for {quantity} {symbol}")
        send_message_to_user(chat_id, f"Placing trailing stop order for {quantity} {symbol} with activation at {activation_price} and trailing delta of {trailing_delta}%.")

        trailing_stop_order = client.futures_create_order(
            symbol=symbol,
            side='SELL' if side == 'BUY' else 'BUY',  # Opposite of the entry side
            quantity=quantity,
            type=Client.ORDER_TYPE_TRAILING_STOP_MARKET,
            activationPrice=activation_price,  # The price at which the trailing stop becomes active
            callbackRate=trailing_delta,  # Trailing stop percentage
            timeInForce=Client.TIME_IN_FORCE_GTC,
            positionSide=position_side
        )

        log_message(f"Entry order and trailing stop order created:\n{order}\n{trailing_stop_order}")
        send_order_summary(chat_id=chat_id, order=order, take_profit_order=trailing_stop_order)
        
    except Exception as e:
        log_message(f"Error placing limit order: {e}")
        send_message_to_user(chat_id, f"Error placing limit order: {e}")


# Function to get symbol precision
def get_symbol_info(symbol):
    try:
        exchange_info = client.futures_exchange_info()
        symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == symbol), None)

        if symbol_info is None:
            log_message(f"Symbol {symbol} not found.")
            return None

        # Get price and quantity precision
        price_precision = symbol_info['pricePrecision']
        quantity_precision = symbol_info['quantityPrecision']
        
        # Get tick size and step size from filters
        tick_size = None
        step_size = None
        for f in symbol_info['filters']:
            if f['filterType'] == 'PRICE_FILTER':
                tick_size = float(f['tickSize'])
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])

        return {
            'price_precision': price_precision,
            'quantity_precision': quantity_precision,
            'tick_size': tick_size,
            'step_size': step_size
        }

    except Exception as e:
        log_message(f"Error fetching symbol info: {e}")
        return None





# Function to read email and place trades based on email subjects
def read_email_and_place_trade(service):
    global is_fetching_signals
    try:
        result = service.users().messages().list(
            userId='me', 
            labelIds=['INBOX'], 
            q='from:noreply@tradingview.com OR from:hyphakofi@gmail.com is:unread'
        ).execute()
        messages = result.get('messages', [])

        if not messages:
            log_message("No new emails found.")
            return

        for msg in messages:
            msg_id = msg['id']
            message = service.users().messages().get(userId='me', id=msg_id).execute()

            subject = next(header['value'] for header in message['payload']['headers'] if header['name'] == 'Subject')
            log_message(f"Email subject received: '{subject}'")
            send_message_to_user(chat_id, f"New signal received: '{subject}'")

            # Extract the timestamp of the email
            internal_date = int(message['internalDate'])  # in milliseconds
            email_time = datetime.fromtimestamp(internal_date / 1000)
            current_time = datetime.utcnow()
            time_threshold = current_time - timedelta(minutes=2)  # Only process emails within the last 2 minutes

            if email_time < time_threshold:
                log_message(f"Email {msg_id} is older than 2 minutes. Skipping.")
                send_message_to_user(chat_id, f"Skipped processing email {msg_id} as it's older than 2 minutes.")
                mark_email_as_read(service, msg_id)  # Optionally mark as read to avoid reprocessing
                continue

            if subject.startswith("Alert: "):
                subject = subject[7:]

            log_message(f"Processed subject: {subject}")

            parts = subject.split(' ')
            if len(parts) == 2:
                side = parts[0].upper()  # Buy or Sell
                symbol = parts[1].upper()  # E.g., FIOUSDT

                

                if side in ['BUY', 'SELL']:
                    log_message(f"Placing {side} order for {symbol}")
                    send_message_to_user(chat_id, f"Placing {side} order for  {symbol}")
                    place_limit_order(symbol, side)
                    mark_email_as_read(service, msg_id)
                else:
                    log_message("Invalid side received in subject.")
                    send_message_to_user(chat_id, "Invalid side received in subject.")
            else:
                log_message("Invalid subject format.")
                send_message_to_user(chat_id, "Invalid subject format.")
    except Exception as e:
        log_message(f"Error reading email: {e}")
        send_message_to_user(chat_id, f"Error reading email: {e}")


# Function to periodically check emails in a separate thread
def email_check_thread(service):
    global is_fetching_signals
    while is_fetching_signals:
        read_email_and_place_trade(service)
        time.sleep(60)  # Check every minute

# Function to handle the /start command
def start(update, context):
    global is_fetching_signals
    if not is_fetching_signals:
        is_fetching_signals = True
        gmail_service = authenticate_gmail()
        threading.Thread(target=email_check_thread, args=(gmail_service,), daemon=True).start()
        context.bot.send_message(chat_id=update.message.chat_id, text="Started fetching signals.")
    else:
        context.bot.send_message(chat_id=update.message.chat_id, text="Already fetching signals.")

# Function to handle the /stop command
def stop(update, context):
    global is_fetching_signals
    if is_fetching_signals:
        is_fetching_signals = False
        context.bot.send_message(chat_id=update.message.chat_id, text="Stopped fetching signals.")
    else:
        context.bot.send_message(chat_id=update.message.chat_id, text="Signal fetching is already stopped.")

# Define a basic /limit_order Telegram bot command handler for manual testing
def limit_order(update, context):
    chat_id = update.message.chat_id
    user_input = context.args

    if len(user_input) != 5:
        message = (
            "Usage: /limit_order <symbol> <quantity> <side> <price> [positionSide]\n"
            "`/limit_order LTCUSDT 2 BUY 66.15 LONG`\n"
            "`/limit_order LTCUSDT 2 SELL 66.5 LONG`\n"
            "`/limit_order LTCUSDT 2 BUY 66.15 SHORT\n`"
            "`/limit_order LTCUSDT 2 SELL 66.5 LONG`"
        )
        send_message_to_user(chat_id, message)
        return

    symbol = user_input[0]
    quantity = float(user_input[1])
    side = user_input[2].upper()
    price = float(user_input[3])
    position_side = user_input[4].upper() if len(user_input) > 4 else None

    if position_side is None:
        position_side = 'LONG' if side == 'BUY' else 'SHORT'

    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            type=Client.ORDER_TYPE_LIMIT,
            timeInForce=Client.TIME_IN_FORCE_GTC,
            positionSide=position_side
        )
        message = (
            f"Limit order created:\n"
            f"Symbol: `{symbol}`\n"
            f"Side: {side}\n"
            f"Quantity: {quantity}\n"
            f"Price: {price}\n"
            f"Position Side: {position_side}"
        )
        send_message_to_user(chat_id, message)
    except Exception as e:
        send_message_to_user(chat_id, f"An error occurred: {e}")

# Add handlers to Telegram bot
updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('stop', stop))
updater.dispatcher.add_handler(CommandHandler('limit_order', limit_order))

# Main function to run the bot
def main():
    gmail_service = authenticate_gmail()
    threading.Thread(target=email_check_thread, args=(gmail_service,), daemon=True).start()

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
