#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import json
import datetime
import math
import codecs
import hashlib
from base64 import binascii
hexlify = binascii.hexlify

from mako.lookup import TemplateLookup
import bottle
from bottle import route, run, static_file, request, redirect, response
from collections import OrderedDict

from TechParser import get_conf, recommend, save
from TechParser.db_functions import *
from TechParser.py2x import unicode_, unicode__, range, urlencode, pickle, parse_qs

REMOVE_TAGS_REGEX = re.compile('<.*?>')

module_path = os.path.dirname(os.path.realpath(__file__))
template_dir_path = os.path.join(module_path, "templates")
static_dir_path = os.path.join(module_path, "static")
logdir = os.path.expanduser("~")
logdir = os.path.join(logdir, ".tech-parser")

mylookup = TemplateLookup(directories=template_dir_path,
                          default_filters=["decode.utf8"],
                          input_encoding="utf-8", output_encoding="utf-8")

def hash_string(string):
    return hashlib.md5(string.encode()).hexdigest()

liked_links = set()
disliked_links = set()
errors = {}
cache = {'templates': {}, 'pages': {}, 'history': {}, 'blacklist': {}, 'cached_main': {}}

CSS_NAME_REGEX = re.compile(r'-?[_a-zA-Z]+[_a-zA-Z0-9-]*$')
COMMA_SEPARATE_REGEX = re.compile(r'[ ]*,[ ]*')

def encode_string(s):
    if isinstance(s, unicode__):
        return s.encode('utf8')
    return s

def remove_tags(s):
    return REMOVE_TAGS_REGEX.sub('', s)

def splitByCommas(text):
    return [i for i in COMMA_SEPARATE_REGEX.split(text) if i]

def split_into_pages(articles, n=30):
    """Split list into pages"""
    
    # TODO return only selected page
    
    pages = []
    i = 0
    
    for j in articles:
        if i >= n:
            i = 0
        
        if i == 0:
            pages.append([j])
        else:
            # TODO cache pages[-1]
            pages[-1].append(j)
        
        i += 1
    
    return pages

def get_page(lst, n=30, page_num=1):
    i = 0
    j = 1
    for k in lst:
        if i >= n:
            i = 0
            j += 1
            if j > page_num:
                break
        if j == page_num:
            yield k
        i += 1

def get_sid():
    return request.get_cookie('sid', '')

def logged_in():
    password = not len(get_conf.config.password)
    return check_session_existance(get_sid()) or password

def encode_url(url):
    return urlencode({'': encode_string(url)})[1:]

def login_required(func):
    def newfunc(*args, **kwargs):
        if logged_in():
            return func(*args, **kwargs)
        redirect('/login/?return_to={0}'.format(encode_url(request.path)))
    return newfunc

class Validator(object):
    def __init__(self):
        self.errors = {}
    
    def add_error(self, location, msg):
        """Add error to error list"""
        
        self.errors.setdefault(location, [])
        self.errors[location].append(msg)
    
    def validate(self, **data):
        """Validate configuration"""
        
        if data['type'] == 'variables':
            # Validate variables
            try:
                update_interval = int(data['update_interval'])
                if update_interval <= 0:
                    self.add_error('update_interval', 'update_interval should be bigger than 0')
            except ValueError:
                self.add_error('update_interval', 'Update interval should be a number')
            if data['db'] not in {'sqlite', 'postgresql'}:
                self.add_error('db', 'Database should be either sqlite or postgresql')
            try:
                num_threads = int(data['num_threads'])
                if num_threads < 1:
                    self.add_error('num_threads', 'Number of threads should be more than 0')
                if num_threads > 10:
                    self.add_error('num_threads', 'Maximum number of threads is 10')
            except ValueError:
                self.add_error('num_threads', 'Number of threads should be an integer between 1 and 10')
            
            if data['server'] not in bottle.server_names:
                servers = map(lambda x: '<a href="javascript:void(0)" onclick="$(\'input[name=v_server]\').val($(this).text())">{0}</a>'.format(x), bottle.server_names)
                self.add_error('server', 'Server must be one of these: {0}'.format(', '.join(servers)))
            try:
                port = int(data['port'])
                if port > 65535 or port < 1:
                    self.add_error('port', 'Port should be an integer between 1 and 65535')
            except ValueError:
                self.add_error('port', 'Port should be an integer')
            
            if data['data_format'] not in {'json', 'pickle', 'db'}:
                self.add_error('data_format', "data_format should be 'json', 'pickle' or 'db'")
            
            for i in data['perfect_word_count']:
                if i < 1:
                    self.add_error('perfect_word_count', 'Each number in perfect_word_count should be greater than 0')
            try:
                ngrams = int(data['ngrams'])
                if ngrams < 1:
                    self.add_error('ngrams', 'ngrams must be greater than 0')
            except ValueError:
                self.add_error('ngrams', 'ngrams must be an integer')
        elif data['type'] == 'rss_feeds':
            feed = data['rss_feed']
            feed_name = data['rss_feed_name']
            h = feed['hash']
            location = 'rss_feed_{0}'.format(h)
            if not len(feed_name):
                self.add_error(location, 'Feed name cannot be empty')
            if not len(feed['short-name']):
                self.add_error(location, 'Feed short name cannot be empty')
            if not feed['url'].startswith('http://') and not feed['url'].startswith('https://'):
                self.add_error(location, 'Invalid URL')
            if feed['icon'] and not feed['icon'].startswith('http://') and not feed['icon'].startswith('https://'):
                 self.add_error(location, 'Invalid icon URL')
            if not CSS_NAME_REGEX.match(feed['short-name']):
                self.add_error(location, 'Short name must be a valid CSS name')
            try:
                priority = float(feed['priority'])
                if priority < 0:
                    self.add_error(location, 'Priority cannot be less than 0')
            except ValueError:
                sekf.add_error(location, 'Priority must be a floating point number')

        return self.errors

def load_articles(filename="articles_dumped"):
    """Load articles from ~/.tech-parser/<filename>"""
    
    try:
        return save.load_from_somewhere(os.path.join(logdir, filename))
    except (IOError, pickle.PickleError, TypeError):
        return OrderedDict()

@route('/static/<filename:path>')
def serve_static(filename):
    """Serve static files"""
    
    return static_file(filename, root=static_dir_path)

@route('/histadd/<addr:path>')
@login_required
def add_to_history(addr):
    recommend.add_article(addr)
    liked_links.add(addr)
    remove_cache()
    
@route('/blacklistadd/<addr:path>')
@login_required
def add_to_blacklist(addr):
    recommend.add_article_to_blacklist(addr)
    disliked_links.add(addr)
    remove_cache()

@route('/blacklistrm/<addr:path>')
@login_required
def rm_from_blacklist(addr):
    recommend.remove_from_blacklist(addr)
    try:
        disliked_links.remove(addr)
    except KeyError:
        pass
    remove_cache()

@route('/histrm/<addr:path>')
@login_required
def rm_from_history(addr):
    recommend.remove_from_history(addr)
    try:
        liked_links.remove(addr)
    except KeyError:
        pass
    remove_cache()

def remove_cache(name=None):
    path = os.path.join(get_conf.logdir, 'cache')
    try:
        contents = os.listdir(path)
    except OSError:
        return
    if name:
        contents = filter(lambda x: x.startswith('cached_' + name), contents)
    for i in contents:
        os.remove(os.path.join(path, i))

@route('/history')
@route('/history/<page_number>')
@login_required
def show_history(page_number=1):
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1
    
    q = unicode_(request.GET.getunicode('q', ''))
    
    html = get_cache('cached_history_{0}_{1}'.format(page_number, hexlify(q.encode('utf8')).decode('utf8')))
    if html:
        return html
    
    history_page = cache['templates'].get('history.html')
    if not history_page:
        history_page = mylookup.get_template('history.html')
        cache['templates']['history.html'] = history_page
    
    # TODO cache data
    articles = recommend.get_interesting_articles()
    
    if q:
        qs = q.lower().split()
        articles = iter(filter(lambda x: has_words(qs, x), articles))
    
    articles = iter(map(lambda x: escape_link(x), articles))
    
    requested_page = list(get_page(articles, 30, page_num=page_number))
    num_pages = page_number
    try:
        next(articles)
        num_pages += 1
    except StopIteration:
        pass
    
    html = history_page.render(articles=requested_page,
                               num_pages=num_pages,
                               page_num=page_number,
                               q=q, page='history',
                               config=get_conf.config).decode('utf8')
    if len(requested_page):
        cache_data('cached_history_{0}_{1}'.format(page_number, hexlify(q.encode('utf8')).decode('utf8')), html)
    return html

@route('/blacklist')
@route('/blacklist/<page_number>')
@login_required
def show_blacklist(page_number=1):
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1

    q = unicode_(request.GET.getunicode('q', ''))
    
    html = get_cache('cached_blacklist_{0}_{1}'.format(page_number, hexlify(q.encode('utf8')).decode('utf8')))
    if html:
        return html
    
    blacklist_page = cache['templates'].get('blacklist.html')
    if not blacklist_page:
        blacklist_page = mylookup.get_template('blacklist.html')
        cache['templates']['blacklist.html'] = blacklist_page
    
    # TODO cache data
    articles = recommend.get_blacklist()
    
    if q:
        qs = q.lower().split()
        articles = iter(filter(lambda x: has_words(qs, x), articles))
    
    articles = iter(map(lambda x: escape_link(x), articles))
    
    requested_page = list(get_page(articles, 30, page_num=page_number))
    num_pages = page_number
    try:
        next(articles)
        num_pages += 1
    except StopIteration:
        pass
    
    html = blacklist_page.render(articles=requested_page,
                                 num_pages=num_pages,
                                 page_num=page_number,
                                 q=q, page='blacklist',
                                 config=get_conf.config).decode('utf8')
    if len(requested_page):
        cache_data('cached_blacklist_{0}_{1}'.format(page_number, hexlify(q.encode('utf8')).decode('utf8')), html)
    return html

def has_words(qs, article):
    """Check if article contains words"""
    
    text = remove_tags(unicode_(article['title'])).lower() \
    + remove_tags(unicode_(article['summary'])).lower()
    
    for i in qs:
        if i not in text:
            return False
    return True

def escape_link(article):
    """Escape HTML tags, etc."""
    
    article['original_link'] = article['link']
    article['link'] = encode_url(article['link'])
    
    return article

def set_liked(articles):
    for article in articles:
        link = article['original_link']
        article['liked'] = link in liked_links
        article['disliked'] = link in disliked_links

def cache_data(name, value):
    if get_conf.config.enable_caching:
        path = os.path.join(get_conf.logdir, 'cache')
        if not os.path.exists(path):
            os.makedirs(path)
        with codecs.open(os.path.join(path, name), 'w', encoding='utf8') as f:
            f.write(value)

def get_cache(name, default=None):
    try:
        with codecs.open(os.path.join(get_conf.logdir, 'cache', name), encoding='utf8') as f:
            return f.read()
    except IOError:
        return default

@route("/")
@route("/<page_number>")
@login_required
def article_list(page_number=1):
    """Show list of articles | Search for articles"""
    
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1

    q = unicode_(request.GET.getunicode('q', ''))
    if not get_conf.config.enable_random or q:
        html = get_cache('cached_main_{0}_{1}'.format(page_number, hexlify(q.encode('utf8')).decode('utf8')))
        if html:
            return html

    main_page = cache['templates'].get('articles.html')
    if not main_page:
        main_page = mylookup.get_template("articles.html")
        cache['templates']['articles.html'] = main_page
    
    cache_page = False
    
    if get_conf.config.data_format == 'db':
        if q:
            articles = select_all_articles()
            qs = q.lower().split()
            requested_page = []
            j = 0
            k = (page_number - 1) * 30
            n = 0
            append = requested_page.append
            
            for article in articles:
                if has_words(qs, article):
                    j += 1
                    if j > k:
                        n += 1
                        if n == 31:
                            break
                        else:
                            append(escape_link(article))
            
            num_pages = page_number - 1 + math.ceil(n / 30.0)
            cache_page = True
        else:
            requested_page = select_articles_from_page(page_number)
            requested_page = list(map(lambda x: escape_link(x), requested_page))
            num_pages = int(get_var('num_pages', 0))
            if num_pages == 0:
                num_pages += 1
                cache_page = False
            else:
                cache_page = True
    else:
        # TODO reduce memory usage
        try:
            articles = load_articles()
        except IOError:
            dump_articles()
            articles = load_articles()
    
        if q:
            qs = q.lower().split()
            articles = iter(filter(lambda x: has_words(qs, x), articles.values()))
            articles = iter(map(lambda x: escape_link(x), articles))
            cache_page = True
        else:
            articles = iter(map(lambda x: escape_link(x), articles.values()))
        
        articles = split_into_pages(articles, 30)
        num_pages = len(articles)
        
        try:
            requested_page = articles[page_number-1]
        except IndexError:
            requested_page = []
    
    if get_conf.config.enable_random and not q:
        random_articles = [escape_link(x) for x in articles_from_list(getRandomArticles(page_number))]
        set_liked(random_articles)
    else:
        random_articles = []
    
    set_liked(requested_page)
    
    html = main_page.render(articles=requested_page,
                            random_articles=random_articles,
                            num_pages=num_pages,
                            page_num=page_number,
                            q=q, page='main',
                            config=get_conf.config,
                            is_parsing=get_var('parsing', '0') == '1').decode('utf8')
    if not cache_page:
        cache_page = bool(len(requested_page))
    
    if cache_page and not get_conf.config.enable_random and not q:
        cache_data('cached_main_{0}_{1}'.format(page_number, hexlify(q.encode('utf8')).decode('utf8')), html)
    return html

@route('/login')
@route('/login/')
@route('/login/', method='POST')
def login():
    ret = request.GET.getunicode('return_to', '/')
    if logged_in():
        redirect(ret)
    else:
        password = request.POST.getunicode('password', None)
        if password is not None and check_password(password):
            new_sid = add_session()
            now = datetime.datetime.now()
            expiration_date = datetime.datetime(now.year+1, now.month,
                now.day, now.hour, now.minute, now.second, now.microsecond)
            response.set_cookie('sid', new_sid, path='/',
                expires=expiration_date)
            redirect(ret)
        else:
            # TODO cache template
            template = mylookup.get_template('login.html')
            return template.render(return_path=encode_url(ret),
                error=password is not None)

@route('/logout')
@route('/logout/')
def logout():
    if not logged_in():
        redirect('/login/')
    else:
        remove_session(get_sid())
        response.set_cookie('sid', '', expires=datetime.datetime(1970, 1, 1, 0, 0, 0))
        redirect('/login/')

@route('/edit')
@route('/edit/')
@login_required
def edit_config():
    global errors
    
    template = mylookup.get_template('edit.html')
    config = get_conf.Config.from_module(get_conf.config)
    config.interesting_words = json.dumps(config.interesting_words, ensure_ascii=False)
    config.boring_words = json.dumps(config.boring_words, ensure_ascii=False)
    
    for parser in config.sites_to_parse.values():
        parser['kwargs'] = json.dumps(parser['kwargs'])
    dup_errors = errors
    errors = {}
    
    return template.render(config=config, page='edit', q='',
                           errors=dup_errors,
                           num_pages=1)

@route('/update/', method='POST')
@login_required
def update_config():
    type_ = request.POST.getunicode('type')
    validator = Validator()
    response = {}
    
    if type_ == 'variables':
        data = {}
        data['update_interval'] = request.POST.getunicode('v_update_interval', get_conf.config.update_interval)
        
        data['db'] = request.POST.getunicode('v_db', get_conf.config.db)
        data['db_path_variable'] = request.POST.getunicode('v_db_path_var')
        data['db_path'] = request.POST.getunicode('v_db_path', get_conf.config.db_path)
        
        data['host'] = request.POST.getunicode('v_host', get_conf.config.host)
        data['port'] = request.POST.getunicode('v_port', get_conf.config.port)
        
        data['num_threads'] = request.POST.getunicode('v_num_threads', get_conf.config.num_threads)
        
        data['server'] = request.POST.getunicode('v_server', get_conf.config.server)
        
        data['save_articles'] = request.POST.getunicode('v_save_articles', False) == 'on'
        
        data['archive_db_path_variable'] = request.POST.getunicode('v_archive_db_path_var')
        data['archive_db_path'] = request.POST.getunicode('v_archive_db_path', get_conf.config.archive_db_path)
        
        data['data_format'] = request.POST.getunicode('v_data_format', get_conf.config.data_format)
        
        data['password_variable'] = request.POST.getunicode('v_password_var')
        data['password'] = request.POST.getunicode('v_password', get_conf.config.password)
        
        data['enable_pocket'] = request.POST.getunicode('v_enable_pocket', False) == 'on'
        data['type'] = type_
        perfect_word_count = request.POST.getunicode('v_perfect_word_count')
        
        if perfect_word_count:
            try:
                perfect_word_count = tuple(int(i) for i in splitByCommas(perfect_word_count))
            except ValueError:
                validator.add_error('perfect_word_count', 'Each number in perfect_word_count should be an integer')
                perfect_word_count = tuple()
        else:
            if perfect_word_count is None:
                perfect_word_count = get_conf.config.perfect_word_count
            else:
                perfect_word_count = tuple()
        
        data['perfect_word_count'] = perfect_word_count
        data['enable_caching'] = request.POST.getunicode('v_enable_caching', False) == 'on'
        data['ngrams'] = request.POST.getunicode('v_ngrams', get_conf.config.ngrams)
        data['enable_random'] = request.POST.getunicode('v_enable_random', False) == 'on'
        
        validator.validate(**data)
        
        if not validator.errors.get('update_interval'):
            get_conf.config.update_interval = int(data['update_interval'])
        if not validator.errors.get('db'):
            get_conf.config.db = data['db']
        get_conf.config.db_path_variable = data['db_path_variable']
        get_conf.config.db_path = data['db_path']
        get_conf.config.host = data['host']
        if not validator.errors.get('port'):
            get_conf.config.port = data['port']
        if not validator.errors.get('num_threads'):
            get_conf.config.num_threads = int(data['num_threads'])
        if not validator.errors.get('server'):
            get_conf.config.server = data['server']
        get_conf.config.archive_db_path_variable = data['archive_db_path_variable']
        get_conf.config.archive_db_path = data['archive_db_path']
        get_conf.config.data_format = data['data_format']
        get_conf.config.password_variable = data['password_variable']
        get_conf.config.password = data['password']
        get_conf.config.enable_pocket = data['enable_pocket'] 
        get_conf.config.perfect_word_count = data['perfect_word_count']
        get_conf.config.ngrams = data['ngrams']
        if not validator.errors.get('perfect_word_count'):
            get_conf.config.perfect_word_count = perfect_word_count
        get_conf.config.enable_caching = data['enable_caching']
        if not validator.errors.get('ngrams'):
            get_conf.config.ngrams = int(data['ngrams'])
        get_conf.config.enable_random = data['enable_random']
    elif type_ == 'parsers':
        for parser in get_conf.config.sites_to_parse.values():
            h = parser['hash']
            enabled = request.POST.getunicode('parser_{0}'.format(h)) in {'on', True}
            kwargs = request.POST.getunicode('kwargs_{0}'.format(h), parser['kwargs'])
            priority = request.POST.getunicode('priority_{0}'.format(h), parser.get('priority', '1.0'))
            try:
                priority = float(priority)
                if priority < 0:
                    validator.add_error('parser_{0}'.format(h), 'Priority cannot be less than 0')
                else:
                    parser['priority'] = priority
            except ValueError:
                validator.add_error('parser_{0}'.format(h), 'Priority must be a floating point number')
            
            try:
                parser['kwargs'] = json.loads(kwargs)
            except (ValueError, TypeError):
                validator.add_error('parser_{0}'.format(h), 'Parser arguments should be in form of JSON')
            
            parser['enabled'] = enabled
    elif type_ == 'rss_feeds':
        response['deleted'], response['modified'] = [], []
        for feed_name, feed in get_conf.config.rss_feeds.items():
            h = feed['hash']
            data = {'rss_feed': {'hash': h}, 'type': type_}
            if request.POST.getunicode('is_deleted_{0}'.format(h), '0') == '1':
                response['deleted'].append((feed_name, h))
                continue
            data['rss_feed_name'] = request.POST.getunicode('name_{0}'.format(h), feed_name)
            new_hash = hash_string(data['rss_feed_name'])
            data['rss_feed']['hash'] = new_hash
            data['rss_feed']['short-name'] = request.POST.getunicode('sn_{0}'.format(h), feed['short-name'])
            data['rss_feed']['url'] = request.POST.getunicode('url_{0}'.format(h), feed['url'])
            data['rss_feed']['icon'] = request.POST.getunicode('icon_{0}'.format(h), feed['icon'])
            data['rss_feed']['color'] = request.POST.getunicode('color_{0}'.format(h), feed['color'])
            data['rss_feed']['enabled'] = request.POST.getunicode('enabled_{0}'.format(h), '0') == '1'
            data['rss_feed']['priority'] = request.POST.getunicode('priority_{0}'.format(h), '1.0')
            
            validator.validate(**data)
            
            if 'rss_feed_{0}'.format(new_hash) not in validator.errors:
                rss_feed = data['rss_feed']
                short_name = rss_feed['short-name']
                name = data['rss_feed_name']
                url = rss_feed['url']
                icon = rss_feed['icon']
                color = rss_feed['color']
                enabled = rss_feed['enabled']
                priority = rss_feed['priority']
                
                if short_name != feed['short-name']:
                    response['modified'].append(('sn_{0}'.format(h), short_name))
                if name != feed_name:
                    response['modified'].append(('name_{0}'.format(h), name))
                if url != feed['url']:
                    response['modified'].append(('url_{0}'.format(h), url))
                if icon != feed['icon']:
                    response['modified'].append(('icon_{0}'.format(h), icon))
                if color != feed['color']:
                    response['modified'].append(('color_{0}'.format(h), color))
                if enabled != feed['enabled']:
                    response['modified'].append(('enabled_{0}'.format(h), enabled))
                if priority != feed['priority']:
                    response['modified'].append(('priority_{0}'.format(h), priority))
                if new_hash != h:
                    response['modified'].append(('hash_{0}'.format(h), new_hash))
                feed['short-name'] = short_name
                feed['url'] = url
                feed['icon'] = icon
                feed['color'] = color
                feed['enabled'] = enabled
                feed['priority'] = float(priority)
                feed['hash'] = new_hash
                get_conf.config.rss_feeds[data['rss_feed_name']] = feed
                if data['rss_feed_name'] != feed_name:
                    get_conf.config.rss_feeds.pop(feed_name)
        for k in response['deleted']:
            get_conf.config.rss_feeds.pop(k[0])
        
        if request.POST.getunicode('new_feed', '1') == '0':
            data = {'rss_feed': {'hash': 'new_feed'}, 'type': 'rss_feeds'}
            data['rss_feed_name'] = request.POST.getunicode('new_feed_name')
            if data['rss_feed_name'] in get_conf.config.rss_feeds:
                validator.add_error('rss_feed_new_feed', 'RSS feed with such name already exists')
            data['rss_feed']['short-name'] = request.POST.getunicode('new_feed_sn')
            data['rss_feed']['url'] = request.POST.getunicode('new_feed_url')
            data['rss_feed']['icon'] = request.POST.getunicode('new_feed_icon')
            data['rss_feed']['color'] = request.POST.getunicode('new_feed_color')
            data['rss_feed']['enabled'] = request.POST.getunicode('new_feed_enabled', '0') == '1'
            data['rss_feed']['priority'] = request.POST.getunicode('new_feed_priority', '1.0')
            validator.validate(**data)
            data['rss_feed']['hash'] = hash_string(data['rss_feed_name'])
            if 'rss_feed_new_feed' not in validator.errors:
                get_conf.config.rss_feeds[data['rss_feed_name']] = {'short-name': data['rss_feed']['short-name'],
                                                            'url': data['rss_feed']['url'],
                                                            'icon': data['rss_feed']['icon'],
                                                            'color': data['rss_feed']['color'],
                                                            'enabled': data['rss_feed']['enabled'],
                                                            'priority': float(data['rss_feed']['priority']),
                                                            'hash': data['rss_feed']['hash']}
                response['new_feed'] = data['rss_feed']
                response['new_feed']['name'] = data['rss_feed_name']
    elif type_ == 'interesting_words':
        try:
            get_conf.config.interesting_words = json.loads(request.POST.getunicode('t_interesting_words', '[]'), encoding='utf-8')
        except (ValueError, TypeError):
            validator.add_error('interesting_words', 'interesting_words should be a JSON object')
    elif type_ == 'boring_words':
        try:
            get_conf.config.boring_words = json.loads(request.POST.getunicode('t_boring_words', '[]'), encoding='utf-8')
        except (ValueError, TypeError):
            validator.add_error('boring_words', 'boring_words should be a JSON object')

    save.write_config(get_conf.config, get_conf.config.filename)
    response['errors'] = validator.errors
    
    return json.dumps(response)
