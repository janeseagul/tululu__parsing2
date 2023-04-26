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


def get_books_list():
    array = []
    for book in range(1, 5):
        url = f'https://tululu.org/l55/{book}/'
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
    parser.add_argument('start_index', help='С какого книги нужно начать скачивание', type=int)
    parser.add_argument('end_index', help='Какой книгой нужно завершить скачивание', type=int)
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


def download_book_txt(book_id, filename, folder='Books/'):
    url = 'https://tululu.org/txt.php'
    payload = {'id': book_id}
    Path(f'./{folder}').mkdir(parents=True, exist_ok=True)

    response = requests.get(url, params=payload)
    response.raise_for_status()
    check_for_redirect(response)

    filepath = Path(f'./{folder}/{sanitize_filename(filename)}.txt')

    with open(filepath, 'wb') as file:
        file.write(response.content)
    return str(filepath)


def download_book_cover(url, filename, folder='Images/'):
    Path(f'./{folder}').mkdir(parents=True, exist_ok=True)

    response = requests.get(url)
    response.raise_for_status()
    check_for_redirect(response)

    filepath = Path(f'./{folder}/{sanitize_filename(filename)}')
    with open(filepath, 'wb') as file:
        file.write(response.content)
    return str(filepath)


def main():
    connection_waiting_sec = 10
    tries_to_connect = 5
    non_filter_books = get_books_list()
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
                text_path = download_book_txt(book_id, book_txt_name)
                cover_path = download_book_cover(cover_image_url, cover_image_url.split('/')[-1])
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
        with open('./books.json', 'w', encoding='utf-8') as file:
            json.dump(books_description, file, indent=True, ensure_ascii=False)


if __name__ == '__main__':
    main()
