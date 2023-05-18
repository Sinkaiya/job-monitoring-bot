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


def create_user_table(telegram_id, telegram_name, table_name):
    """Creates a special table in the DB which belongs to specific user
     and contains this user's ideas.

    :param telegram_id: unique numeric id of user's telegram account
    :type telegram_id: int
    :param telegram_name: user's telegram name
    :type telegram_name: str
    :param table_name: name of the user's table we are about to create
    :type table_name: str

    :return: True of False, depending on whether everything worked correctly
    :rtype: bool
    """
    error = False
    create_query = f"CREATE TABLE IF NOT EXISTS `{table_name}` (" \
                   f"`id` INT PRIMARY KEY AUTOINCREMENT NOT NULL, " \
                   f"`vacancy_id` INT NOT NULL, " \
                   f"`is_sent_to_user` TINYINT NOT NULL, " \
                   f"`is_starred` TINYINT NOT NULL) " \
                   f"ENGINE=InnoDB;"
    logging.info(f'Creating a personal table for user {telegram_id} ({telegram_name})...')
    connection = connect_to_db(**db_config)
    with connection.cursor() as cursor:
        try:
            cursor.execute(create_query)
            connection.commit()
            logging.info(f'A personal table for user {telegram_id} ({telegram_name}) '
                         f'has been created successfully.')
        except Exception as e:
            logging.error(f'An attempt to create a personal table for '
                          f'user {telegram_id} ({telegram_name}) failed: {e}', exc_info=True)
            error = True
        finally:
            connection.close()
            logging.info(f'Connection to the database closed.')
            if error:
                return False
            else:
                return True
