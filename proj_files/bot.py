import logging
import matplotlib.pyplot as plt
import numpy as np
import re
import os
import parser

from wordcloud import WordCloud
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater
from collections import OrderedDict
from os import path
from scipy.stats import entropy


def count_entropy(x):
    """считает энтропию строки x"""
    labels = np.array(list(x))
    _, counts = np.unique(labels, return_counts=True)
    return entropy(counts, base=None)


BOT_TOKEN = "1764134213:AAGWVu3sPuVAeN8jt2GS9OgAfrpUZGt21l8"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

analyzer = None  # экзмепляр анализатора данных с базовым функционалом для статьи
color = None     # сохраняем прошлый цвет для оптимизации генерации word cloud


def start(update: Update, _: CallbackContext):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_text(
        'Введите "/url", ссылку на статью в википедии, язык статьи (ru, en, ...), глубину поиска '
        'и нужно ли приводить слова к начальной форме (для этого ввести любое значение, иначе не '
        'вводить: '
    )


def help_command(update: Update, _: CallbackContext):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Доступные комманды: '
                              '\n\n/top N (asc | desc) - вывести топ самых часто (редко) используемых слов, '
                              'но без учета “выбросов”'
                              '\n\n/stopw - вывести слова-выбросы'
                              '\n\n/cloud COLOR - нарисовать облако слов в указанной цветовой гамме'
                              '\n\n/describe - выводит всю доступную статистику по данным'
                              '\n\n/describe WORD - выводит всю доступную статистику по данному слову в тексте'
                              '\n\n/entropy - считает энтропию текста')


def get_url(update: Update, context: CallbackContext):
    """первоначальная обработка статьи и подстатей глубины search_depth"""
    if len(context.args) < 3:
        update.message.reply_text('некорректная команда')
        return

    url = context.args[0]
    lang = context.args[1]
    search_depth = int(context.args[2])
    norm = False
    if len(context.args) > 3:
        norm = True

    """wordcloud.png = сохраненное облако слов"""
    if path.exists('wordcloud.png'):
        os.remove('wordcloud.png')

    update.message.reply_text('старт инициализации')

    global analyzer
    analyzer = parser.DataAnalyzer(parser.Parser(url, lang, search_depth), norm)

    update.message.reply_text('успешно проинициализировано')


def get_word_cloud(update: Update, context: CallbackContext):
    """получаем облако слов"""

    global color

    def should_be_generated():
        return len(context.args) > 0 and color != context.args[0] or len(context.args) == 0 and color != 'white'

    if should_be_generated():
        common = analyzer.frequency_of_use_of_words.most_common(100)
        wc = WordCloud(width=2600, height=2200, background_color=context.args[0] if len(context.args) > 0 else 'white',
                       relative_scaling=1.0,
                       collocations=False, min_font_size=10).generate_from_frequencies(dict(common))

        color = context.args[0] if len(context.args) > 0 else 'white'
        wc.to_file(path.join("wordcloud.png"))

    update.message.reply_photo(open('wordcloud.png', 'rb'))


def get_top(update: Update, context: CallbackContext):
    """выводим топ N слов"""

    if len(context.args) < 2:
        update.message.reply_text('некорректная комманда')
        return

    def conv(i):
        return str(i[0]) + ' - ' + str(i[1])

    global analyzer

    res = ''
    if context.args[1] == 'asc':
        for i in analyzer.frequency_of_use_of_words.most_common(int(context.args[0])):
            temp = conv(i)

            if len(res + temp) >= 4096:
                update.message.reply_text(res)
                res = ''

            res += '\n' + temp
    elif context.args[1] == 'desc':
        for i in analyzer.frequency_of_use_of_words.most_common()[:-(int(context.args[0]) + 1):-1]:
            temp = conv(i)

            if len(res + temp) >= 4096:
                update.message.reply_text(res)
                res = ''

            res += '\n' + temp
    else:
        update.message.reply_text('некорректная комманда')
    update.message.reply_text(res)


def get_stop_words(update: Update, _: CallbackContext):
    """выводим слова-выбросы"""

    global analyzer

    res = ''
    for i in analyzer.outliers:
        if len(res + i) >= 4096:
            update.message.reply_text(res)
            res = ''
        res += '\n' + i

    update.message.reply_text(res)


def describe(update: Update, context: CallbackContext):
    global analyzer

    if len(context.args) == 0:
        """частота распределения слов"""
        x = np.array(analyzer.frequency_of_use_of_words.most_common())[:, 1]
        plt.hist(x, density=True)
        plt.ylabel('частота')
        plt.xlabel('количество вхождений')
        plt.savefig('word_rate_freq.png')
        update.message.reply_photo(open('word_rate_freq.png', 'rb'))
        plt.close()
        """----------------------------------------"""

        '''распределение длин слов'''
        x = []

        for i in analyzer.frequency_of_use_of_words.most_common():
            x.append(len(i[0]))

        x = np.array(x)
        plt.hist(x, density=True)
        plt.ylabel('частота')
        plt.xlabel('длина')
        plt.savefig('word_len_rate_freq.png')
        update.message.reply_photo(open('word_len_rate_freq.png', 'rb'))
        plt.close()
        """----------------------------------------"""
    else:
        '''количество употреблений слова'''
        word = context.args[0]
        count = analyzer.frequency_of_use_of_words[word]
        update.message.reply_text('слово "' + word + '" встречается '
                                  + str(count) + ' раз(а)')
        """----------------------------------------"""

        '''место по употреблению'''
        st = OrderedDict()
        for i in analyzer.frequency_of_use_of_words.most_common():
            st.update([(i[1], len(st))])

        place = st[analyzer.frequency_of_use_of_words[word]]

        update.message.reply_text('слово "' + word + '" на ' + str(place + 1) + ' месте по употребелению')
        """----------------------------------------"""

        '''ближайшее слово'''

        if place != 0:
            for i in analyzer.frequency_of_use_of_words.most_common():
                if i[1] == place - 1:
                    update.message.reply_text(i[0])
                    break
        """----------------------------------------"""

        '''средняя позиция в предложении'''
        if count > 0:
            sentences = re.split(r'[\n.\[\]]', analyzer.parser.text)
            res = 0
            for i in sentences:
                temp = [parser.get_normal_form(value) for value in re.split(r'[,\s]', i) if value] if \
                    analyzer.is_needed_to_be_normalized else[value for value in re.split(r'[,\s]', i) if value]
                if word in temp:
                    res += temp.index(word)

            update.message.reply_text('средний номер в предложении = ' + str(res / count))
        """----------------------------------------"""

        '''энтропия слова'''
        update.message.reply_text('энтропия слова = ' + str(count_entropy(word)))


def get_entropy(update: Update, _: CallbackContext):
    """посчитать энтропию статьи"""
    global analyzer
    update.message.reply_text(str(count_entropy(analyzer.parser.text)))


def echo(update: Update, _: CallbackContext):
    """Echo the user message."""
    logger.info(f"Receiving message from @{update.message.chat.username}")


def launch_bot():
    """Start the bot."""
    updater = Updater(BOT_TOKEN)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("url", get_url))
    dp.add_handler(CommandHandler("cloud", get_word_cloud))
    dp.add_handler(CommandHandler("top", get_top))
    dp.add_handler(CommandHandler("stopw", get_stop_words))
    dp.add_handler(CommandHandler("describe", describe))
    dp.add_handler(CommandHandler("entropy", get_entropy))

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    updater.start_polling()
    updater.idle()
