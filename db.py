import configparser
import datetime
import logging
from datetime import date
import texts
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


def create_table(create_query, table):
    """Creates a table which belongs to a specific user and contains this user's data.

    :param create_query: MySQL query for table creation
    :type create_query: str
    :param table: name of the table we are creating
    :type table: str

    :return: True of False, depending on whether everything worked correctly
    :rtype: bool
    """
    error = False
    logging.info('')
    logging.info(f'Creating table {table}...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(create_query)
            connection.commit()
            logging.info(f'Table {table} created.')
        except Exception as e:
            logging.error(f'An attempt to create the table {table} failed: {e}', exc_info=True)
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

    :param message: a message object which contains user data

    :return: a specific str flag of False, depending on whether everything worked correctly
    :rtype: bool
    """
    telegram_id = str(message.from_user.id)
    telegram_name = message.from_user.username
    error = False

    # Checking if user is present in the DB already.
    logging.info('')
    logging.info(f'Checking if user {telegram_id} ({telegram_name}) exists...')
    # This variable takes a 'user_created' or 'user_exists' state depending
    # on the results of the checkup, and is returned if everything goes smoothly
    # (otherwise False is returned).
    existence_check_result = str()
    search_query = f"SELECT * FROM `users` WHERE `telegram_id` = {telegram_id};"
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(search_query)
            search_result = cursor.fetchone()
        except Exception as e:
            error = True
            logging.error(f'An attempt to check if the user {telegram_id} ({telegram_name}) '
                          f'is present in the DB failed: {e}', exc_info=True)

        # If there is no such user in the DB, we should do the following:
        #   1. Create the user's entry.
        #   2. Create a table with user's vacancies.
        #   3. Create a table with user's job names.
        #   4. Create a table with user's stop words.
        if search_result is None:
            # 1. Creating the user's entry.
            logging.info(f'User {telegram_id} ({telegram_name}) not found. Adding user...')
            user_vacancies = '_'.join(['vacancies', telegram_id])
            user_jobs = '_'.join(['jobs', telegram_id])
            user_stops = '_'.join(['stops', telegram_id])
            insert_query = f"INSERT INTO `users` (`telegram_id`, `telegram_name`, " \
                           f"`user_vacancies`, `user_jobs`, `user_stops`) " \
                           f"VALUES ('{telegram_id}', '{telegram_name}', '{user_vacancies}', " \
                           f"'{user_jobs}', '{user_stops}');"
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
                user_jobs_create_query = f"CREATE TABLE IF NOT EXISTS `{user_jobs}` (" \
                                         f"`job_name_id` INT UNSIGNED PRIMARY KEY " \
                                         f"AUTO_INCREMENT NOT NULL, " \
                                         f"`job_name` VARCHAR(128) NOT NULL) ENGINE=InnoDB;"
                create_table(user_jobs_create_query, user_jobs)
                # 4. Creating a table with user's stop words.
                user_stops_create_query = f"CREATE TABLE IF NOT EXISTS `{user_stops}` (" \
                                          f"`stop_word_id` INT UNSIGNED PRIMARY KEY " \
                                          f"AUTO_INCREMENT NOT NULL, " \
                                          f"`stop_word` VARCHAR(128) NOT NULL) ENGINE=InnoDB;"
                create_table(user_stops_create_query, user_stops)
                existence_check_result = 'user_created'
            except Exception as e:
                error = True
                logging.error(f'An attempt to add user {telegram_id} ({telegram_name}) '
                              f'to the DB failed: {e}', exc_info=True)
        else:
            existence_check_result = 'user_exists'

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return existence_check_result


def add_vacancies(user_table, vacancies_dict):
    """
    Adds new vacancies to the DB.

    :param user_table: a name of the user's table which stores the vacancies found
                       upon the user's request
    :type user_table: str
    :param vacancies_dict: a dictionary with vacancies: looks like {'vacancy_name': 'vacancy_url'}
    :type vacancies_dict: dict

    :return: True of False, depending on whether everything worked correctly
    :rtype: bool
    """
    logging.info('')
    logging.info(f'Adding new vacancies to the {user_table} table...')
    connection = connect_to_db(**db_config)
    error = False
    for vacancy_name, vacancy_url in vacancies_dict.items():
        # 1. Checking if the vacancy in the db already.
        search_query = f"SELECT * FROM `{user_table}` WHERE `vacancy_url` = '{vacancy_url}';"
        with connection.cursor() as cursor:
            try:
                logging.info(f'Checking if {vacancy_url} is present in the {user_table} table...')
                cursor.execute(search_query)
                search_result = cursor.fetchone()
            except Exception as e:
                logging.error(f'An attempt to check if vacancy {vacancy_url} exists '
                              f'in the {user_table} table failed: {e}', exc_info=True)
                error = True
            # If there is no such a vacancy in the DB, we should add it.
            if search_result is None:
                insert_query = f"INSERT INTO `{user_table}` (`vacancy_url`, `vacancy_name`, " \
                               f"`vacancy_date`, `sent_to_user`) VALUES " \
                               f"('{vacancy_url}', '{vacancy_name}', '{date.today()}', '0');"
                try:
                    logging.info(f'Adding {vacancy_url} to the {user_table} table...')
                    cursor.execute(insert_query)
                    connection.commit()
                    logging.info(f'The vacancy {vacancy_url} added to {user_table} table.')
                except Exception as e:
                    logging.error(f'An attempt to add {vacancy_url} '
                                  f'to {user_table} failed: {e}', exc_info=True)
                    error = True
            # If vacancy is in the db already, we pass it and go to the next one.
            else:
                logging.info(f'The vacancy {vacancy_url} is present in the {user_table} '
                             f'table already.')
                continue

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def add_jobs_or_stops(table, data_list):
    """Adds new entries to jobs or stops tables.

    :param table: a name of the table we need to add the data to
    :type table: str
    :param data_list: a list of job names or stop words which should be added
    :type data_list: list
    :return: True or False, depending on whether the function has been executed correctly or not
    :rtype: bool
    """
    column_name = str()
    if table.startswith('jobs'):
        column_name = 'job_name'
    if table.startswith('stops'):
        column_name = 'stop_word'

    error = False
    logging.info('')
    logging.info(f'Adding new records to the {table} table...')
    connection = connect_to_db(**db_config)

    for data_element in data_list:
        # Checking if there is such a data element in the table already.
        with connection.cursor() as cursor:
            try:
                logging.info(f'Checking if \'{data_element}\' is present in {table}...')
                cursor.execute(f"SELECT * FROM `{table}` "
                               f"WHERE `{column_name}` = '{data_element}';")
                search_result = cursor.fetchone()
            except Exception as e:
                logging.error(f'An attempt to check if \'{data_element}\' is in {table} '
                              f'failed: {e}', exc_info=True)
                error = True

            # If there is no such a job name in the table, we should add it.
            if search_result is None:
                try:
                    logging.info(f'Adding \'{data_element}\' to {table}...')
                    cursor.execute(f"INSERT INTO `{table}` (`{column_name}`) "
                                   f"VALUES ('{data_element}');")
                    connection.commit()
                    logging.info(f'\'{data_element}\' added to {table}.')
                except Exception as e:
                    logging.error(f'An attempt to add \'{data_element}\' to {table} '
                                  f'failed: {e}', exc_info=True)
                    error = True

            # If the data element is in the db already, we pass it and go to the next one.
            else:
                logging.info(f'The table {table} already contains \'{data_element}\'. '
                             f'Skipping...')
                continue

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def get_jobs_or_stops(table):
    """
    Gets user's job names or stop words from the DB and returns them as a list.

    :param table: the name of the table we are extracting the data from
    :type table: str

    :return: a string or False if something went wrong
    :rtype: str or bool
    """
    error = False
    logging.info(f'Getting the data from the \'{table}\' table...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"SELECT * FROM `{table}`;")
            logging.info(f'The data from the \'{table}\' table acquired.')
            result = cursor.fetchall()
            data_str = ', '.join([elem[1] for elem in result])
        except Exception as e:
            logging.error(f'Getting the data from {table} failed: {e}', exc_info=True)
            error = True

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return data_str


# def edit_record(table, column_name, old_record, new_record):
#     """Edits (replaces with a new one) or deletes records in the DB tables.
#
#     :param table: the name of the table which we are performing the operation upon
#     :type table: str
#     :param column_name: the name of the column which contains the data we are about to edit/delete
#     :type column_name: str
#     :param old_record: the old record we are about to replace with a new one
#     :type old_record: str
#     :param new_record: a new record we are about to replace the old one with
#     :type new_record: str
#
#     :return: True/str or False, depending on whether the function
#              has been executed correctly or not
#     :rtype: bool
#     """
#     error = False
#     function_result = str()
#     logging.info('')
#     logging.info(f'Trying to replace the record \'{old_record}\' '
#                  f' with new record \'{new_record}\' in the {table} table...')
#     connection = connect_to_db(**db_config)
#     with connection.cursor() as cursor:
#         try:
#             # Checking if there is such a record in the DB already:
#             logging.info(f'Checking if record \'{new_record}\' is present '
#                          f' in the {table} table already...')
#             cursor.execute(f"SELECT * FROM `{table}` WHERE `{column_name}` = '{new_record}';")
#             search_result = cursor.fetchone()
#             if search_result is None:
#                 logging.info(f'The record \'{new_record}\' is not present '
#                              f' in the {table} yet. Replacing...')  # ???????????
#                 cursor.execute(f"UPDATE `{table}` SET `{column_name}` = '{new_record}' "
#                                f"WHERE `{column_name}` = '{old_record}';")
#                 connection.commit()
#                 function_result = 'changed'
#                 logging.info(
#                     f'An attempt to replace an old record \'{old_record}\' in {table} '
#                     f' with \'{new_record}\' performed successfully.')
#             else:
#                 function_result = 'double'
#                 logging.info(f'The record \'{new_record}\' is indeed present in the {table} '
#                              f' already. Function work result is set to \'{function_result}\'.')
#         except Exception as e:
#             logging.error(f'An attempt to replace an old record \'{old_record}\' in {table} '
#                           f' with \'{new_record}\' failed: {e}', exc_info=True)
#             error = True
#
#     connection.close()
#     logging.info(texts.connection_closed)
#     if error:
#         return False
#     else:
#         return function_result


def clean_up_db_table(table):
    """Truncates the table.

    :param table: the name of the table which we are performing the operation upon
    :type table: str

    :return True or False, depending on whether the function has been executed correctly or not
    :rtype: bool
    """
    error = False
    logging.info('')
    logging.info(f'Trying to clean up the \'{table}\' table...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"TRUNCATE TABLE `{table}`;;")
            connection.commit()
            logging.info(
                f'The \'{table}\' table cleaned up successfully.')
        except Exception as e:
            logging.error(f'An attempt to clean up the \'{table}\' table failed: {e}',
                          exc_info=True)
            error = True

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def delete_record(table, column_name, record):
    """Deletes records in the DB tables.

    :param table: the name of the table which we are performing the operation upon
    :type table: str
    :param column_name: the name of the column which contains the data we are about to delete
    :type column_name: str
    :param record: the record we are about to delete
    :type record: str

    :return: True or False, depending on whether the function has been executed correctly or not
    :rtype: bool
    """
    error = False
    logging.info('')
    logging.info(f'Trying to delete \'{record}\' in the \'{table}\' table...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"DELETE FROM `{table}` WHERE `{column_name}` = '{record}';")
            connection.commit()
            logging.info(
                f'The record \'{record}\' successfully deleted from the \'{table}\' table.')
        except Exception as e:
            logging.error(f'An attempt to delete \'{record}\' from the \'{table}\' table '
                          f'failed: {e}', exc_info=True)
            error = True

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def delete_old_vacancies():
    """
    Iterates over all the tables with vacancies, and deletes the old ones.

    :return: True or False, depending on whether the function has been executed correctly or not
    :rtype: bool
    """
    error = False
    # Getting the list of tables with vacancies.
    tables_list = []
    logging.info('')
    logging.info(f'Starting a regular job of deleting old vacancies. '
                 f'Getting the list of tables with vacancies...')
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
                logging.info(f'Deleting old vacancies in the \'{table}\' table...')
                cursor.execute(f"DELETE FROM `{table}` WHERE `vacancy_date` < '{expiration_date}';")
            connection.commit()
        except Exception as e:
            logging.error(f'An attempt to delete old vacancies in the \'{table}\' table '
                          f'failed: {e}', exc_info=True)
            error = True

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return True


def update_sent_to_user(table, vacancy_id, state):
    """Updates the sent_to_user parameter in the user's vacancies table

    :param table: the name of the table which we are performing the operation upon
    :type table: str
    :param vacancy_id: the id of the vacancy
    :type vacancy_id: str or int
    :param state: the new state for the sent_to_user parameter (0 - false, 1 - true)
    :type state: int

    :return: True or False, depending on whether the function has been executed correctly or not
    :rtype: bool
    """
    error = False
    logging.info(f'Updating the \'sent_to_user\' field for {vacancy_id} '
                 f'in the \'{table}\' table...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"UPDATE `{table}` "
                           f"SET `sent_to_user` = '{state}' "
                           f"WHERE `vacancy_id` = '{vacancy_id}';")
            connection.commit()
            logging.info(f'The \'sent_to_user\' field for {vacancy_id} in the \'{table}\' updated.')
        except Exception as e:
            logging.error(f'Update of \'sent_to_user\' for {vacancy_id} in the \'{table}\' failed: '
                          f'{e}', exc_info=True)
            error = True

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
    logging.info('')
    logging.info(f'Deleting all data for the user {telegram_id}...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            logging.info(f'Getting the tables names for {telegram_id}...')
            cursor.execute(f"SELECT * FROM `users` WHERE `telegram_id` = {telegram_id};")
            result = cursor.fetchall()
            vacancies, jobs, stops = result[0][2], result[0][3], result[0][4]
            logging.info(f'Deleting {telegram_id}\'s tables...')
            cursor.execute(f"DROP TABLE IF EXISTS `{vacancies}`, `{jobs}`, `{stops}`;")
            logging.info(f'{telegram_id}\'s tables deleted.')
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


def check_if_jobs_empty(message):
    """Checks if user's table with job names empty.

    :param message: message: a message object which contains user data

    :return: a specific str flag of False, depending on whether everything worked correctly
    :rtype: bool
    """
    error = False
    add_user_if_none(message)  # creating user if it doesn't exist
    telegram_id = str(message.from_user.id)
    jobs_table_state = 'not_empty'
    jobs_table = '_'.join(['jobs', telegram_id])
    logging.info(f'Checking if the user {telegram_id} has no entries '
                 f'in the \'{jobs_table}\' table...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"SELECT * FROM `{jobs_table}`;")
            if len(cursor.fetchall()) == 0:
                jobs_table_state = 'empty'
        except Exception as e:
            error = True
            logging.error(f'Check if the user {telegram_id} has no entries in the \'{jobs_table}\' '
                          f'table failed: {e}', exc_info=True)

    connection.close()
    logging.info(texts.connection_closed)
    if error:
        return False
    else:
        return jobs_table_state
