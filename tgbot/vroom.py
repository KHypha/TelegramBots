import telegram
import requests
from binance.client import Client
from threading import Thread
import time
import random
from binance.enums import KLINE_INTERVAL_1MINUTE
import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from telegram import ReplyKeyboardMarkup, KeyboardButton


API_KEY = '0gtKKENzEpaVaHne81pbd4FU5UW3sgGQVM7d5EHpa50WEwD3HPLcQyvGI8syKuiV'
API_SECRET = 'LGN1vsVJJl3jhompxIxS14X00WxDKePwNTnopxMeVuYNiHUBApzmHbGINypoc92S'
#API_KEY = '5fyW0DEXWVCPOoCBRATcUsl44USDtBCovYCVNNv6LjBCjEwuH06W2L4Rc2YVwuUh'
#API_SECRET = 'C3HhLwDM88KLJlBirAVq1Yn94cP9Qu1HRGkI2qZ5ApN4sdcF1dlvHctPvAITxJkD'


client = Client(API_KEY, API_SECRET)
TELEGRAM_API_TOKEN = '6247332516:AAE8L_V1HKzNi0tpDVscKtiFhVxeyo-mu04'

symbol = 'LTCUSDT'
trade_quantity = 1
short_term_period = 10
long_term_period = 50

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
        while True:
            positions = client.futures_position_information()
            non_zero_positions = [position for position in positions if float(position['positionAmt']) != 0.0]
            
            if non_zero_positions:
                messages = format_positions(non_zero_positions)
                formatted_message = "📊 Open Positions:\n\n"
                for message in messages:
                    formatted_message += message + "\n"
                
                # Get the current time in HH:MM:SS.mmm format
                current_time = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
                modified_message = f"{formatted_message}Last Updated: {current_time}"
                
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
                
            time.sleep(1.5)  # Update every second
    
    positions_thread = Thread(target=update_positions)
    positions_thread.daemon = True  # Set as daemon thread to automatically terminate when the main program ends
    positions_thread.start()

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
    
    balances_thread = Thread(target=update_balances)
    balances_thread.daemon = True  # Set as daemon thread to automatically terminate when the main program ends
    balances_thread.start()

def format_positions(positions):
    # Fetch account information
    account_info = client.futures_account()
    unrealized_pnl = float(account_info["totalUnrealizedProfit"])
    total_balance = sum(float(balance['walletBalance']) for balance in account_info['assets']) + unrealized_pnl

    total_unrealized_pnl = sum(float(position['unRealizedProfit']) for position in positions)
    pnl_threshold = -total_balance * 0.2
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
        roe = roe if position['positionSide'] == "LONG" else 0-roe
        entry = f"{shape} {symbol} {leverage}✖️  Notional Size: {position_size}\n"
        entry += f"📌 Entry Price: {entry_price:.4f} \n 💹Mark Price: {mark_price:.4f}\n"
        entry += f"🍡 liq Price: {float(position['liquidationPrice']):.4f} \n"
        entry += f"📈 PNL: {unrealized_pnl:.4f} ({roe:.4f}%)\n\n"
        # Close the position if unrealized PNL reaches the threshold
        if unrealized_pnl <= pnl_threshold:
            close_order_side = 'SELL' if position['positionSide'] == 'LONG' else 'BUY'
            close_quantity = abs(position_size)
            # Create a market order to close the position
            order = client.futures_create_order(
                symbol=symbol,
                side=close_order_side,
                quantity=close_quantity,
                type=Client.ORDER_TYPE_MARKET,
                positionSide=position['positionSide']
            )

            entry += f"Position closed based on loss threshold."

        
        if len(formatted_message) + len(entry) <= telegram.constants.MAX_MESSAGE_LENGTH:
            formatted_message += entry
        else:
            formatted_messages.append(formatted_message)
            formatted_message = "📊 Open Positions:\n" + entry
    formatted_messages.append(formatted_message)
    return formatted_messages


def cancel_all_positions(update, context):
    chat_id = update.message.chat_id
    
    try:
        positions = client.futures_position_information()
        non_zero_positions = [position for position in positions if float(position['positionAmt']) != 0.0]

        if not non_zero_positions:
            context.bot.send_message(chat_id=chat_id, text="No open positions found.")
            return
        
        for position in non_zero_positions:
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


def calculate_max_position_size(account_balance, leverage, mark_price, percentage=0.70):
    # Calculate maximum allowed position size for both LONG and SHORT sides
    max_long_position_size = (account_balance * percentage * leverage) / mark_price
    max_short_position_size = (account_balance * percentage * leverage) / mark_price
    positions = client.futures_position_information()
    non_zero_positions = [position for position in positions if float(position['positionAmt']) != 0.0]
    used_quantity = 0
    for position in non_zero_positions:            
        used_quantity += abs(float(position['positionAmt']))

    max_long_position_size -= used_quantity
    max_short_position_size -= used_quantity
    return max_long_position_size, max_short_position_size

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

    account_info = client.futures_account()
    balances = account_info['assets']
    account_balance = sum(float(balance['walletBalance']) for balance in balances)
    leverage = 75
    price_info = client.futures_mark_price(symbol=symbol)
    mark_price = float(price_info["markPrice"])

    # Calculate the maximum position size
    max_long_position_size, _ = calculate_max_position_size(account_balance, leverage, mark_price)

    if quantity > max_long_position_size:
        context.bot.send_message(chat_id=chat_id, text=f"{account_balance} Quantity exceeds maximum position size ({max_long_position_size:.4f}). at {mark_price}")
        return

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
    account_info = client.futures_account()
    balances = account_info['assets']
    account_balance = sum(float(balance['walletBalance']) for balance in balances)
    leverage = 75
    price_info = client.futures_mark_price(symbol=symbol)
    mark_price = float(price_info["markPrice"])

    # Calculate the maximum position size
    _, max_short_position_size = calculate_max_position_size(account_balance,  leverage, mark_price)

    if quantity > max_short_position_size:
        context.bot.send_message(chat_id=chat_id, text=f"Quantity exceeds maximum position size ({max_short_position_size:.4f}).")
        return

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
                                 "/limit_order  LTCUSDT 2 SELL 66.5 SHORT")
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
        context.bot.send_message(chat_id=chat_id, text="Usage: /stop_loss <symbol> <quantity> <side> <stop_price>\n"
                                 "/stop_loss LTCUSDT 1 BUY 64.3\n"
                                 "/stop_loss LTCUSDT 1 BUY 64.3\n")
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
        context.bot.send_message(chat_id=chat_id, text="Usage: /take_profit <symbol> <quantity> <side> <stop_price>\n"
                                 "/take_profit LTCUSDT 1 BUY 64.3\n"
                                 "/take_profit LTCUSDT 1 SELL 64.3\n")
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
        context.bot.send_message(chat_id=chat_id, text="Usage: /cancel <symbol>\n"
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
