import telegram
import requests
from binance.client import Client
from threading import Thread
import time
import random
from binance.enums import KLINE_INTERVAL_1MINUTE

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from telegram import ReplyKeyboardMarkup, KeyboardButton

import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

API_KEY = os.getenv('TRADING_API_KEY')
API_SECRET = os.getenv('TRADING_API_SECRET')

TELEGRAM_API_TOKEN = os.getenv('PORTFOLIO_TOKEN')


client = Client(API_KEY, API_SECRET)

def start(update: Update, context: CallbackContext):
    custom_keyboard = [
        [KeyboardButton('/positions'), KeyboardButton('/balances')],
        [KeyboardButton('/long'), KeyboardButton('/short')],
        [KeyboardButton('/limit_order'), KeyboardButton('/cancel')],
        [KeyboardButton('/close'), KeyboardButton('/display_orders')],
        [KeyboardButton('/stop_loss'), KeyboardButton('/take_profit')],
        [KeyboardButton('/cancel_all_positions'),KeyboardButton('/cancel_all_orders')]
    ]
    reply_markup = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True)
    
    start_message = (
        "Welcome to your Binance bot! Here are the available commands:\n\n"
        "📊 /positions - Display your open positions\n"
        "💰 /balances - Check your account balances\n"
        "📈 /long <symbol> <quantity> - Open a long position\n"
        "🔻 /short <symbol> <quantity> - Open a short position\n"
        "🛒 /limit_order <symbol> <quantity> <side> <price> [positionSide] - Place a limit order\n"
        "❌ /cancel <symbol> - Cancel an open order\n"
        "❌ /cancel_all_positions - Cancel all open positions\n"
        "🔒 /close <symbol> <quantity> <position_side> - Close a position\n"
        "📜 /display_orders - Display your open orders\n"
        "💸 /transfer <asset> <quantity> <from_account> <to_account> - Transfer assets between accounts\n"
        "🛑 /stop_loss <symbol> <quantity> <side> <stop_price> <limit_price> - Place a stop-limit order\n"
        "⏹️ /take_profit <symbol> <quantity> <side> <stop_price> - Place a stop-market order\n"
    )
    
    update.message.reply_text(
        start_message,
        reply_markup=reply_markup,
        parse_mode=telegram.ParseMode.MARKDOWN
    )


def handle_callback(update, context):
    query = update.callback_query
    chat_id = query.message.chat_id
    data = query.data.split("__")  # Split the callback data into symbol and order ID
    symbol = data[0]
    order_id = int(data[1])
    
    try:
        cancelled_order = client.futures_cancel_order(symbol=symbol, orderId=order_id)
        context.bot.send_message(chat_id=chat_id, text=f"Order {order_id} for {symbol} has been cancelled.")
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")


def positions(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id

    def update_positions():
        count = 0  # Initialize a counter for message content modification
        while True:
            positions = client.futures_position_information()
            non_zero_positions = [position for position in positions if float(position['positionAmt']) != 0.0]
            
            if non_zero_positions:
                messages = format_positions(non_zero_positions)
                formatted_message = "📊 Open Positions:\n\n"
                for message in messages:
                    formatted_message += message + "\n"
                
                # Modify the message content slightly by appending the count
                modified_message = f"{formatted_message}{count}"
                
                # Store the last message ID in the context
                if not hasattr(context, 'last_positions_message_id'):
                    message = context.bot.send_message(chat_id=chat_id, text=modified_message)
                    context.last_positions_message_id = message.message_id
                else:
                    context.bot.edit_message_text(chat_id=chat_id, message_id=context.last_positions_message_id, text=modified_message)
            else:
                # If no open positions
                no_positions_message = "📊 You have no open positions."
                
                if hasattr(context, 'last_positions_message_id'):
                    context.bot.edit_message_text(chat_id=chat_id, message_id=context.last_positions_message_id, text=no_positions_message)
                else:
                    message = context.bot.send_message(chat_id=chat_id, text=no_positions_message)
                    context.last_positions_message_id = message.message_id
            
            count += 1  # Increment the count
            time.sleep(1.5)  # Update every second

    positions_thread = Thread(target=update_positions)
    positions_thread.daemon = True  # Set as daemon thread to automatically terminate when the main program ends
    positions_thread.start()

def balances(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id

    def update_balances():
        count = 0  # Initialize a counter for message content modification
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
            
            # Modify the message content slightly by appending the count
            modified_message = f"{message}{count}"
            
            # Store the last message ID in the context
            if not hasattr(context, 'last_balances_message_id'):
                message = context.bot.send_message(chat_id=chat_id, text=modified_message)
                context.last_balances_message_id = message.message_id
            else:
                context.bot.edit_message_text(chat_id=chat_id, message_id=context.last_balances_message_id, text=modified_message)

            count += 1  # Increment the count
            time.sleep(5)  # Update every second

    balances_thread = Thread(target=update_balances)
    balances_thread.daemon = True  # Set as daemon thread to automatically terminate when the main program ends
    balances_thread.start()

from binance.client import Client

# Assuming the get_symbol_precision function is defined here
def get_symbol_precision(symbol):
    try:
        # Fetch exchange info
        exchange_info = client.futures_exchange_info()
        symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == symbol), None)
        
        if symbol_info is None:
            print(f"Symbol {symbol} not found.")
            return None
        
        # Get the price and quantity precision
        price_precision = symbol_info['pricePrecision']
        quantity_precision = symbol_info['quantityPrecision']
        
        return price_precision, quantity_precision
    except Exception as e:
        print(f"Error fetching symbol precision: {e}")
        return None

def format_positions(positions):
    # Fetch account information
    account_info = client.futures_account()
    unrealized_pnl = float(account_info["totalUnrealizedProfit"])
    total_balance = sum(float(balance['walletBalance']) for balance in account_info['assets']) + unrealized_pnl

    total_unrealized_pnl = sum(float(position['unRealizedProfit']) for position in positions)
    
    formatted_messages = []
    formatted_message = ""
    
    # Display total unrealized PnL and total balance
    formatted_message += f"Total Unrealized PnL: {total_unrealized_pnl:.4f}\n"
    formatted_message += f"Total Balance: {total_balance:.4f}\n\n"

    for position in positions:
        symbol = position['symbol']
        unrealized_pnl = float(position['unRealizedProfit'])
        entry_price = float(position['entryPrice'])
        mark_price = float(position['markPrice'])
        position_size = float(position['positionAmt'])
        leverage = float(position['leverage'])
        roe = (((mark_price - entry_price) / entry_price) * 100) * leverage 
        shape = "🟢" if position['positionSide'] == "LONG" else "🔴"
        roe = roe if position['positionSide'] == "LONG" else 0 - roe

        # Fetch the price and quantity precision for the symbol
        precision = get_symbol_precision(symbol)
        if precision:
            price_precision, quantity_precision = precision
        else:
            # Default to 2 decimal places if the precision could not be fetched
            price_precision = 2
            quantity_precision = 0

        # Format prices and quantities according to their precision
        entry_price_formatted = f"{entry_price:.{price_precision}f}"
        mark_price_formatted = f"{mark_price:.{price_precision}f}"
        liquidation_price_formatted = f"{float(position['liquidationPrice']):.{price_precision}f}"
        position_size_formatted = f"{position_size:.{quantity_precision}f}"

        entry = f"{shape} {symbol} {leverage}✖️  Notional Size: {position_size_formatted}\n"
        entry += f"📌 Entry Price: {entry_price_formatted} \n 💹Mark Price: {mark_price_formatted}\n"
        entry += f"🍡 liq Price: {liquidation_price_formatted} \n"
        entry += f"📈 PNL: {unrealized_pnl:.4f} ({roe:.4f}%)\n\n"

        if len(formatted_message) + len(entry) <= telegram.constants.MAX_MESSAGE_LENGTH:
            formatted_message += entry
        else:
            formatted_messages.append(formatted_message)
            formatted_message = "📊 Open Positions:\n" + entry
    formatted_messages.append(formatted_message)
    return formatted_messages

def open_long(update, context):
    chat_id = update.message.chat_id
    user_input = context.args

    if len(user_input) != 2:
        message = "Usage: /long <symbol> <quantity>"
        message += "\n/long LTCUSDT 2"
        context.bot.send_message(chat_id=chat_id, text=message)
        return

    symbol = user_input[0]
    quantity = float(user_input[1])
    position_side = "LONG"  # Set position side to LONG

    try:
        # Create the long position
        order = client.futures_create_order(
            symbol=symbol,
            side=Client.SIDE_BUY,
            quantity=quantity,
            type=Client.ORDER_TYPE_MARKET,
            positionSide=position_side
        )

        context.bot.send_message(chat_id=chat_id, text=f"Hedge long position opened:\nSymbol: {symbol}\nQuantity: {quantity}\nPosition Side: {position_side}")
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")

def cancel_all_positions(update, context):
    chat_id = update.message.chat_id
    
    try:
        positions = client.futures_position_information()
        if not positions:
            context.bot.send_message(chat_id=chat_id, text="No open positions found.")
            return
        
        for position in positions:
            symbol = position['symbol']
            position_side = position['positionSide']
            order_side = "SELL" if position_side == "LONG" else "BUY"
            quantity = abs(float(position['positionAmt']))
            
            order = client.futures_create_order(
                symbol=symbol,
                side=order_side,
                quantity=quantity,
                type=Client.ORDER_TYPE_MARKET,
                positionSide=position_side
            )
        
        context.bot.send_message(chat_id=chat_id, text="All open positions have been canceled.")
    
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")

def cancel_all_orders(update, context):
    chat_id = update.message.chat_id
    
    try:
        orders = client.futures_get_open_orders()
        if not orders:
            context.bot.send_message(chat_id=chat_id, text="No open orders found.")
            return
        
        for order in orders:
            order_symbol = order['symbol']
            order_id = order['orderId']
            try:
                cancelled_order = client.futures_cancel_order(symbol=order_symbol, orderId=order_id)
                context.bot.send_message(chat_id=chat_id, text=f"Order {order_id} for {order_symbol} has been cancelled.")
            except Exception as e:
                context.bot.send_message(chat_id=chat_id, text=f"An error occurred while cancelling order {order_id} for {order_symbol}: {e}")
        
        context.bot.send_message(chat_id=chat_id, text="All open orders have been cancelled.")
    
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")


def open_short(update, context):
    chat_id = update.message.chat_id
    user_input = context.args

    if len(user_input) != 2:
        message = "Usage: /short <symbol> <quantity>"
        message += "\n/short LTCUSDT 1"
        context.bot.send_message(chat_id=chat_id, text=message)
        return

    symbol = user_input[0]
    quantity = float(user_input[1])
    position_side = "SHORT"  # Set position side to SHORT

    try:
        # Create the short position
        order = client.futures_create_order(
            symbol=symbol,
            side=Client.SIDE_SELL,
            quantity=quantity,
            type=Client.ORDER_TYPE_MARKET,
            positionSide=position_side
        )

        context.bot.send_message(chat_id=chat_id, text=f"Hedge short position opened:\nSymbol: {symbol}\nQuantity: {quantity}\nPosition Side: {position_side}")
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")

def close_position(update, context):
    chat_id = update.message.chat_id
    user_input = context.args
    if len(user_input) != 3:
        context.bot.send_message(chat_id=chat_id, text="Usage: /close <symbol> <quantity> <position_side>\n"
                                 "/close LTCUSDT 1 LONG\n"
                                 "/close LTCUSDT 1 SHORT")
        return
    
    symbol = user_input[0]
    quantity = float(user_input[1])
    position_side = user_input[2].upper()  # 'LONG' or 'SHORT'
    
    try:
        positions = client.futures_position_information(symbol=symbol)
        if not positions:
            context.bot.send_message(chat_id=chat_id, text="No positions found for the provided symbol.")
            return
        
        position_to_close = None
        for position in positions:
            if position['positionSide'] == position_side:
                position_to_close = position
                break
        
        if not position_to_close:
            context.bot.send_message(chat_id=chat_id, text=f"No {position_side} position found for the provided symbol.")
            return
        
        # Determine the order side based on the position's side
        if position_side == 'LONG':
            order_side = "SELL"
        else:
            order_side = "BUY"
        
        order = client.futures_create_order(
            positionSide=position_side,
            symbol=symbol,
            side=order_side,
            quantity=quantity,
            type=Client.ORDER_TYPE_MARKET
        )
        
        context.bot.send_message(chat_id=chat_id, text=f"Hedge position closed:\nSymbol: {symbol}\nQuantity: {quantity}\nPosition Side: {position_side}")
    
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")

def limit_order(update, context):
    chat_id = update.message.chat_id
    user_input = context.args

    if len(user_input) != 5:
        context.bot.send_message(chat_id=chat_id, text="Usage: /limit_order <symbol> <quantity> <side> <price> [positionSide]\n"
                                 "/limit_order LTCUSDT 2 BUY 66.15 LONG\n"
                                 "/limit_order  LTCUSDT 2 SELL 66.5 LONG\n"
                                 "/limit_order  LTCUSDT 2 BUY 66.15 SHORT\n"
                                 "/limit_order  LTCUSDT 2 SELL 66.5 LONG")
        return

    symbol = user_input[0]
    quantity = float(user_input[1])
    side = user_input[2].upper()  # 'BUY' or 'SELL'
    price = float(user_input[3])
    position_side = user_input[4].upper() if len(user_input) > 4 else None  # Optional 'LONG' or 'SHORT'

    # If positionSide is not provided, use 'BUY' for long and 'SELL' for short
    if position_side is None:
        position_side = 'LONG' if side == 'BUY' else 'SHORT'

    try:
        # Create the limit order
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            type=Client.ORDER_TYPE_LIMIT,
            timeInForce=Client.TIME_IN_FORCE_GTC,
            positionSide=position_side
        )

        context.bot.send_message(chat_id=chat_id, text=f"Limit order created:\nSymbol: {symbol}\nSide: {side}\nQuantity: {quantity}\nPrice: {price}\nPosition Side: {position_side}")
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")

def stop_loss(update, context):
    chat_id = update.message.chat_id
    user_input = context.args

    if len(user_input) != 4:
        context.bot.send_message(chat_id=chat_id, text="Usage: /stop_loss <symbol> <quantity> <side> <stop_price>"
                                 "/stop_loss LTCUSDT 1 BUY 64.3"
                                 "/stop_loss LTCUSDT 1 BUY 64.3")
        return

    symbol = user_input[0]
    quantity = float(user_input[1])
    side = user_input[2].upper()  # 'BUY' or 'SELL'
    stop_price = float(user_input[3])
    position_side = 'LONG' if side == 'SELL' else 'SHORT'

    try:
        # Create the stop loss order
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            stopPrice=stop_price,
            type=Client.FUTURE_ORDER_TYPE_STOP_MARKET,
            timeInForce=Client.TIME_IN_FORCE_GTC,
            positionSide=position_side
        )

        context.bot.send_message(chat_id=chat_id, text=f"Stop-limit order created:\nSymbol: {symbol}\nSide: {side}\nQuantity: {quantity}\nStop Price: {stop_price}")
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")

def take_profit(update, context):
    chat_id = update.message.chat_id
    user_input = context.args

    if len(user_input) != 4:
        context.bot.send_message(chat_id=chat_id, text="Usage: /take_profit <symbol> <quantity> <side> <stop_price>"
                                 "/take_profit LTCUSDT 1 BUY 64.3"
                                 "/take_profit LTCUSDT 1 SELL 64.3")
        return

    symbol = user_input[0]
    quantity = float(user_input[1])
    side = user_input[2].upper()  # 'BUY' or 'SELL'
    stop_price = float(user_input[3])
    position_side = 'LONG' if side == 'SELL' else 'SHORT'
    try:
        # Create the take profit order
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            stopPrice=stop_price,
            type=Client.FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
            timeInForce=Client.TIME_IN_FORCE_GTC,
            positionSide=position_side
        )

        context.bot.send_message(chat_id=chat_id, text=f"Stop-market order created:\nSymbol: {symbol}\nSide: {side}\nQuantity: {quantity}\nStop Price: {stop_price}")
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")

def display_orders(update, context):
    chat_id = update.message.chat_id
    
    try:
        orders = client.futures_get_open_orders()
        
        if not orders:
            context.bot.send_message(chat_id=chat_id, text="No open orders found.")
            return
        
        orders_text = "Open orders:\n"
        for order in orders:
            orders_text += f"Symbol: {order['symbol']}, Side: {order['side']}, Quantity: {order['origQty']}, Price: {order['price']}\n"
        
        context.bot.send_message(chat_id=chat_id, text=orders_text)
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")

def cancel_order(update, context):
    chat_id = update.message.chat_id
    user_input = context.args
    if len(user_input) != 1:
        context.bot.send_message(chat_id=chat_id, text="Usage: /cancel <symbol>"
                                 "/cancel LTCUSDT")
        return
    
    symbol = user_input[0]
    
    try:
        orders = client.futures_get_open_orders(symbol=symbol)
        if not orders:
            context.bot.send_message(chat_id=chat_id, text="No open orders found for the provided symbol.")
            return
        
        keyboard = []
        for order in orders:
            order_details = f"{order['side']} {order['origQty']} {order['symbol']} @ {order['price']}"
            callback_data = f"{symbol}__{order['orderId']}"  # Include symbol in callback data
            keyboard.append([InlineKeyboardButton(order_details, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=chat_id, text="Select an order to cancel:", reply_markup=reply_markup)
        
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")

def transfer(update, context):
    chat_id = update.message.chat_id
    user_input = context.args

    if len(user_input) != 4:
        context.bot.send_message(chat_id=chat_id, text="Usage: /transfer <asset> <quantity> <from_account> <to_account>")
        return

    asset = user_input[0]
    quantity = float(user_input[1])
    from_account = user_input[2].lower()  # 'spot', 'funding', 'usdm'
    to_account = user_input[3].lower()  # 'spot', 'funding', 'usdm'

    try:
        if from_account == 'spot':
            # Simulate transferring from Spot to Funding or USD-M Futures
            if to_account == 'funding' or to_account == 'usdm':
                order_side = 'SELL' if to_account == 'funding' else 'SELL'
                order_type = 'LIMIT'
                order_response = client.futures_create_order(
                    symbol=f"{asset}USDT",
                    side=order_side,
                    type=order_type,
                    timeInForce='GTC',  # Good till canceled
                    quantity=quantity,
                    price=1.0,  # Adjust the price as needed
                )
                if order_response:
                    context.bot.send_message(chat_id=chat_id, text=f"Asset transfer initiated: {quantity} {asset} from {from_account} to {to_account}.")
                else:
                    context.bot.send_message(chat_id=chat_id, text="Asset transfer failed.")
            else:
                context.bot.send_message(chat_id=chat_id, text="Invalid 'to_account' specified.")
        else:
            context.bot.send_message(chat_id=chat_id, text="Currently, only transfers from Spot account are supported.")
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text=f"An error occurred: {e}")

def main():
    updater = Updater(token=TELEGRAM_API_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("positions", positions))
    dp.add_handler(CommandHandler("balances", balances))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    dp.add_handler(CommandHandler("long", open_long, pass_args=True))
    dp.add_handler(CommandHandler("short", open_short, pass_args=True))
    dp.add_handler(CommandHandler("stop_loss", stop_loss, pass_args=True))
    dp.add_handler(CommandHandler("take_profit", take_profit, pass_args=True))
    dp.add_handler(CommandHandler("close", close_position, pass_args=True))
    dp.add_handler(CommandHandler("cancel", cancel_order, pass_args=True))
    dp.add_handler(CommandHandler("limit_order", limit_order, pass_args=True))
    dp.add_handler(CommandHandler("display_orders", display_orders))
    dp.add_handler(CommandHandler("transfer", transfer, pass_args=True))
    dp.add_handler(CommandHandler("cancel_all_orders", cancel_all_orders))
    dp.add_handler(CommandHandler("cancel_all_positions", cancel_all_positions))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
