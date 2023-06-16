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
    # waiting_for_jobs = State()
    # waiting_for_stops = State()
    waiting_for_jobs_or_stops = State()
    waiting_for_data_to_edit = State()


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    logging.info('The \'cmd_start\' function has been started.')
    if message.text.lower() == '/start':
        greeting = texts.bot_greeting
        await message.answer(greeting)
        logging.info(f'The bot started by {message.from_user.id}.')


async def acquire_data(message, state, table):
    logging.info('The \'acquire_data\' function has been started.')
    """Checks if message is text, converts it into a list, and records it into the DB table.
    """
    # If the user has sent not text but something weird, we are asking
    # to send text only. The state the bot currently in stays the same,
    # so it continues to wait for user's data.
    if message.content_type != 'text' or message.content_type.startswith('/'):
        await message.answer(texts.only_text_warning)
        return
    # Saving the data in the FSM storage via the update_data() method.
    await state.update_data(data_str=message.text)  # IS THIS NECESSARY???
    # Splitting a string into pieces, using a comma as separator and removing spaces.
    data_list = re.split(r',\s*', message.text)
    db_update_result = db.add_jobs_or_stops(table, data_list)
    return db_update_result


@dp.message_handler(commands='delete_user', state='*')
async def delete_user(message: types.Message):
    logging.info('The \'delete_user\' function has been started.')
    if db.delete_user(message.from_user.id):
        await message.answer(texts.user_deleted)
    else:
        await message.answer(texts.bot_error_message)


@dp.message_handler(commands=['add_jobs', 'add_stops'], state='*')
async def cmd_add_jobs_or_stops(message: types.Message, state: FSMContext):
    logging.info('The \'cmd_add_jobs_or_stops\' function has been started.')
    db.add_user_if_none(message)  # checking if user exists and creating it if it doesn't
    # Putting the bot into the 'waiting_for_jobs_or_stops' statement.
    command = message.get_command()
    # command = message.text
    if command == '/add_jobs':
        await message.answer(texts.add_jobs)
    if command == '/add_stops':
        await message.answer(texts.add_stops)
    await state.update_data(command=command)
    await state.set_state(GetUserData.waiting_for_jobs_or_stops.state)


@dp.message_handler(state=GetUserData.waiting_for_jobs_or_stops, content_types='any')
async def jobs_or_stops_acquired(message: types.Message, state: FSMContext):
    logging.info('The \'jobs_or_stops_acquired\' function has been started.')
    command = state.get_data('command')  # RuntimeWarning: coroutine 'FSMContext.get_data' was never awaited
    print(command)
    table = str()
    if command == '/add_jobs':
        table = '_'.join(['jobs', str(message.from_user.id)])  # Or pass only template itself
    if command == '/add_stops':
        table = '_'.join(['stops', str(message.from_user.id)])
    data_acquired = await acquire_data(message, state, table)
    if data_acquired and command == '/add_jobs':
        await message.answer(texts.jobs_list_acquired)
    if data_acquired and command == '/add_stops':
        await message.answer(texts.stops_acquired)  # NAME!!!
    else:
        await message.answer(texts.bot_error_message)
    await state.finish()


@dp.message_handler(commands=['show_jobs', 'show_stops'])
async def show_jobs_or_stops(message: types.Message):
    logging.info('The \'show_jobs_or_stops\' function has been started.')
    # Setting default inline buttons which are glued to each separate message
    buttons = [
        types.InlineKeyboardButton(text="Изменить", callback_data='edit_dataset'),
        types.InlineKeyboardButton(text="Удалить", callback_data='delete_dataset')]
    table = str()
    db.add_user_if_none(message)  # checking if user exists and creating it if it doesn't
    telegram_id = str(message.from_user.id)

    # Checking if user's job names table is empty and warning the user about it:
    user_jobs_check = db.check_if_jobs_empty(message)
    if user_jobs_check == 'empty':
        await message.answer(texts.set_jobs_first)
        return

    # Binding the correct commands to the buttons according to the type of data which is displayed,
    # and setting a proper table name we are acquiring the data from:
    if message.text == '/show_jobs':
        table = '_'.join(['jobs', telegram_id])
        buttons[0]['callback_data'] = 'edit_jobs'
        buttons[1]['callback_data'] = 'delete_jobs'
    if message.text == '/show_stops':
        table = '_'.join(['stops', telegram_id])
        buttons[0]['callback_data'] = 'edit_stops'
        buttons[1]['callback_data'] = 'delete_stops'

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(*buttons)
    # Getting the data from the DB as a string and displaying it, keyboard buttons included.
    data_str = db.get_jobs_or_stops(table)
    await message.answer(data_str, reply_markup=keyboard)


# A callback handler which catches the commands from the inline keyboard.
@dp.callback_query_handler(lambda call: call.data in ['edit_jobs', 'delete_jobs',
                                                      'edit_stops', 'delete_stops'], state='*')
async def cmd_edit_or_delete_jobs_or_stops(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info('The \'cmd_edit_or_delete_jobs_or_stops\' function has been started.')
    # The contents of the message which the button is glued .
    data_str_old = callback_query.message.text
    # The user's telegram id.
    telegram_id = callback_query.message.chat.id
    # The name of the command the button sent, like 'edit_job_names'.
    command = callback_query.data

    # Getting the id of the message we are about to edit:
    await bot.answer_callback_query(callback_query.id)

    # Showing the user the dataset we are about to edit, and asking to enter a new one:
    if command.startswith('edit'):
        await bot.send_message(telegram_id, f'Изменяем следующие данные:\n\n{data_str_old}' +
                               texts.edit_message)
    if command.startswith('delete'):
        await bot.send_message(telegram_id, f'Удаляем следующие данные:\n\n{data_str_old}')

    # Saving the data we are about to edit or delete, the telegram id
    # and the command we received into the FSM storage via the update_data() method:
    await state.update_data(data_str_old=data_str_old)
    await state.update_data(telegram_id=str(telegram_id))
    await state.update_data(command=command)

    # Putting the bot into the 'waiting_for_data_to_edit' statement:
    # await state.set_state(GetUserData.waiting_for_data_to_edit.state)
    await state.set_state(GetUserData.waiting_for_data_to_edit.state)


# This function is being called only from the 'waiting_for_data_to_edit' statement.
@dp.message_handler(state=GetUserData.waiting_for_data_to_edit, content_types='any')
async def edit_or_delete_jobs_or_stops(message: types.Message, state: FSMContext):
    logging.info('The \'edit_or_delete_jobs_or_stops\' function has been started.')
    # Restoring the data details from the FSM storage:
    data_details = await state.get_data()
    print(data_details)
    data_str_old = data_details['data_str_old']
    command = data_details['command']
    print(command)
    telegram_id = data_details['telegram_id']
    table = '_'.join([command[5:], telegram_id])
    print(table)

    # Cleaning up the table:
    table_cleanup = db.clean_up_db_table(table)

    if table_cleanup and command.startswith('edit'):
        # Filling it with new data:
        data_acquired = await acquire_data(message, state, table)
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
