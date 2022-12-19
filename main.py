import time
import os

from webdriver_manager.chrome import ChromeDriverManager

from selenium import webdriver
# Позволяет конфигурировать браузер, который мы открываем:
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import NoSuchElementException

from settings import TOKEN
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters


def selenium_parser(job_title):

    # Задаём свойства браузера.
    # Делаем так, чтобы браузер открывался без открытия окна, в фоновом режиме.
    browser_options = Options()
    # path_to_driver = os.path.abspath(os.path.join('chromedriver'))
    browser_options.add_argument('--headless')

    # Создаём браузер.
    # browser = webdriver.Chrome(executable_path=path_to_driver, options=browser_options)
    browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=browser_options)
    browser.maximize_window()

    # Делаем запрос к сайту.
    browser.get('https://hh.ru')

    # Ищем форму поиска и передаём туда данные.
    search_input = browser.find_element(By.ID, 'a11y-search-input')
    search_input.send_keys(job_title)

    # Находим и нажимаем кнопку Submit. Перед [] пишем название тега, внутри - название css-селектора.
    # search_button = browser.find_element(By.CSS_SELECTOR, 'button[data-qa="search-button"]')
    # search_button.click()

    # Отправляем форму.
    search_input.submit()

    # Ищем данные с полученной страницы (количество вакансий).
    vacancies_count = browser.find_element(By.CSS_SELECTOR, '[data-qa="vacancies-search-header"]')
    v_c = vacancies_count.text

    time.sleep(3)
    browser.close()
    return v_c


# Update - класс в рамках библиотеки telegram.Update, показывающий,
# какие события получает наш handler (обработчик). Через update: Update
# мы указываем функции, какой тип данных мы ожидаем в этом аргументе.
# Второй обязательный аргумент, который мы в данном случае не используем,
# мы просто заменяем на _, чтобы не вылезала ошибка.
async def hello(update: Update, _):
    # Ищем сообщение пользователя.
    user_text = update.message.text

    # Из полученной от пользователя информации берём его имя и извлекаем оттуда first_name.
    user_nickname = update.effective_user.name
    user_first_name = update.effective_user.first_name
    user_last_name = update.effective_user.last_name
    print(f"Пользователь {user_first_name} {user_nickname} {user_last_name} отправил сообщение '{user_text}'.")

    # Отвечаем пользователю: получаем событие, видим, что это было сообщение (message),
    # и пытаемся вернуть текст (reply_text).
    await update.message.reply_text(f"Пользователь {user_first_name} {user_nickname} {user_last_name} "
                                    f"отправил сообщение '{user_text}'.")
    await update.message.reply_text("Ищу информацию...")
    try:
        # Применяем функцию с парсером.
        offers = selenium_parser(user_text)
        print(f'По запросу {user_text} результат - {offers}.')

        # Отдаём ответ.
        await update.message.reply_text(f'По запросу "{user_text}" результат: {offers}.')
    except NoSuchElementException as exc:
        # Обрабатываем некорректный запрос.
        print(f'ничего не найдено.')
        await update.message.reply_text(f'По запросу {user_text} ничего не найдено.')


def main():
    # Создаём приложение.
    app = ApplicationBuilder().token(TOKEN).build()

    # Добавляем обработчик сообщений. Фильтр - сущность в данной библиотеке, подсказывающая,
    # какого типа сообщение мы будем ждать от пользователя (текст, изображение, стикер, файл,
    # аудио (голосовое сообщение) и т.д. Вторым аргументом указывается, с помощью какой
    # функции мы будем обрабатывать сообщение.
    app.add_handler(MessageHandler(filters.TEXT, hello))

    # Запускаем бота.
    app.run_polling()


# Обеспечиваем корректный запуск файла из терминала.
if __name__ == '__main__':
    main()
