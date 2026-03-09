from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


button1 = KeyboardButton(text="Подписаться ✅")
button2 = KeyboardButton(text="Отписаться ❎")

MAIN_KEYBOARD = ReplyKeyboardMarkup(keyboard=[[button1], [button2]], resize_keyboard=True)
