import time
import os
import configparser
import logging

from webdriver_manager.chrome import ChromeDriverManager

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import NoSuchElementException

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
import aiogram.utils.markdown as fmt
from mysql.connector import connect


def selenium_parser(job_title):

    # Setting browser settings. Making it so that it opens without a window, in the background.
    browser_options = Options()
    # browser_options.add_argument('--headless')

    # Creating a browser instance.
    browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=browser_options)
    browser.maximize_window()

    # Performing a request to the web-site.
    browser.get('https://hh.ru')

    # Finding a search form and passing search request there.
    search_input = browser.find_element(By.ID, 'a11y-search-input')
    search_input.send_keys(job_title)

    # Находим и нажимаем кнопку Submit. Перед [] пишем название тега, внутри - название css-селектора.
    # search_button = browser.find_element(By.CSS_SELECTOR, 'button[data-qa="search-button"]')
    # search_button.click()

    # Submitting search request.
    search_input.submit()

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # vacancies_count_object = browser.find_element(By.CSS_SELECTOR, '[data-qa="vacancies-search-header"]')
    # vacancies_count_text = vacancies_count_object.text
    #
    # vacancies_count = str()
    #
    # for sym in vacancies_count_text:
    #     if sym != ' ':
    #         vacancies_count += sym
    #     else:
    #         break
    #
    # vacancies_count = int(vacancies_count)
    #
    # for vacancy in range(vacancies_count):
    #     current_vacancy_object = browser.find_element(By.CSS_SELECTOR, '[data-qa="serp-item__title"]')
    #     current_vacancy_text = current_vacancy_object.text
    #     print(vacancy, current_vacancy_text)
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    vacancies = browser.find_elements(By.CSS_SELECTOR, '[data-qa="serp-item__title"]')
    for vacancy in vacancies:
        print()
        print(vacancy.text)
        print(vacancy.get_attribute('href'))

    time.sleep(3)
    browser.close()
    # return vacancies_count_text


current_job_title = 'python junior'
selenium_parser(current_job_title)

