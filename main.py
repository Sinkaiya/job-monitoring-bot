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


async def acquire_data(message, state, table_name):
    """Checks if message is text, converts it into a list, and records it into the DB.
    """
    # If the user has sent not text but something weird, we are asking
    # to send us text only. The state the bot currently in stays the same,
    # so the bot continues to wait for user's data.
    if message.content_type != 'text':
        await message.answer(texts.only_text_warning)
        return
    # Saving the job names in the FSM storage via the update_data() method.
    await state.update_data(data_str=message.text)
    # Splitting a string into pieces, using a comma as separator and removing spaces
    data_list = re.split(r',\s*', message.text)
    db_update_result = db.add_job_names_or_stop_words(table_name, data_list)
    return db_update_result


@dp.message_handler(commands='add_job_names', state='*')
async def cmd_add_job_names(message: types.Message, state: FSMContext):
    db.add_user_if_none(message)  # checking if user doesn't exist and creating it if it doesn't
    # Putting the bot into the 'waiting_for_job_names' statement:
    await message.answer(texts.enter_job_names)
    await state.set_state(GetUserData.waiting_for_job_names.state)


# This function is being called only from the 'waiting_for_job_names' statement.
@dp.message_handler(state=GetUserData.waiting_for_job_names, content_types='any')
async def job_names_acquired(message: types.Message, state: FSMContext):
    table_name = '_'.join(['job_names', str(message.from_user.id)])
    data_acquired = await acquire_data(message, state, table_name)
    if data_acquired:
        await message.answer(texts.job_list_acquired)
    else:
        await message.answer(texts.bot_error_message)
    await state.finish()


@dp.message_handler(commands='add_stop_words', state='*')
async def cmd_add_stop_words(message: types.Message, state: FSMContext):
    db.add_user_if_none(message)  # checking if user doesn't exist and creating it if it doesn't
    # Putting the bot into the 'waiting_for_stop_words' statement:
    await message.answer(texts.enter_stop_words)
    await state.set_state(GetUserData.waiting_for_stop_words.state)


# This function is being called only from the 'waiting_for_stop_words' statement.
@dp.message_handler(state=GetUserData.waiting_for_stop_words, content_types='any')
async def stop_words_acquired(message: types.Message, state: FSMContext):
    table_name = '_'.join(['stop_words', str(message.from_user.id)])
    data_acquired = await acquire_data(message, state, table_name)
    if data_acquired:
        await message.answer(texts.stop_words_acquired)
    else:
        await message.answer(texts.bot_error_message)
    await state.finish()


@dp.message_handler(commands=['show_job_names', 'show_stop_words'])
async def show_job_names_or_stop_words(message: types.Message):
    # Setting default inline buttons which are glued to each separate message
    buttons = [
        types.InlineKeyboardButton(text="Изменить", callback_data='edit_dataset'),
        types.InlineKeyboardButton(text="Удалить", callback_data='delete_dataset')]
    table_name = str()
    db.add_user_if_none(message)  # checking if user doesn't exist and creating it if it doesn't
    telegram_id = str(message.from_user.id)

    # Checking if user's job names table is empty and warning the user about it:
    user_job_names_check = db.check_if_job_names_empty(message)
    if user_job_names_check == 'empty':
        await message.answer(texts.set_job_names_first)

    # Binding the correct commands to the buttons according to the type of data which is displayed,
    # and setting a proper table name we are acquiring the data from:
    if message.text == '/show_job_names':
        table_name = '_'.join(['job_names', telegram_id])
        buttons[0]['callback_data'] = 'edit_job_names'
        buttons[1]['callback_data'] = 'delete_job_names'
    if message.text == '/show_stop_words':
        table_name = '_'.join(['stop_words', telegram_id])
        buttons[0]['callback_data'] = 'edit_stop_words'
        buttons[1]['callback_data'] = 'delete_stop_words'

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(*buttons)
    data_str = db.get_job_names_or_stop_words(table_name)  # getting the data from the DB as a list
    # Iterating over that list and displaying each element with its own 'edit' and 'delete' buttons:
    await message.answer(data_str, reply_markup=keyboard)


# A callback handler which catches the commands from the 'edit' buttons.
@dp.callback_query_handler(lambda c: c.data.startswith('edit_'), state='*')
async def cmd_edit(callback_query: types.CallbackQuery, state: FSMContext):

    # the contents of the message which the button is glued to
    data_str_old = callback_query.message.text
    # the user's telegram id
    telegram_id = callback_query.message.chat.id
    # the name of the command the button sent, like 'edit_job_names'
    command = callback_query.data

    # Getting the id of the message we are about to edit:
    await bot.answer_callback_query(callback_query.id)

    # Telling the user what we are about to edit, and asking to enter the new one:
    await bot.send_message(telegram_id, f'Изменяем следующие данные:\n\n{data_str_old}' +
                           texts.edit_message)

    # Saving the data we are about to edit, the telegram id and the command we received
    # into the FSM storage via the update_data() method:
    await state.update_data(data_str_old=data_str_old)
    await state.update_data(telegram_id=str(telegram_id))
    await state.update_data(command=command)

    # Putting the bot into the 'waiting_for_data_to_edit' statement:
    # await state.set_state(GetUserData.waiting_for_data_to_edit.state)
    await state.set_state(GetUserData.waiting_for_data_to_edit.state)


# A callback handler which catches the commands from the 'edit' buttons.
@dp.callback_query_handler(lambda c: c.data.startswith('delete_'), state='*')
async def cmd_delete(callback_query: types.CallbackQuery, state: FSMContext):
    # the contents of the message which the button is glued to
    data_str_old = callback_query.message.text
    # the user's telegram id
    telegram_id = callback_query.message.chat.id
    # the name of the command the button sent, like 'edit_job_names'
    command = callback_query.data

    # Getting the id of the message we are about to edit:
    await bot.answer_callback_query(callback_query.id)

    # Saving the data we are about to edit, the telegram id and the command we received
    # into the FSM storage via the update_data() method:
    await state.update_data(data_str_old=data_str_old)
    await state.update_data(telegram_id=str(telegram_id))
    await state.update_data(command=command)

    # Putting the bot into the 'waiting_for_data_to_edit' statement:
    # await state.set_state(GetUserData.waiting_for_data_to_edit.state)
    await state.set_state(GetUserData.waiting_for_data_to_edit.state)


# This function is being called only from the 'waiting_for_data_to_edit' statement.
@dp.message_handler(state=GetUserData.waiting_for_data_to_edit, content_types='any')
async def edite_or_delete(message: types.Message, state: FSMContext):

    # Restoring the data details from the FSM storage:
    data_details = await state.get_data()
    print(data_details)
    data_str_old = data_details['data_str_old']
    command = data_details['command']
    print(command)
    telegram_id = data_details['telegram_id']
    table_name = '_'.join([command[5:], telegram_id])
    print(table_name)

    # Cleaning up the table:
    table_cleanup = db.clean_up_db_table(table_name)

    if table_cleanup and command.startswith('edit'):
        # Filling it with new data:
        data_acquired = await acquire_data(message, state, table_name)
        if data_acquired:
            await message.answer(f'{data_str_old}\n\nизменено на\n\n{message.text}.')
        else:
            await message.answer(texts.bot_error_message)
    elif command.startswith('delete') and table_cleanup:
        await message.answer(texts.table_cleanup_message)
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
