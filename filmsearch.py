import re
import requests
import urllib
from bs4 import BeautifulSoup


class Film:
    def __init__(self, title, time=None, genre=None, date=None,
                 poster=None, summary=None, credits_dict=None, http_path=None):
        self.title = title
        self.time = time
        self.genre = genre
        self.date = date
        self.poster = poster
        self.summary = summary
        self.credits_dict = credits_dict
        self.http_prefix = http_path


def getter(function):
    try:
        return function()
    except Exception:
        return None


def get_film_imdb(film):
    http_path = 'https://www.imdb.com'

    r = requests.get(film)
    soup = BeautifulSoup(r.text, 'lxml')

    head = soup.find('div', 'title_wrapper')
    title = getter(lambda: head.find('h1').get_text().strip())

    if title is None:
        return None

    subtext = head.find('div', 'subtext')
    time = getter(lambda: subtext.find('time').get_text().strip())
    genre = getter(lambda: ', '.join(map(lambda x: x.get_text().strip(), subtext.find_all('a')[:-1])))
    date = getter(lambda: subtext.find('a', title='See more release dates').get_text().strip())

    poster = soup.find('div', 'poster')
    image_link = getter(lambda: ''.join(re.findall(r'.*@|\.[^\.]*$', poster.find('img')['src'])))

    summary = soup.find('div', 'summary_text')
    summary_text = getter(lambda: summary.get_text().strip())

    credit = dict()
    for item in soup.find_all('div', 'credit_summary_item'):
        key = item.find('h4').get_text().split(':')[0]
        data = item.get_text().split(':')[-1].split('|')[0].strip()
        if data:
            credit[key] = data

    return Film(title, time, genre, date, image_link, summary_text, credit, http_path)


def search_imdb(film, episodes=False):
    address = 'https://www.imdb.com/find?ref_=nv_sr_fn&q={0}&s={1}'
    req_type = ['tt', 'ep']

    r = requests.get(address.format(film, req_type[episodes]))
    soup = BeautifulSoup(r.text, 'lxml')

    results = soup.find_all('td', 'result_text')

    films = []
    for i, result in enumerate(results):
        if i >= 5:
            break
        link = result.find('a')
        film = get_film_imdb('https://www.imdb.com' + link['href'])
        if film is not None:
            films.append(film)

    return films


def get_film_kinoteatr(film):
    http_path = 'https://www.kino-teatr.ru'

    r = requests.get(film)
    soup = BeautifulSoup(r.text, 'lxml-xml')

    head = soup.find('div', id='page_name')
    title = getter(lambda: head.get_text().strip())

    if title is None:
        return None

    time = None
    genre = getter(lambda: soup.find('span', itemprop='genre').get_text().strip())
    date = None

    poster = requests.get(film.replace('annot', 'poster'))
    poster_soup = BeautifulSoup(poster.text, 'lxml-xml')
    img_link = getter(lambda: poster_soup.find('div', 'block_wrap').find('a')['href'].split('/'))
    prefix_poster = 'https://www.kino-teatr.ru/movie/poster/{}/{}.jpg'
    image_link = getter(lambda: prefix_poster.format(img_link[-4], img_link[-2]))

    summary = soup.find('div', itemprop='description')
    summary_text = getter(lambda: summary.get_text().strip())

    credit = dict()
    for item in soup.find_all('div', 'film_persons_block'):
        key = item.find('div', 'film_persons_type').get_text().strip()
        if key == 'Премьера':
            date = item.find('div', 'film_persons_names').get_text().strip()
        elif key in ['Режиссер', 'Сценарист', 'Актеры']:
            info_block = item.find('div', 'film_persons_names')
            if info_block.find('span') is None:
                data = item.find('div', 'film_persons_names').get_text().strip()
            else:
                names = info_block.find_all('span', itemprop='name')
                if len(names) > 5:
                    names = names[:5]
                data = ', '.join(map(lambda x: x.get_text().strip(), names))
            credit[key] = data

    return Film(title, time, genre, date, image_link, summary_text, credit, http_path)


def search_kinoteatr(film):
    params = {
            'text': film.encode('cp1251')
            }
    r = requests.post('https://www.kino-teatr.ru/search/', params)
    soup = BeautifulSoup(r.text, 'lxml-xml')

    films = []

    for i, result in enumerate(soup.find_all('div', 'list_item_name')):
        if i >= 5:
            break
        link = result.find('a')
        film = get_film_kinoteatr('https://www.kino-teatr.ru' + link['href'])

        if film is not None:
            films.append(film)

    return films


def watch_film(film):
    result = dict()

    ivi_cinema = 'https://www.ivi.ru/search/?q={}'.format(urllib.parse.quote(film))
    r = requests.get(ivi_cinema)
    soup = BeautifulSoup(r.text, 'lxml-xml')

    link = soup.find('a', 'item-content-wrapper js-collection-content')
    if link is not None:
        result['Ivi'] = 'https://www.ivi.ru' + link['href']

    okko_cinema = 'https://okko.tv/search/{}'.format(film.split(r'(')[0].strip())
    r = requests.get(okko_cinema)
    soup = BeautifulSoup(r.text, 'lxml')

    for res in soup.find_all('section', 'results'):
        name = res.find('h2')
        link = res.find('a', 'movie-card__link')
        if link is not None and name is not None:
            result['Okko, ' + name.get_text().strip().split(' ')[0]] = 'https://okko.tv' + link['href']

    return result
