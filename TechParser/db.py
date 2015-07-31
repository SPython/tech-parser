#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import os

from TechParser.py2x import urlparse, zip_longest
from TechParser import get_conf

try:
    import psycopg2
except ImportError:
    pass

if get_conf.config is None:
    get_conf.set_config_auto()

get_conf.auto_fix_config()
PARAMETER_SIGNS = {'sqlite': '?', 'postgresql': '%s'}

class DBError(Exception):
    pass

class UnsupportedDBError(DBError):
    def __init__(self, db):
        msg = '\'{0}\' database is not supported (yet)'.format(db)
        super(UnsupportedDBError, self).__init__(msg)

class Database(object):
    """Used to automatically determine which query to execute"""
    main_database = None
    databases = {}
    _last_id = 0
    
    def __init__(self, connect_func, db='sqlite', name='', setup_query=None):
        self.connect_func = connect_func
        self.open()
        self.db = db
        self.query_count = 0
        self.setup_query = setup_query
        if db == 'sqlite':
            def func(q, p):
                for (i, j) in zip_longest(q.split(';'), p, fillvalue=tuple()):
                    if len(i):
                        self.cur.execute(i, j)
            self.execute = func
        elif db == 'postgresql':
            def func(q, p):
                self.cur.execute(q, [j for i in p for j in i])
                
            self.execute = func
        self.id = Database._last_id
        self.userData = None
        Database._last_id += 1
        if not name:
            self.name = 'Database-{0}'.format(self.id)
        else:
            self.name = name
        self.setup()
    
    def open(self):
        self.con = self.connect_func()
        self.cur = self.con.cursor()
    
    @staticmethod
    def register(database):
        Database.databases[database.name] = database
    
    def commit(self):
        self.query_count = 0
        self.con.commit()
    
    def setup(self):
        """Setup database"""
        
        if self.setup_query is not None:
            self.execute_query(self.setup_query)
    
    def close(self):
        self.commit()
        self.con.close()
        try:
            Database.databases.pop(self.name)
        except KeyError:
            pass
    
    def execute_query(self, query, parameters=None, commit=True):
        if parameters is None:
            parameters = query.parameters
        if isinstance(query, MultiDBQuery):
            if self.db == 'sqlite':
                self.execute(query.sqlite_query.query, parameters)
            else:
                self.execute(query.postgresql_query.query, parameters)
            self.query_count += 1
        else:
            self.execute(query.query, parameters)
            self.query_count += 1
        if commit:
            self.commit()
    
    def rollback(self):
        self.query_count = 0
        self.con.rollback()
    
    def fetchone(self):
        return self.cur.fetchone()
    
    def fetchmany(self, n):
        return self.cur.fecthmany(n)
    
    def fetchall(self):
        return self.cur.fetchall()
    
    def __del__(self):
        self.close()
    
    def __exit__(self):
        self.close()
    
    def __repr__(self):
        return '<Database name=\'{0}\', id={1}, db=\'{2}\'>'.format(self.name, self.id, self.db)

class MainDatabase(Database):
    def __init__(self):
        connect_func = which_db(get_conf.config.db)
        super(MainDatabase, self).__init__(connect_func,
            get_conf.config.db, 'Main-Database', setup_query=Q_SETUP)
        if get_conf.config.db == 'sqlite':
            self.userData = sqlite3.IntegrityError
        else:
            self.userData = psycopg2.IntegrityError
    
def initialize_main_database():
    """Setup main database"""
    
    Database.main_database = MainDatabase()
    Database.register(Database.main_database)

def initialize_archive_db():
    """Setup archive database"""
    
    if get_conf.config.archive_db_path == 'default':
        path = os.path.join(get_conf.logdir, 'archive.db')
        get_conf.config.archive_db_path = 'sqlite://{0}'.format(path)
    
    parsed = parse_dburl(get_conf.config.archive_db_path)
    db = parsed['scheme']
    if db == 'sqlite':
        connect_func = lambda: sqlite3.connect(parsed['dbname'])
    elif db == 'postgres':
        db = 'postgresql'
        parsed.pop('scheme')
        connect_func = lambda: psycopg2.connect(**parsed)
    else:
        raise UnsupportedDBError(db)
    archiveDB = Database(connect_func, db, name='Archive',
        setup_query=Q_SETUP_ARCHIVE)
    if db == 'postgresql':
        archiveDB.userData = psycopg2.IntegrityError
    else:
        archiveDB.userData = sqlite3.IntegrityError
    Database.register(archiveDB)

class Query(object):
    """Simple single database query. Should be used when query \
can be executed by all databases. Otherwise MultiDBQuery should be used"""
    
    def __init__(self, db='sqlite', query=''):
        self.db = db
        self.query = query
        self.parameters = tuple()
    
    def __add__(self, query):
        if self.query:
            return Query(self.db, self.query + '\n' + query.query)
        else:
            return Query(self.db, self.query + query.query)
    
class MultiDBQuery(object):
    """Query for multiple databases."""
    
    def __init__(self, *queries):
        for query in queries:
            if query.db == 'sqlite':
                self.sqlite_query = query
            elif query.db == 'postgresql':
                self.postgresql_query = query
        self.parameters = tuple()
    
    def __add__(self, query):
        return MultiDBQuery(self.sqlite_query + query.sqlite_query,
                            self.postgresql_query + query.postgresql_query)

def getMultiDBQuery(function, *args, **kwargs):
    return MultiDBQuery(function(*args, db='sqlite', **kwargs), function(*args, db='postgresql', **kwargs))

def select(what, from_where, condition='', order_by='', limit='', offset='', db='sqlite'):
    s = 'SELECT {0} FROM {1}{2}{3}{4}{5};'
    if condition:
        condition = ' WHERE {0}'.format(condition.format(PARAM=PARAMETER_SIGNS.get(db, '')))
    if order_by:
        order_by = ' ORDER BY {0}'.format(order_by)
    if limit:
        limit = ' LIMIT {0}'.format(limit)
    if offset:
        offset = ' OFFSET {0}'.format(offset)
    return Query(db, s.format(what, from_where, condition, order_by, limit, offset))

def create_index(name, table_name, columns='', check_existance=True, unique=False):
    s = 'CREATE {0}INDEX {{0}}{1} ON {{1}};'.format('UNIQUE ' if unique else '',
                                                     ' IF NOT EXISTS' if check_existance else '')
    if columns:
        columns = '({0})'.format(', '.join(columns))
    
    return s.format(name, table_name + columns)

def create_table(name, columns, check_existance=True, db='sqlite'):
    s = 'CREATE TABLE {0}{{0}}({{1}});'.format('IF NOT EXISTS ' if check_existance else '')
    s2 = ''
    for column in columns:
        s2 += '{0} {1}, '.format(column.name, column.type[db])
    s2 = s2[:-2]
    
    return Query(db, s.format(name, s2))

def insert(into, values, db='sqlite'):
    s = 'INSERT INTO {0} VALUES({1});'
    
    return Query(db, s.format(into, ', '.join(values).format(PARAM=PARAMETER_SIGNS.get(db, ''))))

def update(table, columns, condition='', otherwise='', db='sqlite'):
    s = 'UPDATE{0} {1} SET {2}{3};'
    PARAM = PARAMETER_SIGNS.get(db, '')
    if condition:
        condition = ' WHERE {0}'.format(condition.format(PARAM=PARAM))
    values = ''
    for k, v in columns.items():
        values += '{0}={1}, '.format(k, v.format(PARAM=PARAM))
    values = values[:-2]
    
    if otherwise:
        otherwise = ' OR {0}'.format(otherwise)
    
    return Query(db, s.format(otherwise, table, values, condition))

def delete(table, condition='', db='sqlite'):
    s = 'DELETE FROM {0}{1};'
    
    if condition:
        condition = ' WHERE {0}'.format(condition.format(PARAM=PARAMETER_SIGNS.get(db, '')))
    
    return Query(db, s.format(table, condition))

def repeat(function, list_args, list_kwargs):
    for args, kwargs in zip(list_args, list_kwargs):
        yield function(*args, **kwargs)

def alter_table(table, new_table_name='', new_column=None, db='sqlite'):
    s = 'ALTER TABLE {0} {{0}} {{1}};'.format(table)
    if new_table_name:
        return Query(db, s.format('RENAME TO', new_table_name))
    if new_column:
        return Query(db, s.format('ADD COLUMN', new_column.name + ' ' + new_column.type[db]))

def add_column(table, column, db='sqlite'):
    return alter_table(table, new_column=column, db=db)

def rename_table(table, new_table_name):
    return alter_table(table, new_table_name=new_table_name)

class Column(object):
    def __init__(self, name, column_type=None, unique=False, default=None):
        self.name = name
        self.type = ColumnType(column_type, unique, default)

class MultiDBExpression(object):
    def __init__(self, **expressions):
        self.expressions = {k: v.format(PARAM=PARAMETER_SIGNS.get(k, '')) for k, v in expressions.items()}

class ColumnType(object):
    representations = {'sqlite': {'SERIAL': 'INTEGER AUTOINCREMENT'},
                       'postgresql': {'DATETIME': 'TIMESTAMP'}}
    last_type = None
    
    def __init__(self, type_name=None, unique=False, default=None):
        if type_name is None:
            type_name = ColumnType.last_type
        else:
            ColumnType.last_type = type_name
        type_name = type_name.upper()
        self.name = type_name
        self.unique = unique
        self.default = default
        self.strings = {}
    
    def __getitem__(self, name):
        if name == 'sqlite':
            s = self.representations['sqlite'].get(self.name, self.name)
            if self.unique:
                s += ' UNIQUE'
            if self.default:
                s += ' DEFAULT {0}'.format(self.default.expressions['sqlite'])
            return s
        elif name == 'postgresql':
            s = self.representations['postgresql'].get(self.name, self.name)
            if self.unique:
                s += ' UNIQUE'
            if self.default:
                s += ' DEFAULT {0}'.format(self.default.expressions['postgresql'])
            return s
    
        raise KeyError('No such key')

class Table(object):
    name = ''
    order = tuple()
    class columns(object):
        pass
    
    @classmethod
    def create_table(cls):
        return getMultiDBQuery(create_table, cls.name, list(cls.getColumns()))
    
    @classmethod
    def getColumns(cls):
        d = {}
        for x in set(sum([tuple(i.__dict__.values()) for i in cls.columns.__mro__ if i.__name__ != 'object'], tuple())):
            try:
                d[x.name] = x
            except AttributeError:
                pass
        for c in cls.order:
            yield d.pop(c)
    
    @classmethod
    def select(cls, what='*', condition='', order_by='', limit='', offset=''):
        return getMultiDBQuery(select, what, cls.name, condition=condition,
            order_by=order_by, limit=limit, offset=offset)
    
    @classmethod
    def delete(cls, condition=''):
        return getMultiDBQuery(delete, cls.name, condition)
    
    @classmethod
    def insert(cls, values, order=''):
        return getMultiDBQuery(insert, cls.name + order, values)
    
    @classmethod
    def update(cls, columns, condition='', otherwise=''):
        return getMultiDBQuery(update, cls.name, columns, condition, otherwise)
    
    @classmethod
    def create_index(cls, name, columns='', check_existance=True, unique=False):
        return create_index(name, cls.name, columns, check_existance, unique)

class Sessions(Table):
    name = 'sessions'
    order = ('id', 'sid', 'expires')
    class columns(object):
        id = Column('id', 'serial primary key')
        sid = Column('sid', 'text', unique=True)
        expires = Column('expires', 'datetime',
            default=MultiDBExpression(sqlite="(datetime('now', '+1 years'))",
                                      postgresql="now() + INTERVAL '1 year'"))

class History(Table):
    name = 'interesting_articles'
    order = ('id', 'title', 'link', 'summary', 'source', 'fromrss', 'icon', 'color')
    class columns(object):
        id = Column('id', 'serial primary key')
        title = Column('title', 'text')
        link = Column('link', unique=True)
        summary = Column('summary')
        source = Column('source')
        icon = Column('icon')
        color = Column('color')
        fromrss = Column('fromrss', 'integer')

class Blacklist(Table):
    name = 'blacklist'
    order = History.order
    class columns(History.columns):
        pass

class Variables(Table):
    name = 'variables'
    order = ('id', 'name', 'value')
    class columns(object):
        id = Column('id', 'serial primary key')
        name = Column('name', 'text', unique=True)
        value = Column('value')

class Articles(Table):
    name = 'articles'
    order = History.order + ('page_number',)
    class columns(History.columns):
        page_number = Column('page_number', 'integer')

class Archive(Table):
    name = 'articles'
    order = ('id', 'title', 'link', 'source')
    class columns(object):
        id = Column('id', 'serial primary key')
        title = Column('title', 'text')
        link = Column('link', unique=True)
        source = Column('source')

def which_db(db):
    """Determine which database should be used and \
return corresponding function to connect it"""
    
    if db == 'postgresql':
        parsed = parse_dburl(get_conf.config.db_path)
        parsed.pop('scheme')
        connect = lambda: psycopg2.connect(**parsed)
    elif db == 'sqlite':
        arg = os.path.join(get_conf.logdir, 'interesting.db')
        connect = lambda: sqlite3.connect(arg)
    else:
        raise UnsupportedDBError(db)
    
    return connect

def parse_dburl(s):
    """Parse URL to database from string"""
    
    parsed = urlparse(s)
    
    res = {'scheme': parsed.scheme,
        'user': parsed.username,
        'password': parsed.password,
        'host': parsed.hostname,
        'port': parsed.port,
        'dbname': parsed.path}
    if parsed.scheme != 'sqlite':
        res['dbname'] = parsed.path[1:]
    return res

def connect_db(db='sqlite'):
    return which_db(db)()

# Those queries are special because they are used in Database.setup
Q_SETUP = sum(map(lambda x: x.create_table(),
                  [History, Blacklist, Sessions, Variables, Articles]),
              MultiDBQuery(Query('sqlite'), Query('postgresql')))
Q_SETUP_ARCHIVE = Archive.create_table()
