from time import sleep
import sys
import requests
from pathlib import Path
from pathvalidate import sanitize_filename
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import argparse
import os
import json


def get_books_by_category(category, first_page, last_page):
    books_by_category = []
    for page_num in range(first_page, last_page + 1):
        try:
            url = f'https://tululu.org/{category}/{page_num}/'
            response = requests.get(url)
            response.raise_for_status()
            check_for_redirect(response)
            if response.history:
                print(f'Подготовка к скачиванию {page_num - first_page} страниц')
                soup = BeautifulSoup(response.text, 'lxml')
            for soup_item in soup.select('table.d_book'):
                link = urljoin('https://tululu.org/', str(soup_item.select('a')).split()[1][7:-1])
                books_by_category.append(link)
        except requests.ConnectionError:
            print('Ошибка соединения')
            continue
        except requests.HTTPError:
            print('Невозможно отобразить страницу')
            continue
    return books_by_category


def get_book_page(book_id):
    site = 'https://tululu.org/'
    url = urljoin(site, f'b{book_id}/')

    response = requests.get(url)
    response.raise_for_status()
    check_for_redirect(response)

    return response


def check_for_redirect(response):
    if response.history:
        raise requests.HTTPError


def make_parser():
    parser = argparse.ArgumentParser(description='Скрипт для скачивания книг с сайта tululu.org ')
    parser.add_argument('--first_page',
                        help='С какой страницы начать скачивание, по умолчанию - 25',
                        defualt=25,
                        type=int)
    parser.add_argument('--last_page',
                        help='Какой страницей закончить скачивание, по умолчанию - 75',
                        default=75,
                        type=int)
    parser.add_argument('--category',
                        help='Категория, из которой нужно скачивать книги',
                        default='https://tululu.org/l55/')
    parser.add_argument('--download_folder',
                        help='Папка, в которую скачивать файлы',
                        defual='/Images'
                        type=str)
    parser.add_argument('--json_folder',
                        help='Указать путь к json файлу',
                        type=argparse.FileType('w'),
                        default='info.json')
    parser.add_argument('--skip_text',
                        help='Укажите, чтобы не скачивать текст',
                        action='store_true')
    parser.add_argument('--skip_img',
                        help='Укажите, чтобы не скачивать изображения',
                        action='store_true')

    return parser


def parse_book_page(response):
    soup = BeautifulSoup(response.text, 'lxml')

    title_tag = soup.find('h1')
    book_title, author = title_tag.text.split('::')
    book_title = book_title.strip()
    cover_image = soup.select_one('div.bookimage img')
    cover_image_url = urljoin(response.url, cover_image['src'])
    comments = [tag.text for tag in soup.select('div.texts span')]
    book_genres = [tag.text for tag in soup.select('span.d_book a')]

    return {'title': book_title,
            'author': author,
            'cover_link': cover_image_url,
            'comments': comments,
            'genres': book_genres,
            }


def download_book_txt(book_id, filename, folder='Books/', skip_text=False, download_folder=str(Path.cwd())):
    url = 'https://tululu.org/txt.php'
    payload = {'id': book_id}
    Path(download_folder, folder).mkdir(parents=True, exist_ok=True)

    response = requests.get(url, params=payload)
    response.raise_for_status()
    check_for_redirect(response)

    filepath = Path(download_folder, folder, sanitize_filename(filename))
    if not skip_text:
        with open(filepath, 'wb') as file:
            file.write(response.content)
    return str(filepath)


def download_book_cover(url, filename, skip_img=False, folder='Images/', download_folder=str(Path.cwd())):
    Path(download_folder, folder).mkdir(parents=True, exist_ok=True)

    response = requests.get(url)
    response.raise_for_status()
    check_for_redirect(response)

    filepath = Path(download_folder, folder, sanitize_filename(filename))
    if not skip_img:
        with open(filepath, 'wb') as file:
            file.write(response.content)
    return str(filepath)


def main():
    connection_waiting_sec = 10
    tries_to_connect = 5
    parser = make_parser()
    args = parser.parse_args()

    category = args.category
    first_page = args.first_page
    last_page = args.last_page
    download_folder = args.download_folder 
    json_folder = args.json_folder
    skip_img = args.skip_img,
    skip_text = args.skip_text,

    book_category = category.split('/')[-2]

    books_links = get_books_by_category(book_category, first_page, last_page)
    book_id_nums = [b.split('/')[-1][1:] for b in books_links]
    books_description = []
    for book_id in book_id_nums:
        is_connected = True
        tries_to_connect = 5

        while tries_to_connect:
            try:
                book_response = get_book_page(book_id)
                book_title, author, cover_image_url, book_comments, book_genres = parse_book_page(book_response)
                book_txt_name = f'{book_id}. {book_title}'
                if not skip_text:
                    text_path = download_book_txt(book_id, book_txt_name, download_folder)
                if not skip_img:
                    cover_path = download_book_cover(cover_image_url, cover_image_url.split('/')[-1], download_folder)
                book = {
                    'title': book_title,
                    'author': author,
                    'img_src': cover_path,
                    'book_path': text_path,
                    'comments': comments,
                    'genres': genres,
                }
                if os.path.exists(text_path):
                    books_description.append(book)
                break
            except requests.ConnectionError:
                if is_connected:
                    is_connected = False
                    print(f'Нет соединения')
                else:
                    print('Соединение не установлено')
                    print(f'Retrying connection via {connection_waiting_sec} seconds.')
                    sleep(connection_waiting_sec)
            except requests.HTTPError:
                print(f"Невозможно создать {book_txt_name}")
                break
            except ValueError as error:
                print(f'Неожиданная ошибка: {error}')
                print(f'Ошибка загрузки {book_txt_name}.')
            tries_to_connect -= 1

        json_path = Path(f'{download_folder}/{sanitize_filename(json_folder)}')
    with open(json_path, 'a', encoding='utf-8') as file:
        json.dump(books_description, file, indent=True, ensure_ascii=False)


if __name__ == '__main__':
    main()
