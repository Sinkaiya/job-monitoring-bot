import re
import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService


def hh_parser(jobs_list, stops_list):
    """ Opens the advanced search page, fills the search fields in (including stop words),
    parses the page(s) with results and creates a dictionary like {'vacancy title': 'vacancy URL'}.

    :param jobs_list: a list with job titles like ['"python junior"', '"python developer"'];
                      it is important to wrap every title in quotes since it is the only way
                      to make the search engine search full phrase instead of any word from it.
    :type jobs_list: list

    :param stops_list: a list with stop words we need to exclude from search like
                       ['Java', 'JavaScript', 'C++']
    :type stops_list: list

    :return: a dictionary with vacancies like {'vacancy title': 'vacancy URL'}
    :rtype: dict
    """

    # Setting the browser's settings. Making it so that it opens in the background,
    # without opening a window.
    browser_options = Options()
    # browser_options.add_argument('--headless')

    # Creating a browser instance.
    browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()),
                               options=browser_options)
    browser.maximize_window()

    # Performing a request to the web-site.
    browser.get('https://spb.hh.ru/search/vacancy/advanced')

    # Wrapping every job name in quotes because HH's search engine demands it.
    for index, job_name in enumerate(jobs_list):
        new_job_name = '\"' + job_name + '\"'
        jobs_list[index] = new_job_name

    # Finding a search form and passing search request there.
    search_input = browser.find_element(By.CSS_SELECTOR,
                                        '[data-qa="vacancysearch__keywords-input"]')
    search_input.send_keys(' OR '.join(jobs_list))

    # Finding a form for stop words and filling it with them.
    stop_words_input = browser.find_element(By.CSS_SELECTOR,
                                            '[data-qa="vacancysearch__keywords-excluded-input"]')
    stop_words_input.send_keys(', '.join(stops_list))

    # Submitting search request.
    search_input.submit()

    vacancies_count_raw = browser.find_element(By.CSS_SELECTOR,
                                               '[data-qa="vacancies-search-header"] > h1')
    vacancies_count = int(''.join(re.findall(r'(\d+)', vacancies_count_raw.text)))
    if vacancies_count > 50:
        return vacancies_count

    # Creating a dictionary like {'vacancy title': 'vacancy URL'}
    # and filling it up with the search results.
    vacancies_dict = dict()
    while True:
        vacancies = browser.find_elements(By.CSS_SELECTOR, '[data-qa="serp-item__title"]')
        for vacancy in vacancies:
            vacancy_url = vacancy.get_attribute('href')
            strip_position = vacancy_url.find('?')
            vacancy_url = vacancy_url[:strip_position]  # removing the unnecessary part of the URL
            vacancies_dict[vacancy.text] = vacancy_url
        # Checking if there is more than 1 page with search results. If there are more pages,
        # we are setting the next page number and going to the next loop.
        next_page = browser.find_elements(By.CSS_SELECTOR, '[data-qa="pager-next"]')
        print(f"len vacancies dict = {len(vacancies_dict)}")
        if len(next_page) == 1:  # this means there are some more next pages
            next_page = next_page[0].get_attribute('href')
            browser.get(next_page)
        else:
            break

    time.sleep(3)
    browser.close()
    return vacancies_dict
