import configparser
import logging
import time

from mysql.connector import connect

config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8-sig')

logging.basicConfig(level=logging.INFO,
                    filename="jobmonitoringbot.log",
                    filemode="a",
                    format="%(asctime)s %(levelname)s %(message)s")

db_config = {'host': "127.0.0.1",
             'port': 3306,
             'user': config.get('mysql', 'user'),
             'password': config.get('mysql', 'password'),
             'database': "jobmonitoringbot"}


def connect_to_db(host, port, user, password, database):
    """Connects to a MySQL database.

    :param host: host address
    :type host: str
    :param port: port number
    :type port: int
    :param user: username
    :type user: str
    :param password: password
    :type password: str
    :param database: DB name
    :type database: str

    :return: connection
    :rtype: mysql.connector.connection
    """
    connection = None
    for attempt in range(1, 11):
        logging.info(f'Connecting to the database. Attempt {attempt} of 10...')

        try:
            connection = connect(host=host,
                                 port=port,
                                 user=user,
                                 password=password,
                                 database=database)
        except Exception as e:
            logging.error(f'An attempt to connect to the database failed: {e}', exc_info=True)
            time.sleep(5)
            continue

        if connection.is_connected():
            logging.info(f'The connection to the database established successfully.')
            break

    return connection


def create_table(create_query, table_name):
    """Creates a table which belongs to specific user and contains this user's data.

    :param create_query: MySQL query for table creation
    :type create_query: str
    :param table_name: name of the table we are creating
    :type table_name: str

    :return: True of False, depending on whether everything worked correctly
    :rtype: bool
    """
    error = False
    logging.info(f'Creating table {table_name}...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(create_query)
            connection.commit()
            logging.info(f'Table {table_name} created.')
        except Exception as e:
            logging.error(f'Attempt to create table {table_name} failed: {e}', exc_info=True)
            error = True
        finally:
            connection.close()
            logging.info(f'Connection to the database closed.')
            if error:
                return False
            else:
                return True


def add_user_if_none(telegram_id, telegram_name):
    """Checks if a user with such telegram id is present in the DB already,
        and creates a new entry if there is no such user in the DB.

    :param telegram_id: unique numeric identifier of user's telegram account
    :type telegram_id: int
    :param telegram_name: the user's telegram name (the one that starts with @)
    :type telegram_name: str

    :return: True of False, depending on whether everything worked correctly
    :rtype: bool
    """
    # Checking if user in the DB already.
    search_query = f"SELECT * FROM `users` WHERE `telegram_id` = {telegram_id};"
    connection = connect_to_db(**db_config)

    with connection.cursor() as cursor:
        try:
            logging.info(f'Checking if user {telegram_id} ({telegram_name}) exists...')
            cursor.execute(search_query)
        except Exception as e:
            logging.error(f'An attempt to check if the user {telegram_id} ({telegram_name}) '
                          f'is present in the DB already failed: {e}', exc_info=True)

        # If there is no such user in the DB, we should do the following:
        #   1. Create the user's entry.
        #   2. Create the user's table.
        #   3. Create the user's stop words table.
        if cursor.fetchone() is None:
            # 1. Creating the user's entry.
            logging.info(f'User {telegram_id} ({telegram_name}) not found. Adding user...')
            user_table = 'user_' + str(telegram_id)
            print(user_table)
            user_stop_words_table = user_table + '_stop_words'
            print(user_stop_words_table)
            insert_query = f"INSERT INTO `users` (`telegram_id`, `telegram_name`, " \
                           f"`user_table`, `user_stop_words_table`) " \
                           f"VALUES ('{telegram_id}', '{telegram_name}', '{user_table}', " \
                           f"'{user_stop_words_table}');"
            try:
                cursor.execute(insert_query)
                connection.commit()
                logging.info(f'User {telegram_id} ({telegram_name}) added to the DB.')
                # 2. Creating the user's table.
                user_table_create_query = f"CREATE TABLE IF NOT EXISTS `{user_table}` (" \
                                          f"`record_id` INT PRIMARY KEY AUTO_INCREMENT NOT NULL, " \
                                          f"`vacancy_id` INT NOT NULL) ENGINE=InnoDB;"
                create_table(user_table_create_query,user_table)
                # 3. Creating the user's stop words table.
                user_stop_words_table_create_query = f"CREATE TABLE IF NOT EXISTS " \
                                                     f"`{user_stop_words_table}` (" \
                                                     f"`stop_word_id` INT PRIMARY KEY AUTO_INCREMENT NOT NULL, " \
                                                     f"`stop_word` VARCHAR(128) NOT NULL) ENGINE=InnoDB;"
                create_table(user_stop_words_table_create_query, user_stop_words_table)
                connection.close()
                logging.info(f'Connection to the database closed.')
                return 'db_created'
            except Exception as e:
                logging.error(f'An attempt to add user {telegram_id} ({telegram_name}) '
                              f'to the DB failed: {e}', exc_info=True)
                connection.close()
                logging.info(f'Connection to the database closed.')
                return False
        else:
            logging.info(f'User {telegram_id} ({telegram_name}) exists. No action is needed.')
            connection.close()
            logging.info(f'Connection to the database closed.')
            return 'db_exists'


def add_vacancies(vacancies_dict):
    connection = connect_to_db(**db_config)

    for vacancy_name, vacancy_url in vacancies_dict.items():
        # 1. Checking if the vacancy in the db already.
        search_query = f"SELECT * FROM `vacancies` WHERE `vacancy_url` = '{vacancy_url}';"
        with connection.cursor() as cursor:
            try:
                logging.info(f'Checking if vacancy {vacancy_url} exists...')
                cursor.execute(search_query)
            except Exception as e:
                logging.error(f'An attempt to check if vacancy {vacancy_url} exists failed: {e}', exc_info=True)
            # If vacancy is not in the DB, we should add it.
            if cursor.fetchone() is None:
                insert_query = f"INSERT INTO `vacancies` (`vacancy_url`, `vacancy_name`) VALUES " \
                               f"('{vacancy_url}', '{vacancy_name}');"
                try:
                    logging.info(f'Adding vacancy {vacancy_url} to db...')
                    cursor.execute(insert_query)
                    connection.commit()
                    logging.info(f'Vacancy {vacancy_url} added to db.')
                except Exception as e:
                    logging.error(f'An attempt to add vacancy {vacancy_url} to db failed: {e}', exc_info=True)
            # If vacancy in the db already, we should pass it and move to the next one.
            else:
                continue

    connection.close()
    logging.info(f'Connection to the database closed.')

