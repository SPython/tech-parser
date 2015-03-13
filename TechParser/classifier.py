#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

import os
import re

from collections import Counter

from TechParser.py2x import unicode_, chr, htmlentitydefs

import nltk.corpus
import nltk.stem

ENGLISH_STOPWORDS = nltk.corpus.stopwords.words('english')

class TextClassifier(object):
    replacements = {}
    stemmer = nltk.stem.PorterStemmer()
    regular_expressions = [(re.compile(r'\bain\'t\b'), ''),
        (re.compile(r'\b(?P<g1>\w+)\'(s|m|d|ve|re)\b'), '\g<g1>'),
        (re.compile(r'\b(?P<g1>\w+)n\'t\b'), '\g<g1>'),
        (re.compile(r'\b(' + r'|'.join(ENGLISH_STOPWORDS) + r')\b'), ''),
        (re.compile(r'<.*?>'), ' '),
        (re.compile(r'\d+'), '')]
    unicode_chr_regex = re.compile(r'&#?\w+;')
    tokenize_regex = re.compile(r'\w+\'\w{1,2}|\w+')
    
    def __init__(self, categories):
        self._counts_change, self.counts, self.sample_counts, self._sample_counts_change = {}, {}, {}, {}
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
    def tokenize(text):
        return TextClassifier.tokenize_regex.findall(text)
    
    @staticmethod
    def load_irregular_words():
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'irregular_words.csv')) as f:
            for line in f:
                line = line.strip().split(',')
                first = line[0]
                for word in line[1:]:
                    TextClassifier.replacements[word] = first
    
    @staticmethod
    def prepare_words(text):
        text = TextClassifier.apply_regexes(TextClassifier.unescape(text.lower()))
        text = TextClassifier.tokenize(text)
        return TextClassifier.replace_irregular_words(text)
    
    @staticmethod
    def prepare_article(article):
        return TextClassifier.prepare_counter(article['title'] + ' ' + article['summary'])
    
    @staticmethod
    def prepare_counter(text):
        return Counter(TextClassifier.prepare_words(text))
    
    def classify_text(self, text):
        """Get probabilities for text"""
        
        return self.classify_features(TextClassifier.prepare_counter(text))
    
    def classify_article(self, article):
        """Get probabilities for article"""
        
        return self.classify_features(TextClassifier.prepare_article(article))
    
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
        
        self.add_sample(TextClassifier.prepare_counter(article['title'] + ' ' + article['summary']), category)
    
    def apply_changes(self):
        """Update actual counters"""
        
        for category, changes in self._counts_change.items():
            old_count = self.sample_counts[category]
            new_sample_count = old_count + self._sample_counts_change[category]
        
            r = old_count / new_sample_count
            counter = self.counts[category]
            
            if r != 0:
                for k in counter.keys():
                    counter[k] *= r
            for k, v in changes.items():
                counter[k] += v / new_sample_count
            
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
    
    c = TextClassifier(['interesting', 'boring'])
    
    print('Training classifier...')
    for i in h:
        c.add_article(i, 'interesting')

    for i in b:
        c.add_article(i, 'boring')
    
    print('Applying changes...')
    c.apply_changes()
    
    import IPython
    IPython.embed()