import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService


def selenium_parser(job_titles_list, stop_words_list):
    """ Opens the advanced search page, fills the search fields in (including stop words),
    parses the page(s) with results and creates a dictionary like {'vacancy title': 'vacancy URL'}.

    :param job_titles_list: a list with job titles like ['"python junior"', '"python developer"'];
    it is important to wrap every title in quotes since it is the only way to make the search
    engine search full phrase instead of any word from it.
    :type job_titles_list: list

    :param stop_words_list: a list with stop words we need to exclude from search like
    ['Java', 'JavaScript', 'C++']
    :type stop_words_list: list

    :return: a dictionary with vacancies like {'vacancy title': 'vacancy URL'}
    :rtype: dict
    """

    # Setting browser settings. Making it so that it opens without a window, in the background.
    browser_options = Options()
    # browser_options.add_argument('--headless')

    # Creating a browser instance.
    browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()),
                               options=browser_options)
    browser.maximize_window()

    # Performing a request to the web-site.
    browser.get('https://spb.hh.ru/search/vacancy/advanced')

    # Finding a search form and passing search request there.
    search_input = browser.find_element(By.CSS_SELECTOR,
                                        '[data-qa="vacancysearch__keywords-input"]')
    search_input.send_keys(' OR '.join(job_titles_list))

    # Finding a form for stop words and filling it with them.
    stop_words_input = browser.find_element(By.CSS_SELECTOR,
                                            '[data-qa="vacancysearch__keywords-excluded-input"]')
    stop_words_input.send_keys(', '.join(stop_words_list))

    # Submitting search request.
    search_input.submit()

    # Creating a dictionary like {'vacancy title': 'vacancy URL'}
    # and filling it up with search results.
    vacancies_dict = dict()
    while True:
        vacancies = browser.find_elements(By.CSS_SELECTOR, '[data-qa="serp-item__title"]')
        for vacancy in vacancies:
            vacancy_url = vacancy.get_attribute('href')
            strip_position = vacancy_url.find('?')
            vacancy_url = vacancy_url[:strip_position]
            vacancies_dict[vacancy.text] = vacancy_url
        # Checking if there is more than 1 page with search results. If there are more pages,
        # we are setting the next page number and going to the next loop.
        next_page = browser.find_elements(By.CSS_SELECTOR, '[data-qa="pager-next"]')
        if len(next_page) == 1:
            next_page = next_page[0].get_attribute('href')
            browser.get(next_page)
        else:
            break

    time.sleep(3)
    browser.close()
    return vacancies_dict
