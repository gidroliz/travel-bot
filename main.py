import asyncio
import logging
from random import choice
import sys
from aiogram import F, Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup
from aiogram.enums.parse_mode import ParseMode
from aiogram.exceptions import TelegramBadRequest
from configparser import ConfigParser
import openai
from dotenv import dotenv_values

secrets = dotenv_values(".env")

openai.api_key = secrets.get("API_KEY")

bot = Bot(token=secrets.get("TOKEN"))
dp = Dispatcher()

config = ConfigParser()
config.read("config.ini", encoding="utf-8")


# Генератор клавиатуры, row_size - сколько кнопок в строке клавиатуры
def get_keyboard(row_size=1, buttons_list="KB", callbacks_list="callback"):
    buttons = []
    temp = []
    for button in config.items(buttons_list):  # цикл по кнопкам из конфга
        temp.append(
            types.InlineKeyboardButton(
                text=button[1],
                callback_data=config.get(callbacks_list, button[0]),
            )
        )
        if len(temp) == row_size:
            buttons.append(temp.copy())
            temp.clear()
    else:
        if temp:
            buttons.append(temp)
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

# функция, фильтрующая недопустимые html-теги в ответе нейросети
def filter_tags(text):
    not_allowed_tags=['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'li', 'img', 'div', 'table', 'tr', 'th', 'td', 'form', 'input', 'textarea', 'button', 'br', 'hr']
    for tag in not_allowed_tags:
        text=text.replace(f'<{tag}>','')
        text=text.replace(f'</{tag}>','')
    return text

# Обработчик запроса к ChatGPT
async def get_response(prompt: str, message: str) -> str:
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": message},
    ]
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o", messages=messages, temperature=0.2)
        return response.choices[0].message["content"]
    except:
        return "error"


# Обработчик команды /start
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(config.get("texts", "welcome"), reply_markup=get_keyboard())


# Обработчик инлайн кнопок
@dp.callback_query()
async def process_callback(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    message = callback_query.message
    callbacks = dict(config.items("callback"))
    button = [key for key, value in callbacks.items() if value == data][0]
    await state.set_data({"chat": message.chat.id, "data": data})
    await message.answer(config.get("answer", button))
    await callback_query.answer()


# Обработчик сообщений с текстом
@dp.message(F.text)
async def handle_message(message: types.Message, state: FSMContext):
    text = message.text
    if text.startswith("/"):
        await message.reply(config.get("texts", "use_buttons"))
    else:
        state_data = await state.get_data()
        data = state_data.get("data")
        if data:
            callbacks = dict(config.items("callback"))
            button = [key for key, value in callbacks.items()
                      if value == data][0]
            prompt = config.get("prompts", button)
            await message.reply(choice(list(config.items("wait")))[1])
            try:
                bot_response = await get_response(prompt, text)
                if bot_response != "error":
                    bot_response=filter_tags(bot_response)
                    await message.reply(
                        bot_response,
                        reply_markup=get_keyboard(),
                        parse_mode=ParseMode("HTML"),
                    )
                else:
                    # если при запросе к GPT возникла ошибка
                    raise TelegramBadRequest('getMe', 'Error in ChatGPT request')
            except TelegramBadRequest as e:
                logging.error(e.message)
                await message.reply(
                    config.get("texts", "error"), reply_markup=get_keyboard()
                )


# Запуск процесса поллинга новых апдейтов
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
