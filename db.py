import configparser
import datetime
import logging
from datetime import date
import texts
import time
import re

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
            logging.info(texts.connection_closed)
            if error:
                return False
            else:
                return True


def add_user_if_none(message):
    """Checks if a user with such telegram id is present in the DB already,
        and creates a new entry if there is no such user in the DB.

    :param message: an aiogram message object which contains user data

    :return: a specific str flag of False, depending on whether everything worked correctly
    :rtype: bool
    """
    telegram_id = str(message.from_user.id)
    telegram_name = message.from_user.usernam
    error = False

    # Checking if user is present in the DB already.
    logging.info(f'Checking if user {telegram_id} ({telegram_name}) exists...')
    # This variable takes a 'user_created' or 'user_exists' state depending
    # on the results of the checkup, and is returned if everything goes smoothly
    # (otherwise False is returned).
    existency_check_result = str()
    search_query = f"SELECT * FROM `users` WHERE `telegram_id` = {telegram_id};"
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(search_query)
        except Exception as e:
            error = True
            logging.error(f'An attempt to check if the user {telegram_id} ({telegram_name}) '
                          f'is present in the DB failed: {e}', exc_info=True)

        # If there is no such user in the DB, we should do the following:
        #   1. Create the user's entry.
        #   2. Create a table with user's vacancies.
        #   3. Create a table with user's job names.
        #   4. Create a table with user's stop words.
        if cursor.fetchone() is None:
            # 1. Creating the user's entry.
            logging.info(f'User {telegram_id} ({telegram_name}) not found. Adding user...')
            user_vacancies = '_'.join(['vacancies', telegram_id])
            user_job_names = '_'.join(['job_names', telegram_id])
            user_stop_words = '_'.join(['stop_words', telegram_id])
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
                                              f"`vacancy_id` INT UNSIGNED PRIMARY KEY " \
                                              f"AUTO_INCREMENT NOT NULL, " \
                                              f"`vacancy_url` VARCHAR(256) NOT NULL, " \
                                              f"`vacancy_name` VARCHAR(512) NOT NULL, " \
                                              f"`vacancy_date` DATE NOT NULL, " \
                                              f"`sent_to_user` TINYINT NOT NULL) ENGINE=InnoDB;"
                create_table(user_vacancies_create_query, user_vacancies)
                # 3. Creating a table with user's job names.
                user_job_names_create_query = f"CREATE TABLE IF NOT EXISTS `{user_job_names}` (" \
                                              f"`job_name_id` INT UNSIGNED PRIMARY KEY " \
                                              f"AUTO_INCREMENT NOT NULL, " \
                                              f"`job_name` VARCHAR(128) NOT NULL) ENGINE=InnoDB;"
                create_table(user_job_names_create_query, user_job_names)
                # 4. Creating a table with user's stop words.
                user_stop_words_create_query = f"CREATE TABLE IF NOT EXISTS `{user_stop_words}` (" \
                                               f"`stop_word_id` INT UNSIGNED PRIMARY KEY " \
                                               f"AUTO_INCREMENT NOT NULL, " \
                                               f"`stop_word` VARCHAR(128) NOT NULL) ENGINE=InnoDB;"
                create_table(user_stop_words_create_query, user_stop_words)
                existency_check_result = 'user_created'
            except Exception as e:
                error = True
                logging.error(f'An attempt to add user {telegram_id} ({telegram_name}) '
                              f'to the DB failed: {e}', exc_info=True)
        else:
            existency_check_result = 'user_exists'

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return existency_check_result


def add_vacancies(user_table_name, vacancies_dict):
    """
    Adds new vacancies to the DB.

    :param user_table_name: a name of the user's table which stores the vacancies found
                            upon user's request
    :type user_table_name: str
    :param vacancies_dict: a dictionary which contains vacancies: looks like
                           {'vacancy_name': 'vacancy_url'}
    :type vacancies_dict: dict

    :return: True of False, depending on whether everything worked correctly
    :rtype: bool
    """
    logging.info(f'Adding new vacancies to the {user_table_name} table...')
    connection = connect_to_db(**db_config)
    error = False
    for vacancy_name, vacancy_url in vacancies_dict.items():
        # 1. Checking if the vacancy in the db already.
        search_query = f"SELECT * FROM `{user_table_name}` WHERE `vacancy_url` = '{vacancy_url}';"
        with connection.cursor() as cursor:
            try:
                logging.info(f'Checking if vacancy {vacancy_url} exists '
                             f'in {user_table_name} table...')
                cursor.execute(search_query)
            except Exception as e:
                logging.error(f'An attempt to check if vacancy {vacancy_url} exists '
                              f'in {user_table_name} table failed: {e}', exc_info=True)
                error = True
            # If vacancy is not in the DB, we should add it.
            if cursor.fetchone() is None:
                insert_query = f"INSERT INTO `{user_table_name}` (`vacancy_url`, `vacancy_name`, " \
                               f"`vacancy_date`, `sent_to_user`) VALUES " \
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
            # If vacancy is in the db already, we pass it and go to the next one.
            else:
                continue

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def edit_or_delete_record(table_name, column_name, record, operation, old_record=None):
    """Edits (replaces with a new one) or deletes records in the DB tables.

    :param table_name: the name of the table which we are performing the operation upon
    :type table_name: str
    :param column_name: the name of the column which contains the data we are about to edit/delete
    :type column_name: str
    :param record: the record we are about to delete or
                   a *new* record we are about to replace the old one
    :type record: str
    :param operation: the operation we are about to perform: edit or delete
    :type operation: str
    :param old_record: the old record we are about to replace with a new one
    :type old_record: str

    :return: True or False, depending on whether the function has been executed correctly or not
    :rtype: bool
    """
    error = False
    query = None
    if operation == 'edit':
        query = f"UPDATE `{table_name}` " \
                f"SET `{column_name}` = '{record}' " \
                f"WHERE `{column_name}` = '{old_record}';"
    if operation == 'delete':
        query = f"DELETE FROM `{table_name}` WHERE `{column_name}` = '{record}';"
    logging.info(f'Trying to {operation} record {record} in {table_name}...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(query)
            connection.commit()
            logging.info(f'An attempt to {operation} {record} from {table_name} '
                         f'performed successfully.')
        except Exception as e:
            logging.error(f'An attempt to {operation} {record} from {table_name} failed: {e}',
                          exc_info=True)
            error = True

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def delete_old_vacancies():
    """
    Iterates over all the tables which contain vacancies, and deletes the old ones.

    :return: True or False, depending on whether the function has been executed correctly or not
    :rtype: bool
    """
    error = False
    # Getting the list of tables with vacancies.
    tables_list = []
    logging.info(f'Getting the list of tables with vacancies...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"SHOW TABLES LIKE 'vacancies%';")
            result = cursor.fetchall()
            for elem in result:
                tables_list.append(elem[0])
            logging.info(f'A list of tables with vacancies created.')
        except Exception as e:
            logging.error(f'An attempt to create a list of tables with vacancies '
                          f'failed: {e}', exc_info=True)
            error = True

    # Calculating the expiration date.
    expiration_date = datetime.date.today() - datetime.timedelta(days=90)

    # Iterating over the tables and deleting old vacancies in each one of them.
    with connection.cursor() as cursor:
        try:
            for table in tables_list:
                logging.info(f'Deleting old vacancies in the {table} table...')
                cursor.execute(f"DELETE FROM `{table}` WHERE `vacancy_date` < '{expiration_date}';")
            connection.commit()
        except Exception as e:
            logging.error(f'An attempt to delete old vacancies failed: {e}', exc_info=True)
            error = True

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def update_sent_to_user(table_name, vacancy_id, state):
    """Updates the sent_to_user parameter in the user's vacancies table

    :param table_name: the name of the table which we are performing the operation upon
    :type table_name: str
    :param vacancy_id: the id of the vacancy
    :type vacancy_id: str or int
    :param state: the new state for the sent_to_user parameter (0 - false, 1 - true)
    :type state: int

    :return: True or False, depending on whether the function has been executed correctly or not
    :rtype: bool
    """
    error = False
    logging.info(f'Updating \'sent_to_user\' field for {vacancy_id} in {table_name}...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"UPDATE `{table_name}` "
                           f"SET `sent_to_user` = '{state}' "
                           f"WHERE `vacancy_id` = '{vacancy_id}';")
            connection.commit()
            logging.info(f'The \'sent_to_user\' field for {vacancy_id} in {table_name} updated.')
        except Exception as e:
            logging.error(f'Update of \'sent_to_user\' for {vacancy_id} in {table_name} failed: '
                          f'{e}', exc_info=True)
            error = True

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def add_job_names_or_stop_words(table_name, data_list):
    """Adds new entries to job_names or stop_words tables.

    :param table_name: a name of the table we need to add the data to
    :type table_name: str
    :param data_list: a list of job names or stop words which should be added
    :type data_list: list
    :return: True or False, depending on whether the function has been executed correctly or not
    :rtype: bool
    """
    column_name = str()
    if table_name.startswith('job_names'):
        column_name = 'job_name'
    if table_name.startswith('stop_words'):
        column_name = 'stop_word'

    error = False
    connection = connect_to_db(**db_config)

    for data_element in data_list:
        # Checking if there is such a data element in the table already.
        with connection.cursor() as cursor:
            try:
                logging.info(f'Checking if {data_element} is in {table_name} already...')
                cursor.execute(f"SELECT * FROM `{table_name}` "
                               f"WHERE `{column_name}` = '{data_element}';")
            except Exception as e:
                logging.error(f'An attempt to check if {data_element} is in {table_name} '
                              f'failed: {e}', exc_info=True)
                error = True

            # If there is no such a job name in the table, we should add it.
            if cursor.fetchone() is None:
                try:
                    logging.info(f'Adding {data_element} to {table_name}...')
                    cursor.execute(f"INSERT INTO `{table_name}` (`{column_name}`) "
                                   f"VALUES ('{data_element}');")
                    connection.commit()
                    logging.info(f'{data_element} added to {table_name}.')
                except Exception as e:
                    logging.error(f'An attempt to add {data_element} to {table_name} '
                                  f'failed: {e}', exc_info=True)
                    error = True

            # If the data element is in the db already, we pass it and go to the next one.
            else:
                continue

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def delete_user(telegram_id):
    """Deletes all user data, including the user's tables and the user's record in the DB.

    :param telegram_id: user's telegram id
    :type telegram_id: int or str

    :return:True or False, depending on whether the function has been executed correctly or not
    :rtype: bool
    """
    error = False
    logging.info(f'Deleting all data for the user {telegram_id}...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            logging.info(f'Getting the tables names for {telegram_id}...')
            cursor.execute(f"SELECT * FROM `users` WHERE `telegram_id` = {telegram_id};")
            result = cursor.fetchall()
            vacancies, job_names, stop_words = result[0][2], result[0][3], result[0][4]
            logging.info(f'Deleting {telegram_id}\'s tables...')
            cursor.execute(f"DROP TABLE IF EXISTS `{vacancies}`, `{job_names}`, `{stop_words}`;")
            logging.info(f'Deleting {telegram_id}\'s record in the DB...')
            cursor.execute(f"DELETE FROM `users` WHERE `telegram_id` = '{telegram_id}';")
            connection.commit()
            logging.info(f'All data for user {telegram_id} deleted.')
        except Exception as e:
            logging.error(f'An attempt to delete user {telegram_id} failed: {e}', exc_info=True)
            error = True

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def get_job_names_or_stop_words(table_name):
    """
    Gets user's job names or stop words from the DB and returns them as a list.

    :param table_name: the name of the table we are extracting the data from
    :type table_name: str

    :return: a list of strings or False if something went wrong
    :rtype: list or bool
    """
    error = False
    logging.info(f'Getting the data from {table_name}...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"SELECT * FROM `{table_name}`;")
            logging.info(f'The data from {table_name} acquired')
            result = cursor.fetchall()
            data_list = [elem[1] for elem in result]
        except Exception as e:
            logging.error(f'Getting the data from {table_name} failed: {e}', exc_info=True)
            error = True

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return data_list


def check_if_job_names_empty(message):
    """Checks if user's table with job names empty.

    :param message: message: an aiogram message object which contains user data

    :return: a specific str flag of False, depending on whether everything worked correctly
    :rtype: bool
    """
    error = False
    add_user_if_none(message)  # creating user if it doesn't exist
    telegram_id = str(message.from_user.id)
    job_names_table_state = 'not_empty'
    job_names_table = '_'.join(['job_names', telegram_id])
    logging.info(f'Checking if user {telegram_id} has no entries in {job_names_table}...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"SELECT * FROM `{job_names_table}`;")
            if len(cursor.fetchall()) == 0:
                job_names_table_state = 'empty'
        except Exception as e:
            error = True
            logging.error(f'Checking if user {telegram_id} has no entries in {job_names_table} '
                          f'failed: {e}', exc_info=True)

    connection.close()
    logging.info(texts.connection_closed)
    print(job_names_table_state)
    if error:
        return False
    else:
        return job_names_table_state
