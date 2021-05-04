import math
import requests
import re
import pymorphy2

from bs4 import BeautifulSoup
from collections import Counter


def get_normal_form(x):
    """приводит слова к начальной форме"""
    morph = pymorphy2.MorphAnalyzer()
    p = morph.parse(x)[0]
    return p.normal_form


class Parser:
    """в этом классе происходит первоначальная обработка статьи, то есть: сохраняются все ссылки, которые необходимо
    обработать, сохраняется список всех слов"""

    def urls_ini(self, search_depth, url):
        """рекурсивно \"складываем\" все необходимые ссылки в set"""
        if search_depth == 0:
            return

        try:
            contents = requests.get(url).text
        except:
            return

        soup = BeautifulSoup(contents, 'lxml')

        if len(soup.find_all("div", class_="mw-parser-output")) == 0:
            return

        soup = BeautifulSoup(str(soup.find_all("div", class_="mw-parser-output")[0]), 'lxml')
        soup = soup.find_all('a', href=True)

        def is_correct_link(i):
            """проверяет, не является ли ссылка \"плохой\""""
            return len(i.find_all('a', class_='image')) == 0 and \
                   len(i.find_all('a', class_='internal')) == 0 and \
                   len(i.find_all('a', title='Улучшение статьи')) == 0 and \
                   len(i.find_all('a', class_='external text')) == 0 and \
                   len(i.find_all('a', title='Просмотр этого шаблона')) == 0 and \
                   len(i.find_all('a', class_='mw-editsection-visualeditor')) == 0 and \
                   len(i.find_all('a', title='Редактировать раздел «См. также»')) == 0

        for elem in soup:
            i = BeautifulSoup(str(elem), 'lxml')
            if is_correct_link(i):
                res = i.find('a').get('href')
                if len(res) >= 5:
                    if res[0:4] != 'https':
                        res = 'https://' + self.lang + '.wikipedia.org' + res
                    self.urls.add(res)
                    self.urls_ini(search_depth - 1, res)

    def get_rought_text(self, url):
        """сохраняем текст статьи"""
        contents = requests.get(url).text

        soup = BeautifulSoup(contents, 'lxml')
        soup = BeautifulSoup(str(soup.find_all("div", class_="mw-parser-output")[0]), 'lxml')
        return soup.get_text()

    def __init__(self, url, lang, search_depth):
        self.urls = set()  # множество всех ссылок, которые надо обработать
        self.urls.add(url)

        self.text = self.get_rought_text(url)  # текс самой первой статьи

        self.lang = lang  # язык статей
        self.search_depth = search_depth  # глубина поиска
        self.urls_ini(search_depth - 1, url)

        self.words = []  # список всех слов

        self.process_urls()

    def process_urls(self):
        """обрабатываем все сслыки"""
        for url in self.urls:
            try:
                contents = requests.get(url).text
            except:
                continue

            soup = BeautifulSoup(contents, 'lxml')
            if len(soup.find_all("div", class_="mw-parser-output")) == 0:
                continue
            soup = BeautifulSoup(str(soup.find_all("div", class_="mw-parser-output")[0]), 'lxml')
            content = soup.get_text()

            reg = re.compile(r'[^a-zA-Zа-яА-Я ]')
            reg1 = re.compile(r'[$displaystyle$, $mathbb$]')

            content = (reg1.sub(' ', reg.sub(' ', content))).split()

            """русские слова из 2ух букв"""
            two_symb_words = ['як', 'ёж', 'уж', 'ум', 'ус', 'юг', 'яд', 'ад', 'аз', 'яр', 'щи', 'ил']

            """ведь мы не хотим обрабатывать большую часть служебных слов"""
            for i in content:
                if len(i) >= 3 or i in two_symb_words:
                    self.words.append(i)


class DataAnalyzer:
    def count_standard_deviation(self, x):
        """посчитать стандартное отклонение частоты слова"""

        res = 0
        for elem in self.frequency_of_use_of_words.items():
            res += (x - elem[1]) ** 2
        res /= len(self.frequency_of_use_of_words)

        return math.sqrt(res)

    def find_outliers(self):
        """детектим слова-выбросы"""

        for elem in self.frequency_of_use_of_words.items():
            if self.count_standard_deviation(elem[1]) >= 3.0:
                self.outliers.append(elem[0])

    def __init__(self, parser, norm):
        self.parser = parser
        self.frequency_of_use_of_words = Counter()  # словаь с частой вхождения каждого слова
        self.is_needed_to_be_normalized = norm  # нужно ли приводить слова к начальной форме

        """заполняем частоту слов"""
        temp = set()
        for i in parser.words:
            temp.add(i)

        for i in temp:
            j = i if not norm else get_normal_form(i)
            self.frequency_of_use_of_words[j] += 1
        """--------------------------------------"""

        self.outliers = []
        self.find_outliers()

        for i in self.outliers:
            self.frequency_of_use_of_words.pop(i)  # удаляем выбросы из обработанной информации
