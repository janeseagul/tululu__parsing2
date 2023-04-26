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


def get_books_list(category, first, last):
    array = []
    for book in range(first, last + 1):
        url = f'https://tululu.org/{category}/{book}/'
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        for i in soup.select('table.d_book'):
            link = urljoin('https://tululu.org/', str(i.select('a')).split()[1][7:-1])
            array.append(link)
    return array


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
                        help='С какой страницы начать скачивание',
                        type=int)
    parser.add_argument('--last_page',
                        help='Какой страницей закончить скачивание',
                        type=int)
    parser.add_argument('--category',
                        help='Категория, из которой нужно скачивать книги',
                        default='https://tululu.org/l55/')
    parser.add_argument('--download_folder',
                        help='Папка, в которую скачивать файлы',
                        type=str)
    parser.add_argument('--json_folder',
                        help='Указать путь к json файлу',
                        type=argparse.FileType('w'),
                        default='info.json')
    parser.add_argument('--skip_text', help='Укажите, чтобы не скачивать текст')
    parser.add_argument('--skip_img', help='Укажите, чтобы не скачивать изображения')

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

    return book_title, author, cover_image_url, comments, book_genres


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
    parser = make_parser()
    args = parser.parse_args()
    category = args.category
    first_page = args.first_page
    last_page = args.last_page
    download_folder = str(args.download_folder)
    json_folder = args.json_folder.name,
    skip_img = args.skip_img,
    skip_text = args.skip_text,

    book_category = category.split('/')[-2]
    connection_waiting_sec = 10
    tries_to_connect = 5
    non_filter_books = get_books_list(book_category, first_page, last_page)
    non_filter_books_reduced = [b.split('/')[-2][1:] for b in non_filter_books]
    books_description = []
    for book_id in non_filter_books_reduced:
        is_connected = True
        number_of_tries = 5
        while tries_to_connect > 0:
            try:
                response = get_book_page(book_id)
                book_title, author, cover_image_url, book_comments, book_genres = parse_book_page(response)
                book_txt_name = f'{book_id}. {book_title}'
                text_path = download_book_txt(book_id, book_txt_name, skip_text, download_folder)
                cover_path = download_book_cover(cover_image_url, cover_image_url.split('/')[-1], skip_img, download_folder)
                genres = book_genres
                comments = book_comments
                book_describe = {
                    'title': book_title,
                    'author': author,
                    'img_src': cover_path,
                    'book_path': text_path,
                    'comments': comments,
                    'genres': genres,
                }
                if os.path.exists(text_path):
                    books_description.append(book_describe)
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
            tries_to_connect -= 1
        json_path = Path(f'{download_folder}/{sanitize_filename(json_folder)}')
        with open(json_path, 'a', encoding='utf-8') as file:
            json.dump(books_description, file, indent=True, ensure_ascii=False)


if __name__ == '__main__':
    main()
