import time
import os
import configparser
import logging
import aioschedule
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
import aiogram.utils.markdown as fmt
from mysql.connector import connect
import db
import utils
import texts
import re

config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8-sig')
bot_token = config.get('telegram', 'token')
admin_id = int(config.get('telegram', 'admin_id'))

logging.basicConfig(level=logging.INFO,
                    filename="jobmonitoringbot.log",
                    filemode="a",
                    format="%(asctime)s %(levelname)s %(message)s")

bot = Bot(token=bot_token)
dp = Dispatcher(bot=bot, storage=MemoryStorage())


# To keep the bot's states we need to create a class which is inherited from
# the StatesGroup class. The attributes within this class should be the instances
# of the State() class.
class GetUserData(StatesGroup):
    waiting_for_job_names = State()
    waiting_for_stop_words = State()
    waiting_for_data_to_edit = State()


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    if message.text.lower() == '/start':
        greeting = texts.bot_greeting
        await message.answer(greeting)


async def check_if_user_exists(message):
    """Checks if there is the user's record in the DB already, and creates it if none.
    """
    telegram_id = message.from_user.id
    telegram_name = message.from_user.username
    full_name = message.from_user.full_name
    user_add_result = db.add_user_if_none(telegram_id, telegram_name)
    if user_add_result == 'db_created':
        await message.answer(f'Приветствуем, {fmt.hbold(full_name)}, {texts.user_entry_created}',
                             parse_mode=types.ParseMode.HTML)


async def acquire_data(message, state, table_name):
    """Checks if message is text, converts it into a list, and records it into the DB.
    """
    # If the user has sent not text but something weird, we are asking
    # to send us text only. The state the bot currently in stays the same,
    # so the bot continues to wait for user's idea.
    if message.content_type != 'text':
        await message.answer(texts.only_text_warning)
        return
    # Saving the job names in the FSM storage via the update_data() method.
    await state.update_data(data_str=message.text)
    data_list = re.split(r',\s*', message.text)
    db_update_result = db.add_job_names_or_stop_words(table_name, data_list)
    return db_update_result


@dp.message_handler(commands='add_job_names', state='*')
async def cmd_add_job_names(message: types.Message, state: FSMContext):
    await check_if_user_exists(message)
    # Putting the bot into the 'waiting_for_job_names' statement:
    await message.answer(texts.enter_job_names)
    await state.set_state(GetUserData.waiting_for_job_names.state)


# This function is being called only from the 'waiting_for_job_names' statement.
@dp.message_handler(state=GetUserData.waiting_for_job_names, content_types='any')
async def job_names_acquired(message: types.Message, state: FSMContext):
    table_name = 'job_names_' + str(message.from_user.id)
    data_acquired = await acquire_data(message, state, table_name)
    if data_acquired:
        await message.answer(texts.job_list_acquired)
        await message.answer(texts.enter_stop_words)
        # Putting the bot into the 'waiting_for_stop_words' statement:
        await state.set_state(GetUserData.waiting_for_stop_words.state)
    else:
        await message.answer(texts.bot_error_message)
        await state.finish()


@dp.message_handler(commands='add_stop_words', state='*')
async def cmd_add_stop_words(message: types.Message, state: FSMContext):
    await check_if_user_exists(message)
    # Putting the bot into the 'waiting_for_stop_words' statement:
    await message.answer(texts.enter_stop_words)
    await state.set_state(GetUserData.waiting_for_stop_words.state)


# This function is being called only from the 'waiting_for_stop_words' statement.
@dp.message_handler(state=GetUserData.waiting_for_stop_words, content_types='any')
async def stop_words_acquired(message: types.Message, state: FSMContext):
    table_name = 'stop_words_' + str(message.from_user.id)
    data_acquired = await acquire_data(message, state, table_name)
    if data_acquired:
        await message.answer(texts.stop_words_acquired)
    else:
        await message.answer(texts.bot_error_message)
    await state.finish()


@dp.message_handler(commands=['show_job_names', 'show_stop_words'])
async def show_job_names_or_stop_words(message: types.Message):
    buttons = [
        types.InlineKeyboardButton(text="Изменить список", callback_data='edit_dataset'),
        types.InlineKeyboardButton(text="Удалить список", callback_data='delete_dataset')]
    table_name = None
    if message.text == '/show_job_names':
        table_name = 'job_names_' + str(message.from_user.id)
        buttons[0]['callback_data'] = 'edit_job_names'
        buttons[1]['callback_data'] = 'delete_job_names'
    if message.text == '/show_stop_words':
        table_name = 'stop_words_' + str(message.from_user.id)
        buttons[0]['callback_data'] = 'edit_stop_words'
        buttons[1]['callback_data'] = 'delete_stop_words'
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(*buttons)
    data = db.get_job_names_or_stop_words(table_name)
    for elem in data:
        await message.answer(elem, reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith('edit_'), state='*')
async def cmd_edit_or_delete(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, 'Введите новое:')
    data = callback_query.message.text  # программист python
    chat = callback_query.message.chat.id  # 64633225
    command = callback_query.data  # edit_job_names
    await state.update_data(data_str_old=data)
    await state.update_data(data_chat=chat)
    await state.update_data(data_command=command)
    await state.set_state(GetUserData.waiting_for_data_to_edit.state)


# This function is being called only from the 'waiting_for_data_to_edit' statement.
@dp.message_handler(state=GetUserData.waiting_for_data_to_edit, content_types='any')
async def edite_or_delete(message: types.Message, state: FSMContext):
    if message.content_type != 'text':
        await message.answer(texts.only_text_warning)
        return
    # Saving the job names in the FSM storage via the update_data() method.
    await state.update_data(data_str=message.text)
    record = message.text
    data_details = await state.get_data()  # {'data_str_old': 'программист python', 'data_chat': 64633225, 'data_command': 'edit_job_names'}
    table_name = ''.join([data_details['data_command'][5:], '_', str(data_details['data_chat'])])
    column_name = data_details['data_command'][5:-1]
    print(table_name, column_name, data_details['data_str_old'])
    # data_acquired = await acquire_data(message, state, table_name)
    data_changed = db.edit_or_delete_record(table_name, column_name, record, 'edit', data_details['data_str_old'])
    if data_changed:
        await message.answer(texts.job_list_acquired)
    else:
        await message.answer(texts.bot_error_message)
    await state.finish()


# async def scheduler():
#     aioschedule.every().day.at("09:00").do(db.)
#     while True:
#         await aioschedule.run_pending()
#         await asyncio.sleep(1)
#
#
# async def on_startup(_):
#     asyncio.create_task(scheduler())


if __name__ == '__main__':
    # executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    executor.start_polling(dp, skip_updates=True)
