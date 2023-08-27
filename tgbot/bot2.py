import telebot
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

API_TOKEN = "6655743456:AAGGwfcD5Haosk9v9z_G78GN-wsh5ILYFZI"
bot = telebot.TeleBot(API_TOKEN, parse_mode=None)

def get_daily_horoscope(sign: str, day: str) -> dict:
    url = "https://horoscope-app-api.vercel.app/api/v1/get-horoscope/daily"
    params = {"sign": sign, "day": day}
    response = requests.get(url, params)
    return response.json()

@bot.message_handler(commands=['Greet'])
def greet(message):
    bot.reply_to(message, "Hey! How's it going?")

@bot.message_handler(commands=['start', 'hello'])
def send_welcome(message):
    bot.reply_to(message, "Howdy, how are you doing?")

@bot.message_handler(commands=['horoscope'])
def ask_for_sign(message):
    keyboard = InlineKeyboardMarkup(row_width=3)
    zodiac_signs = [
        "Aries", "Taurus", "Gemini", "Cancer",
        "Leo", "Virgo", "Libra", "Scorpio",
        "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]
    buttons = [InlineKeyboardButton(sign, callback_data=sign) for sign in zodiac_signs]
    keyboard.add(*buttons)
    
    bot.send_message(
        message.chat.id,
        "Please select your zodiac sign:",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: True)
def ask_for_day(call):
    sign = call.data
    text = (
        "What day do you want to know?\n"
        "Choose one: TODAY, TOMORROW, YESTERDAY, or a date in format YYYY-MM-DD."
    )
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    bot.register_next_step_handler(call.message, show_horoscope, sign)

def show_horoscope(message, sign):
    day = message.text
    horoscope = get_daily_horoscope(sign, day)
    data = horoscope["data"]
    horoscope_message = (
        f'Horoscope: {data["horoscope_data"]}\n'
        f'Sign: {sign}\n'
        f'Day: {data["date"]}'
    )
    bot.send_message(message.chat.id, "Here's your horoscope!")
    bot.send_message(message.chat.id, horoscope_message)

bot.polling()
