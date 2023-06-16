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
