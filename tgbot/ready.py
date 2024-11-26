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
import re
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram import Update
# Initialize a set to track processed email IDs
processed_emails = set()
# Flag to control email fetching
is_fetching_signals = True


# Load environment variables from .env file
load_dotenv()
chat_id = '1068035728'

# Set up logging
logging.basicConfig(filename='trading_bot.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# API Keys
BINANCE_API_KEY = os.getenv('TWENTYK_API_KEY')
BINANCE_API_SECRET = os.getenv('TWENTYK_API_SECRET')
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
def get_realized_pnl(symbol, position_side):
    """
    Fetch the realized PnL for the most recent closed position for a given symbol and position side.
    
    Args:
        client: Binance API client instance.
        symbol (str): Trading pair symbol, e.g., 'FIOUSDT'.
        position_side (str): 'LONG' or 'SHORT'.
    
    Returns:
        float: Realized PnL in USDT, or 0.0 if no PnL is found.
    """
    try:
        # Fetch futures income history for 'REALIZED_PNL'
        income_history = client.futures_income_history(
            symbol=symbol,
            incomeType='REALIZED_PNL',
            limit=10  # Fetch the last 10 entries to ensure coverage
        )

        # Filter income history for the correct position side
        if not income_history:
            log_message(f"No realized PnL history found for {symbol} {position_side}.")
            return 0.0

        # Get the most recent entry matching the position side
        for entry in income_history:
            if entry['symbol'] == symbol:
                realized_pnl = float(entry['income'])
                log_message(f"Realized PnL for {symbol} {position_side}: {realized_pnl} USDT.")
                return realized_pnl

        log_message(f"No matching PnL found for {symbol} {position_side}.")
        return 0.0

    except Exception as e:
        log_message(f"Error fetching realized PnL: {e}")
        return 0.0

def transfer_profit_to_spot_wallet(profit, symbol, position_side, chat_id):
    """
    Transfer 30% of the profit from the futures wallet to the spot wallet.
    
    Args:
        client: Binance API client instance.
        profit (float): The profit amount in USDT.
        symbol (str): Trading pair symbol.
        position_side (str): 'LONG' or 'SHORT'.
        chat_id (int): Telegram chat ID to send notifications.
    
    Returns:
        None
    """
    try:
        if profit > 0:
            transfer_amount = profit * 0.3  # 30% of the profit
            transfer_response = client.futures_account_transfer(
                asset='USDT',  # Assuming USDT is the trading asset
                amount=transfer_amount,
                type=2  # Type 2 is for transfer from Futures to Spot
            )

            log_message(f"Transferred {transfer_amount} USDT from Futures to Spot wallet. Response: {transfer_response}")
            send_message_to_user(
                chat_id,
                f"✅ Transferred {transfer_amount} USDT from Futures to Spot wallet."
            )
        else:
            log_message(f"No profit to transfer for {symbol} {position_side}. Profit: {profit} USDT.")
            send_message_to_user(
                chat_id,
                f"No profit to transfer for {symbol} {position_side}. Total profit was {profit:.2f} USDT."
            )
    except Exception as e:
        log_message(f"Error during transfer to spot wallet: {e}")
        send_message_to_user(chat_id, f"Error transferring profit to Spot wallet: {e}")

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
            type='TRAILING_STOP_MARKET',
            activationPrice=activation_price,  # The price at which the trailing stop becomes active
            callbackRate=trailing_delta,  # Trailing stop percentage
            timeInForce=Client.TIME_IN_FORCE_GTC,
            positionSide=position_side
        )

        log_message(f"Entry order and trailing stop order created:\n{order}\n{trailing_stop_order}")
        send_order_summary(chat_id=chat_id, order=order, take_profit_order=trailing_stop_order)
        # Track the position based on its side (long or short)
        position_side = 'LONG' if side == 'BUY' else 'SHORT'

        # Monitor the position for closure and calculate PNL
        
        # Monitor the position for closure
        while True:
            position_info = client.futures_position_information(symbol=symbol)
            position = next((p for p in position_info if p['symbol'] == symbol and p['positionSide'] == position_side), None)

            if position and float(position['positionAmt']) == 0:
                # Position is closed, fetch the realized PnL
                realized_pnl = get_realized_pnl(symbol, position_side)
                pnl_status = "profit" if realized_pnl > 0 else "loss"
                send_message_to_user(
                    chat_id,
                    f"✅ Your {symbol} {position_side} position has been closed. You made a {pnl_status} of {abs(realized_pnl)} USDT!"
                )
                log_message(f"Position closed for {symbol} {position_side}, realized PNL: {realized_pnl} USDT.")
                
                # Transfer profit to spot wallet if applicable
                transfer_profit_to_spot_wallet(realized_pnl, symbol, position_side, chat_id)

                break
            else:
                log_message(f"Waiting for {position_side} position to close for {symbol}...")
                time.sleep(60)  # Wait for 60 seconds before checking again


        
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
    global is_fetching_signals, processed_emails
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
            
            # Skip already processed emails
            if msg_id in processed_emails:
                log_message(f"Email {msg_id} has already been processed. Skipping.")
                continue
            
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
                    place_limit_order(symbol, side)
                    mark_email_as_read(service, msg_id)
                    processed_emails.add(msg_id)  # Add email ID to processed set
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
def escape_markdown_v2(text):
    # Escape characters that have special meaning in Markdown
    escape_chars = r'_*[]()~>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def balances(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id

    def update_balances():
        while True:
            account_info = client.futures_account()
            balances = account_info['assets']
            unrealized_pnl = float(account_info["totalUnrealizedProfit"])
            
            total_balance = sum(float(balance['walletBalance']) for balance in balances) + unrealized_pnl
            
            message = f"💰 Total Balance: 💲{total_balance:.4f}\n\n📈 Asset Balances:\n"
            message += f"🤑 Unrealized PnL: 💲{unrealized_pnl:.4f}\n"
            for balance in balances:
                if float(balance['walletBalance']) > 0.0:
                    message += f"💳 {balance['asset']}: 💲{float(balance['walletBalance']):.4f}\n"
            
            # Get the current time in HH:MM:SS.mmm format
            current_time = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
            modified_message = f"{message}Last Updated: {current_time}"
            
            if not hasattr(context, 'last_balances_message_id'):
                message = context.bot.send_message(chat_id=chat_id, text=modified_message)
                context.last_balances_message_id = message.message_id
            else:
                context.bot.edit_message_text(chat_id=chat_id, message_id=context.last_balances_message_id, text=modified_message)

            time.sleep(5)  # Update every second
    balances_thread = threading.Thread(target=update_balances)
    balances_thread.daemon = True  # Set as daemon thread to automatically terminate when the main program ends
    balances_thread.start()

def limit_order(update, context):
    chat_id = update.message.chat_id
    user_input = context.args

    if len(user_input) != 5:
        message = (
            "Usage: /limit_order <symbol> <quantity> <side> <price> [positionSide]\n"
            "`/limit_order LTCUSDT 2 BUY 66.15 LONG`\n"
            "`/limit_order LTCUSDT 2 SELL 66.5 LONG`\n"
            "`/limit_order LTCUSDT 2 BUY 66.15 SHORT`\n"
            "`/limit_order LTCUSDT 2 SELL 66.5 SHORT`"
        )
        send_message_to_user(chat_id, escape_markdown_v2(message), parse_mode='MarkdownV2')
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
            f"Symbol: `{escape_markdown_v2(symbol)}`\n"
            f"Side: {escape_markdown_v2(side)}\n"
            f"Quantity: {quantity}\n"
            f"Price: {price}\n"
            f"Position Side: {escape_markdown_v2(position_side)}"
        )
        send_message_to_user(chat_id, message, parse_mode='MarkdownV2')
    except Exception as e:
        send_message_to_user(chat_id, f"An error occurred: {e}")

# Add handlers to Telegram bot
updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('stop', stop))
updater.dispatcher.add_handler(CommandHandler('limit_order', limit_order))
updater.dispatcher.add_handler(CommandHandler('balances', balances))


# Main function to run the bot
def main():
    gmail_service = authenticate_gmail()
    threading.Thread(target=email_check_thread, args=(gmail_service,), daemon=True).start()

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
