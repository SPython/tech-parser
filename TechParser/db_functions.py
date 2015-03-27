#!/usr/bin/env python
# -*- coding: utf-8 -*-

from TechParser.query import *
from TechParser import db, get_conf
from TechParser.classifier import TextClassifier
import uuid
import json
from Crypto import Random
from collections import OrderedDict, Counter

def loadClassifier(interesting_articles=None, blacklist=None):
    classifier_counts = get_var('classifier_counts', '')
    classifier_sample_counts = get_var('classifier_sample_counts', '')
    classifier = TextClassifier(['interesting', 'boring'])
    
    try:
        classifier.counts = {k: Counter(v) for k, v in json.loads(classifier_counts).items()}
        classifier.sample_counts = json.loads(classifier_sample_counts)
    except ValueError:
        if interesting_articles is None:
            interesting_articles = get_interesting_articles()
        if blacklist is None:
            blacklist = get_blacklist()
        
        for i in interesting_articles:
            classifier.add_article(i, 'interesting')
        
        for i in blacklist:
            classifier.add_article(i, 'boring')
            
        classifier.apply_changes()
        saveClassifier(classifier)
    
    return classifier

def getArticleFromHistoryByLink(link):
    db.Database.main_database.execute_query(Q_GET_ARTICLE_FROM_HISTORY, [(link,)])
    return db.Database.main_database.fetchone()

def getArticleFromBlacklistByLink(link):
    db.Database.main_database.execute_query(Q_GET_ARTICLE_FROM_BLACKLIST, [(link,)])
    return db.Database.main_database.fetchone()

def saveClassifier(classifier):
    set_var('classifier_counts', json.dumps(classifier.counts))
    set_var('classifier_sample_counts', json.dumps(classifier.sample_counts))

def remove_from_blacklist(link):
    """Remove article from blacklist by link"""

    article = getArticleFromBlacklistByLink(link)
    if article:
        article = articles_from_list([article])[0]
        classifier = loadClassifier()
        classifier.remove_article(article, 'boring')
        classifier.apply_changes()
        saveClassifier(classifier)
        
        db.Database.main_database.execute_query(Q_DELETE_FROM_BLACKLIST, [(link,)])

def remove_from_history(link):
    """Remove article from history by link"""
    
    article = getArticleFromHistoryByLink(link)
    if article:
        article = articles_from_list([article])[0]
        classifier = loadClassifier()
        classifier.remove_article(article, 'interesting')
        classifier.apply_changes()
        saveClassifier(classifier)
        
        db.Database.main_database.execute_query(Q_DELETE_FROM_HISTORY, [(link,)])

def add_to_blacklist(article):
    """Add article to blacklist"""
    
    IntegrityError = db.Database.main_database.userData # userData contains exception
    
    try:
        title = article['title']
        link = article['link']
        summary = article['summary']
        source = article['source']
        fromrss = article.get('fromrss', 0)
        icon = article.get('icon', '')
        color = article.get('color', '#000')
        parameters = [(title, link, summary, fromrss, icon, color, source)]
        
        db.Database.main_database.execute_query(Q_ADD_TO_BLACKLIST, parameters)
        
        classifier = loadClassifier()
        classifier.add_article(article, 'boring')
        classifier.apply_changes()
        saveClassifier(classifier)
    except IntegrityError:
        db.Database.main_database.con.rollback()

def add_to_interesting(article):    
    """Add article to history"""
    
    IntegrityError = db.Database.main_database.userData # userData contains exception
    
    try:
        title = article['title']
        link = article['link']
        summary = article['summary']
        source = article['source']
        fromrss = article.get('fromrss', 0)
        icon = article.get('icon', '')
        color = article.get('color', '#000')
        parameters = [(title, link, summary, fromrss, icon, color, source)]
        
        db.Database.main_database.execute_query(Q_ADD_TO_HISTORY, parameters)
        
        classifier = loadClassifier()
        classifier.add_article(article, 'interesting')
        classifier.apply_changes()
        saveClassifier(classifier)
    except IntegrityError:
        db.Database.main_database.con.rollback()

def articles_from_list(lst, liked=False, disliked=False):
    return [{'title': x[0],
            'link': x[1],
            'summary': x[2],
            'fromrss': x[3],
            'icon': x[4],
            'color': x[5],
            'source': x[6],
            'liked': liked,
            'disliked': disliked} for x in lst]

def get_blacklist():
    """Get list of articles from blacklist"""
    
    db.Database.main_database.execute_query(Q_GET_BLACKLIST)
    
    # TODO return generator
    # TODO reduce memory usage
    return articles_from_list(db.Database.main_database.fetchall(), disliked=True)

def get_interesting_articles():
    """Get list of articles from history (that were marked as interesting)"""
    
    db.Database.main_database.execute_query(Q_GET_HISTORY)
    
    # TODO return generator
    # TODO reduce memory usage
    return articles_from_list(db.Database.main_database.fetchall(), liked=True)

def generate_sessionid(num_bytes=16):
    return uuid.UUID(bytes=Random.get_random_bytes(num_bytes))

def add_session():
    sid = str(generate_sessionid())
    db.Database.main_database.execute_query(Q_ADD_SESSIONID, [(sid,)])
    return sid

def delete_session(sid):
    db.Database.main_database.execute_query(Q_DELETE_SESSIONID, [(sid,)])

def check_password(password):
    return get_conf.config.password == password

def check_session_existance(sid):
    remove_old_sessions()
    db.Database.main_database.execute_query(Q_CHECK_SESSIONID, [(sid,)])
    return not not db.Database.main_database.fetchone() # Convert result to boolean

def remove_old_sessions():
    db.Database.main_database.execute_query(Q_REMOVE_OLD_SESSIONIDS)

def remove_session(sid):
    db.Database.main_database.execute_query(Q_REMOVE_SESSIONID, [(sid,)])

def get_var(name, default=None):
    db.Database.main_database.execute_query(Q_GET_VAR, [(name,)])
    try:
        return db.Database.main_database.fetchone()[0]
    except TypeError:
        return default

def set_var(name, value):
    mainDB = db.Database.main_database
    IntegrityError = mainDB.userData
    try:
        mainDB.execute_query(Q_ADD_VAR, [(name, value)])
    except IntegrityError:
        mainDB.con.rollback()
        mainDB.execute_query(Q_SET_VAR, [(value, name)])

def paginate_articles(articles, per_page=30):
    """Set a page number for each article"""
    
    current_page = 1
    i = 0
    
    for article in articles.values():
        if i >= per_page:
            i = 0
            current_page += 1
        
        article['page_number'] = current_page
        
        i += 1
    
    return current_page

def select_articles_from_page(page_number):
    mainDB = db.Database.main_database
    
    mainDB.execute_query(Q_SELECT_FROM_PAGE, [(page_number,)])
    articles = OrderedDict()
    
    # TODO return generator
    # TODO reduce memory usage
    for i in mainDB.fetchall():
        link = i[2]
        articles[link] = {'title': i[1],
                          'link': link,
                          'summary': i[3],
                          'source': i[4],
                          'fromrss': i[5],
                          'icon': i[6],
                          'color': i[7],
                          'page_number': page_number}
    
    return articles

def select_all_articles():
    mainDB = db.Database.main_database
    
    mainDB.execute_query(Q_SELECT_ALL_ARTICLES, [tuple()])
    articles = OrderedDict()
    # TODO return generator
    # TODO reduce memory usage
    for i in mainDB.fetchall():
        link = i[2]
        articles[link] = {'title': i[1],
                          'link': link,
                          'summary': i[3],
                          'source': i[4],
                          'fromrss': i[5],
                          'icon': i[6],
                          'color': i[7],
                          'page_number': i[8]}
    
    return articles

def clear_pages():
    mainDB = db.Database.main_database
    mainDB.execute_query(Q_CLEAR_ARTICLES, [tuple()])
    set_var('num_pages', '0')

def save_articles(articles):
    mainDB = db.Database.main_database
    IntegrityError = mainDB.userData
    
    clear_pages()
    
    num_pages = paginate_articles(articles)
    
    for article in articles.values():
        title = article['title']
        link = article['link']
        summary = article['summary']
        source = article['source']
        fromrss = article.get('fromrss', 0)
        icon = article.get('icon', '')
        color = article.get('color', '#000')
        page_number = article['page_number']
        parameters = [(title, link, summary, source, fromrss, icon, color, page_number)]
        
        try:
            mainDB.execute_query(Q_ADD_ARTICLE, parameters, commit=False)
        except IntegrityError:
            if mainDB.query_count > 0:
                mainDB.commit()
            mainDB.rollback()
    mainDB.commit()
    
    set_var('num_pages', str(num_pages))
