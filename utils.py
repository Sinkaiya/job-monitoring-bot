import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import NoSuchElementException

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


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

    # Submitting search request.
    search_input.submit()

    current_vacancies_dict = dict()

    while True:
        vacancies = browser.find_elements(By.CSS_SELECTOR, '[data-qa="serp-item__title"]')
        for vacancy in vacancies:
            current_vacancies_dict[vacancy.text] = vacancy.get_attribute('href')
        next_page = browser.find_elements(By.CSS_SELECTOR, '[data-qa="pager-next"]')
        if len(next_page) == 1:
            next_page = next_page[0].get_attribute('href')
            browser.get(next_page)
        else:
            break

    time.sleep(3)
    browser.close()
    return current_vacancies_dict


def selenium_parser_advanced(job_title, stop_words_list):

    # Setting browser settings. Making it so that it opens without a window, in the background.
    browser_options = Options()
    # browser_options.add_argument('--headless')

    # Creating a browser instance.
    browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=browser_options)
    browser.maximize_window()

    # Performing a request to the web-site.
    browser.get('https://spb.hh.ru/search/vacancy/advanced')

    # Finding a search form and passing search request there.
    search_input = browser.find_element(By.CSS_SELECTOR, '[data-qa="vacancysearch__keywords-input"]')
    search_input.send_keys(job_title)

    # Finding a form for stop words and filling it with them.
    stop_words_input = browser.find_element(By.CSS_SELECTOR, '[data-qa="vacancysearch__keywords-excluded-input"]')
    stop_words_input.send_keys(', '.join(stop_words_list))

    # Submitting search request.
    search_input.submit()

    # Creating the dict like {'vacancy title': 'vacancy URL'} and filling it up.
    vacancies_dict = dict()
    while True:
        vacancies = browser.find_elements(By.CSS_SELECTOR, '[data-qa="serp-item__title"]')
        for vacancy in vacancies:
            vacancy_url = vacancy.get_attribute('href')
            strip_position = vacancy_url.find('?')
            vacancy_url = vacancy_url[:strip_position]
            vacancies_dict[vacancy.text] = vacancy_url
        next_page = browser.find_elements(By.CSS_SELECTOR, '[data-qa="pager-next"]')
        if len(next_page) == 1:
            next_page = next_page[0].get_attribute('href')
            browser.get(next_page)
        else:
            break

    time.sleep(3)
    browser.close()
    return vacancies_dict


current_job_title = 'python junior'
current_stop_words = ['Java', 'JavaScript', 'C++', 'C#', '1С', 'Ruby', 'QA', 'Java Script', 'Unity']
current_jobs_dict = selenium_parser_advanced(current_job_title, current_stop_words)
print(len(current_jobs_dict))
# for k, v in current_jobs_dict.items():
#     print(k, v)
print(current_jobs_dict)
