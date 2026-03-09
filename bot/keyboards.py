from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


SUBSCRIBE_BUTTON_TEXT = "Подписаться ✅"
UNSUBSCRIBE_BUTTON_TEXT = "Отписаться ❎"
CURRENT_SCHEDULE_BUTTON_TEXT = "Текущее расписание 📅"

button1 = KeyboardButton(text=SUBSCRIBE_BUTTON_TEXT)
button2 = KeyboardButton(text=UNSUBSCRIBE_BUTTON_TEXT)
button3 = KeyboardButton(text=CURRENT_SCHEDULE_BUTTON_TEXT)

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[button1], [button2], [button3]],
    resize_keyboard=True,
)
