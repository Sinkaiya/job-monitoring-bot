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


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    if message.text.lower() == '/start':
        greeting = 'Добро пожаловать в бот.\n\n' \
                   'Первым делом нужно указать желаемую вакансию (можно несколько через запятую). ' \
                   'Стоп-слова используются для уточнения того, что искать не надо. Их тоже можно несколько.' \
                   '\n\n' \
                   'Приятного использования. :3'
        await message.answer(greeting)


async def check_if_user_exists(message):
    """A simple function which checks if we have such user in the DB already, and creating it if none.
    """
    telegram_id = message.from_user.id
    telegram_name = message.from_user.username
    full_name = message.from_user.full_name
    user_add_result = db.add_user_if_none(telegram_id, telegram_name)
    if user_add_result == 'db_created':
        await message.answer(f'Приветствуем, {fmt.hbold(full_name)}. Ваша база данных успешно '
                             f'создана. Приятного использования.', parse_mode=types.ParseMode.HTML)


@dp.message_handler(commands='add_job_names', state='*')
async def cmd_add_job_names(message: types.Message, state: FSMContext):
    await check_if_user_exists(message)
    # Putting the bot into the 'waiting_for_job_names' statement:
    await message.answer('Введите названия желаемых должностей через запятую:')
    await state.set_state(GetUserData.waiting_for_job_names.state)


# This function is being called only from the 'waiting_for_vacancy_name' statement.
@dp.message_handler(state=GetUserData.waiting_for_job_names, content_types='any')
async def job_names_acquired(message: types.Message, state: FSMContext):
    # If the user has sent not text but something weird, we are asking
    # to send us text only. The state the bot currently in stays the same,
    # so the bot continues to wait for user's idea.
    if message.content_type != 'text':
        await message.answer('Бот приемлет только текст. Попробуйте ещё раз.')
        return
    # Saving the idea in the FSM storage via the update_data() method.
    await state.update_data(user_idea=message.text)
    job_names_list = message.text.split(', ')
    telegram_id = message.from_user.id
    table_name = 'job_names_' + str(telegram_id)
    db_update_result = db.add_job_names_or_stop_words(table_name, job_names_list)
    if db_update_result:
        await message.answer('Список должностей успешно сохранён.')
        await message.answer('Введите стоп-слова - то, что вам не нужно, чтобы было в названиях вакансий:')
        await state.set_state(GetUserData.waiting_for_stop_words.state)
    else:
        await message.answer('Что-то пошло не так. Пожалуйста, попробуйте ещё раз.')
    await state.finish()


@dp.message_handler(commands='add_stop_words', state='*')
async def cmd_add_stop_words(message: types.Message, state: FSMContext):
    await check_if_user_exists(message)
    await message.answer('Введите стоп-слова - то, что вам не нужно, чтобы было в названиях вакансий:')
    await state.set_state(GetUserData.waiting_for_stop_words.state)


@dp.message_handler(state=GetUserData.waiting_for_stop_words, content_types='any')
async def stop_words_acquired(message: types.Message, state: FSMContext):
    # If the user has sent not text but something weird, we are asking
    # to send us text only. The state the bot currently in stays the same,
    # so the bot continues to wait for user's idea.
    if message.content_type != 'text':
        await message.answer('Бот приемлет только текст. Попробуйте ещё раз.')
        return
    # Saving the idea in the FSM storage via the update_data() method.
    await state.update_data(user_idea=message.text)
    stop_words_list = message.text.split(', ')
    telegram_id = message.from_user.id
    table_name = 'stop_words_' + str(telegram_id)
    db_update_result = db.add_job_names_or_stop_words(table_name, stop_words_list)
    if db_update_result:
        await message.answer('Список стоп-слов успешно сохранён.')
    else:
        await message.answer('Что-то пошло не так. Пожалуйста, попробуйте ещё раз.')
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
