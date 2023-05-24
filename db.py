import configparser
import logging
from datetime import date
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
        #   2. Create a table with user's vacancies.
        #   3. Create a table with user's job names.
        #   4. Create a table with user's stop words.
        if cursor.fetchone() is None:
            # 1. Creating the user's entry.
            logging.info(f'User {telegram_id} ({telegram_name}) not found. Adding user...')
            user_vacancies = 'vacancies_' + str(telegram_id)
            user_job_names = 'job_names_' + str(telegram_id)
            user_stop_words = 'stop_words_' + str(telegram_id)
            insert_query = f"INSERT INTO `users` (`telegram_id`, `telegram_name`, " \
                           f"`user_vacancies`, `user_job_names`, `user_stop_words`) " \
                           f"VALUES ('{telegram_id}', '{telegram_name}', '{user_vacancies}', " \
                           f"'{user_job_names}', '{user_stop_words}');"
            try:
                cursor.execute(insert_query)
                connection.commit()
                logging.info(f'User {telegram_id} ({telegram_name}) added to the DB.')
                # 2. Creating a table with user's vacancies.
                user_vacancies_create_query = f"CREATE TABLE IF NOT EXISTS `{user_vacancies}` (" \
                                              f"`vacancy_id` INT UNSIGNED PRIMARY KEY AUTO_INCREMENT NOT NULL, " \
                                              f"`vacancy_url` VARCHAR(256) NOT NULL, " \
                                              f"`vacancy_name` VARCHAR(512) NOT NULL, " \
                                              f"`vacancy_date` DATE NOT NULL, " \
                                              f"`is_sent_to_user` TINYINT NOT NULL) ENGINE=InnoDB;"
                create_table(user_vacancies_create_query, user_vacancies)
                # 3. Creating a table with user's job names.
                user_job_names_create_query = f"CREATE TABLE IF NOT EXISTS `{user_job_names}` (" \
                                              f"`job_name_id` INT UNSIGNED PRIMARY KEY AUTO_INCREMENT NOT NULL, " \
                                              f"`job_name` VARCHAR(128) NOT NULL) ENGINE=InnoDB;"
                create_table(user_job_names_create_query, user_job_names)
                # 4. Creating a table with user's stop words.
                user_stop_words_create_query = f"CREATE TABLE IF NOT EXISTS `{user_stop_words}` (" \
                                               f"`stop_word_id` INT UNSIGNED PRIMARY KEY AUTO_INCREMENT NOT NULL, " \
                                               f"`stop_word` VARCHAR(128) NOT NULL) ENGINE=InnoDB;"
                create_table(user_stop_words_create_query, user_stop_words)
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


def add_vacancies(user_table_name, vacancies_dict):
    """
    Adds new vacancies into the DB.

    :param user_table_name: a name of the user's table which stores the vacancies found upon user's request
    :type user_table_name: str
    :param vacancies_dict: a dictionary which contains vacancies: looks like {'vacancy_name': 'vacancy_url'}
    :type vacancies_dict: dict

    :return: True of False, depending on whether everything worked correctly
    :rtype: bool
    """
    connection = connect_to_db(**db_config)
    error = False

    for vacancy_name, vacancy_url in vacancies_dict.items():
        # 1. Checking if the vacancy in the db already.
        search_query = f"SELECT * FROM `{user_table_name}` WHERE `vacancy_url` = '{vacancy_url}';"
        with connection.cursor() as cursor:
            try:
                logging.info(f'Checking if vacancy {vacancy_url} exists in {user_table_name} table...')
                cursor.execute(search_query)
            except Exception as e:
                logging.error(f'An attempt to check if vacancy {vacancy_url} exists '
                              f'in {user_table_name} table failed: {e}', exc_info=True)
                error = True
            # If vacancy is not in the DB, we should add it.
            if cursor.fetchone() is None:
                insert_query = f"INSERT INTO `{user_table_name}` (`vacancy_url`, `vacancy_name`, " \
                               f"`vacancy_date`, `is_sent_to_user`) VALUES " \
                               f"('{vacancy_url}', '{vacancy_name}', '{date.today()}', '0');"
                try:
                    logging.info(f'Adding vacancy {vacancy_url} to {user_table_name} table...')
                    cursor.execute(insert_query)
                    connection.commit()
                    logging.info(f'Vacancy {vacancy_url} added to {user_table_name} table.')
                except Exception as e:
                    logging.error(f'An attempt to add vacancy {vacancy_url} '
                                  f'to {user_table_name} failed: {e}', exc_info=True)
                    error = True
            # If vacancy in the db already, we should pass it and move to the next one.
            else:
                continue

    connection.close()
    logging.info(f'Connection to the database closed.')
    if error:
        return False
    else:
        return True



def update_db(table_name, data_field, data, telegram_id=None):
    """Updates the data in the DB, depending on the `data_field` parameter.

    :param table_name: name of the DB table we are about to update
    :type table_name: str
    :param telegram_id: the id of the user in the DB table
    :type telegram_id: str or int
    :param data_field: field of the table that should be updated
    :type data_field: str
    :param data: the data that should be written into the specific field of the table
    :type data: str

    :return: True of False, depending on whether everything worked correctly
    :rtype: bool
    """
    error = False
    if "'" in str(data):
        data = data.replace("'", "\\'")
    if "`" in str(data):
        data = data.replace("`", "\\`")
    if table_name == 'users':
        update_query = f"UPDATE `{table_name}` SET `{data_field}` = '{data}' " \
                       f"WHERE `telegram_id` = '{telegram_id}'"
    else:
        update_query = f"INSERT INTO `{table_name}` (`{data_field}`) VALUES ('{data}');"
    logging.info(f'Trying to update the `{data_field}` field of `{table_name}` table '
                 f'with `{data}` value...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            double_check_query = f"SELECT * FROM `{table_name}` WHERE `{data_field}` = '{data}';"
            logging.info(f'Checking if {data} is present in the {table_name} already...')
            cursor.execute(double_check_query)
            result = cursor.fetchall()
            if result:
                logging.info(f'{data} is present in the {table_name} already.')
                return 'there_is_double'
            else:
                cursor.execute(update_query)
                connection.commit()
                logging.info(f'An attempt to update the `{data_field}` field of `{table_name}` '
                             f'table with `{data}` value has been successful.')
                return 'idea_saved'
        except Exception as e:
            logging.error(f'An attempt to update the `{data_field}` field of `{table_name}` '
                          f'table with `{data}` value failed: {e}', exc_info=True)
            error = True
        finally:
            connection.close()
            logging.info(f'Connection to the database closed.')
            if error:
                return False


def update_user_vacancies():
    pass
    # update is_sent_to_user field
    # delete record if vacancy_date > datetime.now + 90 days


def update_user_job_names():
    pass
    # add new record
    # remove existing record
    # edit existing record


def update_user_stop_words():
    # add new stop word
    # remove stop word
    # edit existing stop word
    pass


def delete_user():
    pass
    # drop user_vacancies
    # drop user_job_names
    # drop user_stop_words
    # remove user entry from `users`



