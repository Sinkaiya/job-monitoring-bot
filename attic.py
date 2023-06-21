# Just a storage for some stuff that is not used anymore,
# but it is better to still keep it, just in case. :)

# These separate functions don't fit into the DRY principle,
# so I've joined every pair of them into one.

# @dp.message_handler(commands='add_jobs', state='*')
# async def cmd_add_job_names(message: types.Message, state: FSMContext):
#     db.add_user_if_none(message)  # checking if user exists and creating it if it doesn't
#     # Putting the bot into the 'waiting_for_jobs' statement.
#     await message.answer(texts.add_job_names)
#     await state.set_state(GetUserData.waiting_for_jobs.state)
#
#
# # This function is being called only from the 'waiting_for_jobs' statement.
# @dp.message_handler(state=GetUserData.waiting_for_jobs, content_types='any')
# async def jobs_acquired(message: types.Message, state: FSMContext):
#     table = '_'.join(['jobs', str(message.from_user.id)])
#     data_acquired = await acquire_data(message, state, table)
#     if data_acquired:
#         await message.answer(texts.jobs_list_acquired)
#     else:
#         await message.answer(texts.bot_error_message)
#     await state.finish()
#
#
# @dp.message_handler(commands='add_stops', state='*')
# async def cmd_add_stops(message: types.Message, state: FSMContext):
#     db.add_user_if_none(message)  # checking if user exists and creating it if it doesn't
#     # Putting the bot into the 'waiting_for_stops' statement:
#     await message.answer(texts.enter_stops)
#     await state.set_state(GetUserData.waiting_for_stops.state)
#
#
# # This function is being called only from the 'waiting_for_stops' statement.
# @dp.message_handler(state=GetUserData.waiting_for_stops, content_types='any')
# async def stops_acquired(message: types.Message, state: FSMContext):
#     table = '_'.join(['stops', str(message.from_user.id)])
#     data_acquired = await acquire_data(message, state, table)
#     if data_acquired:
#         await message.answer(texts.stops_acquired)
#     else:
#         await message.answer(texts.bot_error_message)
#     await state.finish()


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
