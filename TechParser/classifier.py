#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

import os
import re
import codecs

from collections import Counter

from TechParser.py2x import unicode_, chr, htmlentitydefs
from TechParser import get_conf

if get_conf.config is None:
    get_conf.set_config_auto()

import nltk.stem

ENGLISH_STOPWORDS = []
with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'english_stopwords.txt')) as f:
    for word in f:
        ENGLISH_STOPWORDS.append(word.strip())

class TextClassifier(object):
    replacements = {}
    stemmer = nltk.stem.PorterStemmer()
    regular_expressions = [(re.compile(r'\bain\'t\b'), ''),
        (re.compile(r'\b(?P<g1>\w+)\'(s|m|d|ve|re)\b'), '\g<g1>'),
        (re.compile(r'\b(?P<g1>\w+)n\'t\b'), '\g<g1>'),
        (re.compile(r'\b(' + r'|'.join(ENGLISH_STOPWORDS) + r')\b'), ''),
        (re.compile(r'\d+'), '')]
    unicode_chr_regex = re.compile(r'&#?\w+;')
    tokenize_regex = re.compile(r'\w+\'\w{1,2}|\w+[#\+]*')
    remove_tags_regex = re.compile(r'<.*?>')
    
    def __init__(self, categories, ngrams=None):
        self._counts_change, self.counts, self.sample_counts, self._sample_counts_change = {}, {}, {}, {}
        if ngrams is None:
            ngrams = get_conf.config.ngrams
        self.ngrams = ngrams
        for i in categories:
            self._counts_change[i] = Counter()
            self.counts[i] = Counter()
            self._sample_counts_change[i] = 0
            self.sample_counts[i] = 0
    
    @staticmethod
    def apply_regexes(text):
        for regular_expression, replacement in TextClassifier.regular_expressions:
            text = regular_expression.sub(replacement, text)
        
        return text
    
    def addWordsFromConfiguration(self):
        for i in get_conf.config.interesting_words:
            if type(i) in {list, tuple, set}:
                word, priority = i
            else:
                priority = 1.0
                word = i
            
            words = self.prepare_words(word)
        
            for word in words:
                self.counts['interesting'][word] *= priority
        
        for i in get_conf.config.boring_words:
            if type(i) in {list, tuple, set}:
                word, priority = i
            else:
                priority = 1.0
                word = i
            
            words = self.prepare_words(word)
            
            for word in words:
                self.counts['boring'][word] *= priority
    
    @staticmethod
    def unescape(text):
        try:
            text = unicode_(text)
        except TypeError:
            pass
        
        def fixup(m):
            text = m.group(0)
            if text[:2] == "&#":
                try:
                    if text[:3] == "&#x":
                        return chr(int(text[3:-1], 16))
                    else:
                        return chr(int(text[2:-1]))
                except ValueError:
                    pass
            else:
                try:
                    text = chr(htmlentitydefs.name2codepoint[text[1:-1]])
                except KeyError:
                    pass
            return text
        
        return TextClassifier.unicode_chr_regex.sub(fixup, text)
    
    @staticmethod
    def replace_irregular_words(words):
        new = []
        for i in words:
            replacement = TextClassifier.replacements.get(i, i).split()
            for j in replacement:
                new.append(TextClassifier.stemmer.stem(j))
        
        return new
    
    @staticmethod
    def remove_tags(text, replacement=' '):
        return TextClassifier.remove_tags_regex.sub(replacement, text)
    
    @staticmethod
    def tokenize(text):
        return TextClassifier.tokenize_regex.findall(text)
    
    @staticmethod
    def load_irregular_words():
        with codecs.open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'irregular_words.csv'), 'r', 'utf8') as f:
            for line in f:
                line = line.strip().split(',')
                first = line[0]
                for word in line[1:]:
                    TextClassifier.replacements[word] = first
    
    @staticmethod
    def prepare_words(text):
        text = TextClassifier.apply_regexes(TextClassifier.unescape(text.lower()))
        text = TextClassifier.tokenize(TextClassifier.remove_tags(text))
        return TextClassifier.replace_irregular_words(text)
    
    @staticmethod
    def prepare_ngrams(text, n=1):
        words = TextClassifier.prepare_words(text)
        
        for i in range(len(words)):
            sliced1 = words[i:i+n]
            
            yield ' '.join(sliced1)
            
            len_sliced1 = len(sliced1)
            
            for j in range(1, n):
                sliced2 = words[i:i+j]
                len_sliced2 = len(sliced2)
                if len_sliced2 >= j and len_sliced1 != len_sliced2:
                    yield ' '.join(sliced2)
                else:
                    break
    
    @staticmethod
    def prepare_article(article, n=1):
        return TextClassifier.prepare_counter(article['title'] + ' ' + article['summary'], n)
    
    @staticmethod
    def prepare_counter(text, n=1):
        return Counter(TextClassifier.prepare_ngrams(text, n))
    
    def classify_text(self, text):
        """Get probabilities for text"""
        
        return self.classify_features(TextClassifier.prepare_counter(text, self.ngrams))
    
    def classify_article(self, article):
        """Get probabilities for article"""
        
        return self.classify_features(TextClassifier.prepare_article(article, self.ngrams))
    
    def add_sample(self, features, category):
        """Increment counters"""
        
        self._counts_change[category] += features
        self._sample_counts_change[category] += 1
    
    def add_samples(self, samples):
        """Add list of samples"""
        
        for sample in samples:
            self.add_sample(*sample)
    
    def add_articles(self, articles):
        """Add list of articles"""
        
        for sample in articles:
            self.add_article(*sample)
    
    def remove_sample(self, features, category):
        """Remove sample"""
        
        self._counts_change[category] -= features
        self._sample_counts_change[category] -= 1
    
    def remove_article(self, article, category):
        """Remove article as sample"""
        
        self.remove_sample(TextClassifier.prepare_counter(article['title'] + ' ' + article['summary']), category)
    
    def remove_samples(self, samples):
        """Remove list of samples"""
        
        for sample in samples:
            self.remove_sample(*sample)
    
    def remove_articles(self, articles):
        """Remove list of articles"""
        
        for sample in articles:
            self.remove_article(*sample)
    
    def add_article(self, article, category):
        """Add article as sample"""
        
        self.add_sample(TextClassifier.prepare_counter(article['title'] + ' ' + article['summary'], self.ngrams), category)
    
    def apply_changes(self):
        """Update actual counters"""
        
        for category, changes in self._counts_change.items():
            old_count = self.sample_counts[category]
            new_sample_count = old_count + self._sample_counts_change[category]
            
            try:
                r = old_count / new_sample_count
            except ZeroDivisionError:
                r = 0.0
            counter = self.counts[category]
            
            if r != 0:
                for k in counter.keys():
                    counter[k] *= r
            try:
                for k, v in changes.items():
                    counter[k] += v / new_sample_count
            except ZeroDivisionError:
                pass
            
            changes.clear()
            self.sample_counts[category] = new_sample_count
            self._sample_counts_change[category] = 0
    
    def classify_feature(self, feature):
        """Get probabilities for feature"""
        
        feature_counts = {}
        
        sum_ = 0
        
        for category, counter in self.counts.items():
            count = counter.get(feature, 0)
            sum_ += count
            feature_counts[category] = count
        
        probabilities = {i: 1.0 for i in self.counts.keys()}
        
        if sum_ == 0:
            value = 1.0 / len(feature_counts.keys())
            for i in probabilities.keys():
                probabilities[i] = value
            return probabilities
        
        for k, i in feature_counts.items():
            probabilities[k] = i  / sum_
        
        return probabilities
    
    def classify_features(self, features):
        """Get probabilities for features"""
        
        result = Counter()
        length = 0
        
        for feature, count in features.items():
            length += count
            probabilities = self.classify_feature(feature)
            for i in range(count):
                for k, v in probabilities.items():
                    result[k] += v
        
        for k in result:
            result[k] /= length
        
        return result

if __name__ == '__main__':
    print('Loading TechParser modules...')
    from TechParser.db import initialize_main_database
    from TechParser.recommend import get_interesting_articles, get_blacklist
    
    print('Initializing database...')
    initialize_main_database()
    
    print('Loading articles...')
    h = get_interesting_articles()
    b = get_blacklist()
    
    print('Loading irregular words...')
    TextClassifier.load_irregular_words()
    
    c = TextClassifier(['interesting', 'boring'], ngrams=1)
    
    print('Training classifier...')
    for i in h:
        c.add_article(i, 'interesting')

    for i in b:
        c.add_article(i, 'boring')
    
    print('Applying changes...')
    c.apply_changes()
    
    import IPython
    IPython.embed()
