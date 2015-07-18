#!/usr/bin/env python
# -*- coding: utf-8 -*-

import imp
import os
import json
import hashlib
from TechParser.py2x import unicode_, encodestr

logdir = os.path.expanduser("~")
logdir = os.path.join(logdir, ".tech-parser")

config = None

def hash_string(string):
    return hashlib.md5(encodestr(unicode_(string))).hexdigest()

class Config(object):
    def __init__(self, hide=False, filename='', **kwargs):
        self.sites_to_parse = kwargs.get('sites_to_parse')
        
        for k,v in self.sites_to_parse.items():
            v['hash'] = hash_string(k)
            v.setdefault('priority', 1.0)
        
        self.rss_feeds = kwargs.get('rss_feeds')
        
        for k,v in self.rss_feeds.items():
            v['hash'] = hash_string(k)
            v.setdefault('priority', 1.0)
        
        self.interesting_words = kwargs.get('interesting_words')
        self.boring_words = kwargs.get('boring_words')
        self.update_interval = kwargs.get('update_interval')
        self.db = kwargs.get('db')
        self.db_path_variable = kwargs.get('db_path_variable', 'DATABASE_URL')
        if not hide or not self.db_path_variable:
            try:
                db_path = db_path = os.environ.get(self.db_path_variable)
                if db_path:
                    self.db_path = db_path
                else:
                    self.db_path = kwargs['db_path']
            except KeyError:
                pass
        self.host = kwargs.get('host')
        self.port = kwargs.get('port')
        self.num_threads = kwargs.get('num_threads')
        self.server = kwargs.get('server')
        self.save_articles = kwargs.get('save_articles')
        self.archive_db_path_variable = kwargs.get('archive_db_path_variable', 'ARCHIVE_DATABASE_URL')
        if not hide or not self.archive_db_path_variable:
            try:
                archive_db_path = os.environ.get(self.archive_db_path_variable)
                if archive_db_path:
                    self.archive_db_path = archive_db_path
                else:
                    self.archive_db_path = kwargs['archive_db_path']
            except KeyError:
                pass
        self.data_format = kwargs.get('data_format')
        self.password_variable = kwargs.get('password_variable', 'TechParser_PASSWORD')
        if not hide or not self.password_variable:
            try:
                password = os.environ.get(self.password_variable)
                if password:
                    self.password = password
                else:
                    self.password = kwargs['password']
            except KeyError:
                pass
        self.enable_pocket = kwargs.get('enable_pocket')
        self.json_config = kwargs.get('json_config', False)
        self.perfect_word_count = kwargs.get('perfect_word_count')
        self.enable_caching = kwargs.get('enable_caching', True)
        self.ngrams = kwargs.get('ngrams', 1)
        
        auto_fix_config(self, hide=hide)
        
        self.filename = filename
    
    @staticmethod
    def from_module(module, hide=False):
        d = {}
        d['sites_to_parse'] = {k: {'module': v['module'].__name__,
            'kwargs': v['kwargs'],
            'hash': hash_string(k),
            'enabled': v['enabled'],
            'priority': v.get('priority', 1.0)}
            for k,v in module.sites_to_parse.items()}
        d['rss_feeds'] = module.rss_feeds
        
        for k,v in d['rss_feeds'].items():
            v['hash'] =  hash_string(k)
            v.setdefault('priority', 1.0)
        
        d['interesting_words'] = module.interesting_words
        d['boring_words'] = module.boring_words
        d['update_interval'] = module.update_interval
        d['db'] = module.db
        d['db_path_variable'] = module.db_path_variable
        if not hide or not d['db_path_variable']:
            d['db_path'] = os.environ.get(d['db_path_variable'], module.db_path)
        d['host'] = module.host
        d['port'] = module.port
        d['num_threads'] = module.num_threads
        d['server'] = module.server
        d['save_articles'] = module.save_articles
        d['archive_db_path_variable'] = module.archive_db_path_variable
        if not hide or not d['archive_db_path_variable']:
            d['archive_db_path'] = os.environ.get(d['archive_db_path_variable'], module.archive_db_path)
        d['data_format'] = module.data_format
        d['password_variable'] = module.password_variable
        if not hide or not d['password_variable']:
            d['password'] = os.environ.get(d['password_variable'], module.password)
        d['enable_pocket'] = module.enable_pocket
        d['json_config'] = module.json_config
        d['perfect_word_count'] = module.perfect_word_count
        d['enable_caching'] = module.enable_caching
        d['ngrams'] = module.ngrams
        d['hide'] = hide
        
        return Config(**d)

def get_default_config():
    return __import__('TechParser.parser_config').parser_config

def get_config(fname):
    fname = os.path.expanduser(fname)
    if fname.endswith('.py'):
        config = imp.load_source('parser_config', fname)
        config.filename = fname
        return config
    else:
        with open(fname) as f:
            config = config_from_json(f.read())
            config.filename = fname
            return config

def set_config(parser_config):
    global config
    
    config = parser_config
    
    for k,v in config.sites_to_parse.items():
        v['hash'] = hash_string(k)

    for k,v in config.rss_feeds.items():
        v['hash'] = hash_string(k)

def set_config_from_fname(fname):
    set_config(get_config(fname))

def set_default_config():
    set_config(get_default_config())

def set_config_from_logdir(fname):
    set_config_from_fname(os.path.join(logdir, fname))

def set_user_config():
    set_config_from_logdir('user_parser_config.py')

def config_from_json(json_str):
    conf = Config(**json.loads(json_str))
    conf.sites_to_parse = {k: {'module': __import__(v['module'], fromlist=['']),
                               'kwargs': v['kwargs'], 'enabled': v['enabled'],
                               'priority': v.get('priority', 1.0)}
                           for k,v in conf.sites_to_parse.items()}
    
    return conf

def set_config_auto():
    try:
        set_user_config()
    except IOError:
        set_default_config()
    
    if hasattr(config, 'json_config') and config.json_config:
        try:
            set_config_from_logdir('user_parser_config.json')
        except ValueError:
            pass
        except IOError:
            pass

def setdefault(obj, attr, value=None):
    try:
        getattr(obj, attr)
    except AttributeError:
        setattr(obj, attr, value)

def getSourceData(source, default=None):
    for k, v in config.sites_to_parse.items():
        if v['module'].SHORT_NAME == source:
            return (k, v)
    
    for k, v in config.rss_feeds.items():
        if v['short-name'] == source:
            return (k, v)
    
    return default

def auto_fix_config(conf=None, hide=False):
    if conf is None:
        conf = config
    setdefault(conf, 'sites_to_parse', {})
    
    for v in conf.sites_to_parse.values():
        v.setdefault('enabled', True)
    
    setdefault(conf, 'rss_feeds', {})
    setdefault(conf, 'interesting_words', set())
    setdefault(conf, 'boring_words', set())
    setdefault(conf, 'host', '0.0.0.0')
    setdefault(conf, 'port', 8080)
    setdefault(conf, 'num_threads', 2)
    setdefault(conf, 'save_articles', False)
    setdefault(conf, 'db', 'sqlite')
    setdefault(conf, 'server', 'auto')
    setdefault(conf, 'update_interval', 1800)
    setdefault(conf, 'archive_db_path_variable', '')
    if not hide:
        setdefault(conf, 'archive_db_path',
                   os.environ.get(conf.archive_db_path_variable, 'default'))
    setdefault(conf, 'db_path_variable', '')
    if not hide:
        setdefault(conf, 'db_path', os.environ.get(conf.db_path_variable, ''))
    setdefault(conf, 'data_format', 'pickle')
    setdefault(conf, 'password_variable', '')
    if not hide:
        setdefault(conf, 'password', os.environ.get(conf.password_variable, ''))
    setdefault(conf, 'enable_pocket', False)
    setdefault(conf, 'json_config', False)
    setdefault(conf, 'perfect_word_count', (25, 50, 100, 150, 300, 600, 1200))
    setdefault(conf, 'enable_caching', True)
    setdefault(conf, 'ngrams', 1)
