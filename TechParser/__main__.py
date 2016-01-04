#!/usr/bin/env python
# -*- coding: utf-8 -*-

from random import shuffle
import os
import sys
import re
import multiprocessing
import argparse
import sqlite3
import traceback
import signal
import atexit
from time import time, sleep

from operator import itemgetter
from collections import OrderedDict

from bottle import default_app

from Daemo import Daemon, DaemonError

from TechParser import get_conf, recommend, parser, db, server, save, auto_alter
from TechParser.db_functions import set_var, get_var, get_interesting_articles
from TechParser.db_functions import get_blacklist, trainClassifier, saveClassifier
from TechParser.query import Q_SAVE_ARTICLES
from TechParser.py2x import range, urlencode

running_as_daemon = False
# TODO add description for this variable
parsing = False
lock_enabled = True

if get_conf.config is None:
    get_conf.set_config_auto()

get_conf.auto_fix_config()

logdir = server.logdir

if not os.path.exists(logdir):
    os.mkdir(logdir)

if not os.path.exists(os.path.join(logdir, "__init__.py")):
    open(os.path.join(logdir, "__init__.py"), "w").close()

if not os.path.exists(os.path.join(logdir, "user_parser_config.py")):
    f = open(os.path.join(logdir, "user_parser_config.py"), "w")
    default_config = open(os.path.join(server.module_path, "parser_config.py"))
    f.write(default_config.read())
    default_config.close()
    f.close()

def log(text, f=sys.stdout, add_newline=True, clear_str=False,
    ignore_daemon=False):
    
    if add_newline:
        text += "\n"
    
    if (clear_str or running_as_daemon) and not ignore_daemon:
        text = re.sub(r"\033\[(\d+|\d+;\d+)m", "", text)
    
    f.write(text)
    f.flush()

def logerr(*args, **kwargs):
    kwargs['f'] = sys.stderr
    log(*args, **kwargs)

def simple_plural(n, s=""):
    n = str(n)
    if n.endswith("1") and not n.endswith("11"):
        return s
    else:
        return s + "s"

def show_progress(s, shared_object):
    progress = round(shared_object.value, 2)
    return "\033[0;32m[{0}%]\033[0m ".format(progress)+s

def parse_site(queue, articles, progress, total_length):
    """Worker for parsing articles"""
    
    config = get_conf.config
    num = 50.0 / total_length # Progress change
    s = "Got {0} article{1} from {2}"
    
    while not queue.empty():
        site = queue.get()
        site_name = site[1]
        site_type = site[0] 
        
        update_progress(progress, num)
        log(show_progress("Parsing articles from {0}".format(site_name), progress))
        
        if site_type == 'r':
            d = config.rss_feeds[site_name]
            url = d.get('url', '')
            short_name = d.get('short-name', 'unknown')
            icon = d.get('icon', '')
            color = d.get('color', '#000')
            if not len(color):
                color = '#000'
            if not len(icon):
                icon = ''
            
            try:
                # Get articles
                new_articles = parser.parse_rss(url, short_name, icon, color)
                
                # Add articles to queue
                _put = articles.put # OPTIMISATION
                for i in new_articles:
                    _put(i)
                
                update_progress(progress, num)
                
                len_new = len(new_articles)
                
                log(show_progress(s.format(len_new, simple_plural(len_new), site_name), progress))
            except Exception as error:
                logerr('Failed to parse articles from {0}'.format(site))
                logerr(traceback.format_exc())
        else:
            d = config.sites_to_parse[site_name]
            module = d["module"]
            kwargs = d["kwargs"]
            
            try:
                # Get articles
                new_articles = module.get_articles(**kwargs)
                
                # Add articles to queue
                _put = articles.put # OPTIMISATION
                for i in new_articles:
                    _put(i)
                
                update_progress(progress, num)
                
                len_new = len(new_articles)
                
                log(show_progress(s.format(len_new, simple_plural(len_new), site_name), progress))
            except Exception:
                logerr('Failed to parse articles from {0}'.format(site))
                logerr(traceback.format_exc())

def update_progress(shared_object, num):
    shared_object.value += num

def getEnabled(d):
    """Returns items (x) of the dictionary (d) that have x['enabled'] == True"""
    
    for k, v in d.items():
        if v['enabled']:
            yield (k, v)

def generator_length(g):
    length = 0
    for i in g:
        length += 1
    return length

def dump_articles(filename="articles_dumped"):
    """Dump articles to ~/.tech-parser/<filename>"""
    
    global parsing
    
    if parsing or (lock_enabled and get_var('parsing', '0') == '1'):
        log('Already parsing articles. Hold on.')
        return
    
    try:
        set_var('parsing', '1')
        parsing = True
        
        m = multiprocessing.Manager()
        
        articles = m.Queue()
    
        progress = m.Value('d', 0.0)
        
        main_queue = m.Queue()
        
        enabled_parsers = dict(getEnabled(get_conf.config.sites_to_parse))
        enabled_feeds = dict(getEnabled(get_conf.config.rss_feeds))
        total_length = len(enabled_parsers.keys()) + len(enabled_feeds.keys())
        
        for k in enabled_parsers.keys():
            main_queue.put(('p', k))
                
        for k in enabled_feeds.keys():
            main_queue.put(('r', k))
                
        pool = multiprocessing.Pool(processes=get_conf.config.num_threads)
        
        for i in range(get_conf.config.num_threads):
            pool.apply_async(parse_site, (main_queue, articles, progress, total_length))
        
        pool.close()
        pool.join()
                            
        try:
            data = server.load_articles()
            if isinstance(data, OrderedDict):
                links_before = set(server.load_articles().keys())
            else:
                links_before = {i['link'] for i in server.load_articles()}
        except ValueError:
            links_before = set()
            
        list_articles = []
        _append = list_articles.append # OPTIMISATION
        _get = articles.get # OPTIMISATION
        _empty = articles.empty # OPTIMISATION
        
        links = {i['link'] for i in get_interesting_articles()}
        links.update({i['link'] for i in get_blacklist()})
        
        while not _empty():
            article = _get()
            link = article['link']
            if link not in links:
                _append(article)
                links.add(link)
        
        log("Total articles: %d" %(len(list_articles)))
        log("New articles: %d"
            %(len([i for i in list_articles if i['link'] not in links_before])))
        
        if get_conf.config.save_articles:
            log("Saving articles to archive...")
            archiveDB = db.Database.databases['Archive']
            IntegrityError = archiveDB.userData # userData contains exception
            
            for article in list_articles:
                title = article["title"]
                link = article["link"]
                source = article["source"]
                
                try:
                    archiveDB.execute_query(Q_SAVE_ARTICLES, [(title, link, source)], commit=False)
                except IntegrityError:
                    if archiveDB.query_count > 0:
                        archiveDB.commit()
                    archiveDB.rollback()
            archiveDB.commit()
                
        num = generator_length(recommend.get_interesting_articles())
        num += generator_length(recommend.get_blacklist())
            
        if num >= 20:
            log("Ranking articles...")
            list_articles = sorted(recommend.rank_articles(list_articles), key=itemgetter(1), reverse=True)
            ordered = OrderedDict([(i[0]['link'], i[0]) for i in list_articles])
        else:
            log("Shuffling articles...")
            shuffle(list_articles)
            ordered = OrderedDict([(i['link'], i) for i in list_articles])
        
        log("Dumping articles...")
        
        path = os.path.join(os.path.expanduser("~"), ".tech-parser")
        path = os.path.join(path, filename)
        
        save.dump_somewhere(ordered, path)
        server.remove_cache()
    finally:
        set_var('parsing', '0')
        parsing = False

def dump_articles_per(s):
    """Dump articles per <s> seconds"""
    
    # Reopen databases to avoid OperationalError
    db.Database.main_database.con.close()
    db.Database.main_database.open()
    try:
        archiveDB = db.Database.databases['Archive']
        archiveDB.con.close()
        archiveDB.open()
    except KeyError:
        pass
    
    while True:
        if int(time()) % s == 0:
            dump_articles()
        sleep(1)

class ParserDaemon(Daemon):
    def __init__(self):
        pidfile = os.path.join(logdir, "tech-parser.pid")
        so = open(os.path.join(logdir, "output.log"), "a+")
        se = open(os.path.join(logdir, "error.log"), "a+")
        if os.stat(so.name).st_size > 102400:
            so.truncate()
        if os.stat(se.name).st_size > 102400:
            se.truncate()
        
        super(ParserDaemon, self).__init__(pidfile, stdout=so, stderr=se)
    
    def onStart(self):
        run_server(host=get_conf.config.host, port=get_conf.config.port)

def is_hostname(hostname):
    if len(hostname) > 255:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1]
    allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))

def run_server(host, port):
    config = get_conf.config
    
    def targetFunc():
        atexit.register(lambda: set_var('running', '0') if parsing else None)
        lmbd = lambda _,__: sys.exit(0)
        signal.signal(signal.SIGTERM, lmbd)
        signal.signal(signal.SIGABRT, lmbd)
        dump_articles_per(config.update_interval)
    
    p1 = multiprocessing.Process(target=targetFunc)
    atexit.register(p1.terminate)
    
    if not running_as_daemon:
        lmbd = lambda _,__: sys.exit(0)
        signal.signal(signal.SIGTERM, lmbd)
        signal.signal(signal.SIGABRT, lmbd)
    
    p1.start()
    
    # Reopen databases to avoid OperationalError
    db.Database.main_database.con.close()
    db.Database.main_database.open()
    try:
        archiveDB = db.Database.databases['Archive']
        archiveDB.con.close()
        archiveDB.open()
    except KeyError:
        pass
    
    server.run(host=host, port=port, server=config.server)

def main(arguments):
    global lock_enabled
    
    arg_parser = argparse.ArgumentParser(description="""\
Article parser.
Available commands: start|stop|restart|update|run HOST:PORT|lock|unlock|locked?|rerank|clean cache""")
    
    arg_parser.add_argument("action", nargs="+",
        action="store", default=[], help="Action to run")
    arg_parser.add_argument("--config", help="Path to configuration")
    arg_parser.add_argument("--num-threads",
        help="Number of threads for parsing articles")
    arg_parser.add_argument("--update-interval", help="Update interval")
    arg_parser.add_argument("--server", help="Server to use")
    arg_parser.add_argument("--db", choices=['sqlite', 'postgresql'],
        help="Database to use: sqlite or postgresql")
    arg_parser.add_argument("--no-lock", action="store_true", default=False)
    
    args = arg_parser.parse_args(arguments)
    
    lock_enabled = not args.no_lock
    
    if args.config:
        get_conf.set_config_from_fname(args.config)
    
    if args.num_threads:
        try:
            get_conf.config.num_threads = int(args.num_threads)
        except ValueError:
            logerr("'{0}' is not an integer".format(args.num_threads))
            sys.exit(1)

    if args.update_interval:
        try:
            get_conf.config.update_interval = int(args.update_interval)
        except ValueError:
            logerr("'{0}' is not an integer".format(args.update_interval))
            sys.exit(1)
    
    if args.server:
        get_conf.config.server = args.server
    
    if args.db:
        get_conf.config.db = args.db
    
    db.initialize_main_database()
    auto_alter.alter_main_database(False)
    if get_conf.config.save_articles:
        db.initialize_archive_db()
        auto_alter.alter_archive_database(False)
    
    if args.action:
        if args.action[0] == 'lock':
            set_var('parsing', '1')
        elif args.action[0] == 'unlock':
            set_var('parsing', '0')
        elif args.action[0] == 'locked?':
            log({'0': 'False', '1': 'True'}.get(get_var('parsing', '0'), 'False'))
        elif args.action[0] == 'train':
            log('Training classifier...')
            saveClassifier(trainClassifier())
        elif args.action[0] == 'rerank':            
            path = os.path.join(get_conf.logdir, "articles_dumped")
            articles = save.load_from_somewhere()
            
            if isinstance(articles, OrderedDict):
                articles = articles.values()
            
            log('Ranking articles...')
            
            articles = sorted(recommend.rank_articles(articles), key=itemgetter(1), reverse=True)
            articles = OrderedDict([(i[0]['link'], i[0]) for i in articles])
            
            save.dump_somewhere(articles, path)
            server.remove_cache()
            
        elif args.action[0] == "run":
            if len(args.action) == 1:
                addr = get_conf.config.host + ":" + get_conf.config.port
            else:
                addr = args.action[1]
            if not ":" in addr:
                addr += ":80"
            elif addr.endswith(":"):
                addr += "80"
        
            host, port = addr.split(":")
            is_host_correct = is_hostname(host)
            
            try:
                is_port_correct = int(port) <= 65535 and int(port) > 0
            except ValueError:
                is_port_correct = False
                
            if not is_host_correct:
                logerr("Invalid hostname")
                sys.exit(1)
            elif not is_port_correct:
                logerr("Invalid port")
                sys.exit(1)
            else:
                server.liked_links = {i['link'] for i in recommend.get_interesting_articles()}
                server.disliked_links = {i['link'] for i in recommend.get_blacklist()}
                run_server(host, port)
        elif args.action[0] == "update":
            atexit.register(lambda: set_var('parsing', '0') if parsing else None)
            lmbd = lambda _,__: sys.exit(0)
            signal.signal(signal.SIGTERM, lmbd)
            signal.signal(signal.SIGABRT, lmbd)
            dump_articles()
        elif args.action[0] == "start":
            server.liked_links = {i['link'] for i in recommend.get_interesting_articles()}
            server.disliked_links = {i['link'] for i in recommend.get_blacklist()}
            atexit.register(lambda: set_var('parsing', '0') if parsing else None)
            lmbd = lambda _,__: sys.exit(0)
            signal.signal(signal.SIGABRT, lmbd)
            running_as_daemon = True
            parser_daemon = ParserDaemon()
            try:
                parser_daemon.start()
            except DaemonError as e:
                logerr('Failed to start server: {0}'.format(e))
                sys.exit(1)
        elif args.action[0] == "stop":
            running_as_daemon = True
            parser_daemon = ParserDaemon()
            try:
                parser_daemon.stop()
            except DaemonError as e:
                logerr('Failed to stop server: {0}'.format(e))
                sys.exit(1)
        elif args.action[0] == "clean" and len(args.action) > 1 and args.action[1] == "cache":
            log("Cleaning cache...")
            server.remove_cache()
            log("Done!")

if __name__ == "__main__":
    main(sys.argv[1:])
else:
    app = default_app()
