import asyncio
import logging
import time
from collections import defaultdict

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

import filmsearch as film


with open('token', 'r') as token_file:
    API_TOKEN = token_file.read().strip()


USER_RESULTS = defaultdict(str)
USER_TIMESTAMPS = defaultdict(int)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
loop = asyncio.get_event_loop()
bot = Bot(token=API_TOKEN, loop=loop)
storage = MemoryStorage()
dp = Dispatcher(bot, loop=loop, storage=storage)


def get_list_results(films, chat_id, english=True):
    markup = types.InlineKeyboardMarkup()
    if len(films) == 0:
        msg = 'Sorry, no films with your query.' if english else 'Извините, по вашему запросу ничего не найдено.'
    else:
        msg = '<b>The films I have found:</b>\n\n' if english else '<b>Вот что я нашел:</b>\n\n'
        for i, film_item in enumerate(films):
            msg_item = '<b>{}. {}</b>'.format(i + 1, film_item.title)
            markup.add(types.InlineKeyboardButton('{}. {}'.format(i + 1, film_item.title),
                                                  callback_data='{}:{}'.format(i, chat_id)))

            if film_item.genre is not None:
                msg_item += ' - <i>{}</i>'.format(film_item.genre)
            if film_item.date is not None:
                msg_item += ' - ({})'.format(film_item.date)
            msg += '{}\n\n'.format(msg_item)
        msg += 'Results will expire in 10 minutes' if english else 'Результаты будут недействительны через 10 минут'
    return msg, markup


@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    """
    This handler will be called when client send `/start` or `/help` commands.
    """
    await message.reply("""Hi!
I'm CinemaBot!
Type the title of film to search it.

Привет!
Я КиноБот!
Набери название фильма, чтобы я его поискал""")


@dp.message_handler(regexp='.*[А-Яа-я].*')
async def russian_search(message: types.Message):
    to_del = []
    for i, chat_id in enumerate(USER_TIMESTAMPS):
        if time.time() - USER_TIMESTAMPS[chat_id] > 600:
            to_del.append(chat_id)
        if i >= 2:
            break
    for chat_id in to_del:
        del USER_RESULTS[chat_id]
        del USER_TIMESTAMPS[chat_id]

    films = film.search_kinoteatr(message.text)
    USER_RESULTS[message.chat.id] = films
    USER_TIMESTAMPS[message.chat.id] = time.time()

    msg, markup = get_list_results(films, message.chat.id, english=False)
    await bot.send_message(message.chat.id, msg, parse_mode='HTML', reply_markup=markup)


@dp.message_handler()
async def english_search(message: types.Message):
    films = film.search_imdb(message.text)
    USER_RESULTS[message.chat.id] = films
    USER_TIMESTAMPS[message.chat.id] = time.time()

    msg, markup = get_list_results(films, message.chat.id)
    await bot.send_message(message.chat.id, msg, parse_mode='HTML', reply_markup=markup)


@dp.callback_query_handler(func=lambda query: query.data.split(':')[0] in list(map(str, range(5))))
async def film_info(query: types.CallbackQuery):
    item, chat_id = map(int, query.data.split(':'))
    film_item = USER_RESULTS[chat_id][item]
    USER_TIMESTAMPS[chat_id] = time.time()

    msg_item = '<b>{}</b>\n'.format(film_item.title)

    if film_item.genre is not None:
        msg_item += '<i>{}</i>\n'.format(film_item.genre)
    if film_item.date is not None:
        msg_item += '({})\n\n'.format(film_item.date)
    if film_item.time is not None:
        msg_item += '[{}]\n\n'.format(film_item.time)
    if film_item.summary is not None:
        msg_item += '{}\n\n'.format(film_item.summary)
    for credential, info in film_item.credits_dict.items():
        msg_item += '<b>{}</b>: {}\n'.format(credential, info)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('Back',
                                          callback_data='back:{}'.format(chat_id)))
    markup.add(types.InlineKeyboardButton('Watch',
                                          callback_data='watch:{}:{}'.format(item, chat_id)))
    if film_item.poster is not None:
        await bot.send_message(chat_id, '[Poster]({})'.format(film_item.poster), parse_mode='Markdown')
    await bot.send_message(chat_id, msg_item, parse_mode='HTML', reply_markup=markup)


@dp.callback_query_handler(func=lambda query: query.data.split(':')[0] == 'back')
async def back_to_list(query: types.CallbackQuery):
    chat_id = int(query.data.split(':')[-1])
    msg, markup = get_list_results(USER_RESULTS[chat_id], chat_id, english=False)
    USER_TIMESTAMPS[chat_id] = time.time()
    await bot.send_message(chat_id, msg, parse_mode='HTML', reply_markup=markup)


@dp.callback_query_handler(func=lambda query: query.data.split(':')[0] == 'watch')
async def watch_film(query: types.CallbackQuery):
    item, chat_id = map(int, query.data.split(':')[1:])
    film_item = USER_RESULTS[chat_id][item]
    USER_TIMESTAMPS[chat_id] = time.time()

    results = film.watch_film(film_item.title)

    msg = '<b>Watch in:</b>\n\n'
    for platform, link in results.items():
        msg += '<a href="{}"> {} </a>\n\n'.format(link, platform)
    msg += 'This is beta function. Some results may be incorrect.'
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('Back',
                                          callback_data='back:{}'.format(chat_id)))

    await bot.send_message(chat_id, msg, parse_mode='HTML', reply_markup=markup)


if __name__ == '__main__':
    executor.start_polling(dp, loop=loop, skip_updates=True)
