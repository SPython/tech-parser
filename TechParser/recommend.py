#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from collections import Counter

from TechParser import get_conf, save
from TechParser.py2x import *
from TechParser.db_functions import *
from TechParser.classifier import TextClassifier

if get_conf.config is None:
    get_conf.set_config_auto()

TextClassifier.load_irregular_words()

def findNearestNumber(n, numbers):
    nearest = numbers[0]
    min_distance = abs(n - nearest)
    for i in numbers[1:]:
        d = abs(n - i)
        if d < min_distance:
            min_distance, nearest = d, i
    
    return nearest

def rankByWordCount(num_words):
    n = findNearestNumber(num_words, get_conf.config.perfect_word_count)
    return 1.0 - abs(num_words - n) / (num_words + n)

def rankBySourcePriority(score, source):
    d = 1.0 - score
    try:
        return 1.0 - d / get_conf.getSourceData(source, (None, {}))[1].get('priority', 1.0)
    except ZeroDivisionError:
        return 0.0

def rank_articles(articles, classifier=None, word_bias=False):
    if classifier is None:
        classifier = loadClassifier()
    if not word_bias:
        classifier.addWordsFromConfiguration()
    
    for article in articles:
        article_text = article['title'] + ' ' + article['summary']
        article_text = classifier.unescape(article_text)
        article_text = classifier.remove_tags(article_text).lower()
        words = classifier.tokenize(article_text)
        words = Counter(classifier.tokenize(classifier.apply_regexes(article_text)))
        del article_text
        
        score = classifier.classify_features(words)['interesting']
        if get_conf.config.perfect_word_count:
            num_words = len(words)
            score = (score + rankByWordCount(num_words)) / 2.0
        
        score = rankBySourcePriority(score, article['source'])
        
        yield (article, score)
        
def add_article(addr):
    if get_conf.config.data_format == 'db':
        article = article_from_list(getArticle(addr))
        add_to_interesting(article)
        return
    
    path = os.path.join(get_conf.logdir, 'articles_dumped')
    
    try:
        articles = save.load_from_somewhere(path)
    except IOError:
        log('WARNING: articles_dumped is missing!')
        return
    
    for article in articles:
        if article['link'] == addr:
            add_to_interesting(article)

def add_article_to_blacklist(addr):
    if get_conf.config.data_format == 'db':
        article = article_from_list(getArticle(addr))
        add_to_blacklist(article)
        return
    
    path = os.path.join(get_conf.logdir, 'articles_dumped')
    
    try:
        articles = save.load_from_somewhere(path)
    except IOError:
        log('WARNING: articles_dumped is missing!')
        return
    
    for article in articles:
        if article['link'] == addr:
            add_to_blacklist(article)
