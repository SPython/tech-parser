#!/usr/bin/env python
# -*- coding: utf-8 -*-

from TechParser.db import *

Q_DELETE_FROM_BLACKLIST = Blacklist.delete(condition='link={PARAM}')
Q_DELETE_FROM_HISTORY = History.delete(condition='link={PARAM}')
Q_ADD_TO_BLACKLIST = Blacklist.insert(values=['{PARAM}']*7,
    order='(title, link, summary, fromrss, icon, color, source)')
Q_ADD_TO_HISTORY = History.insert(values=['{PARAM}']*7,
    order='(title, link, summary, fromrss, icon, color, source)')
Q_SAVE_ARTICLES = Articles.insert(order='(title, link, source)', values=['{PARAM}']*3)
Q_ADD_SESSIONID = Sessions.insert(values=['{PARAM}'], order='(sid)')
Q_DELETE_SESSIONID = Sessions.delete('sid={PARAM}')
Q_CHECK_SESSIONID = Sessions.select('id', condition='sid={PARAM}')
Q_REMOVE_OLD_SESSIONIDS = MultiDBQuery(delete('sessions',
        condition="expires <= date('now')", db='sqlite'),
    delete('sessions',
        condition='expires <= now()', db='postgresql'))
Q_REMOVE_SESSIONID = Sessions.delete('sid={PARAM}')
Q_GET_VAR = Variables.select('value', condition='name={PARAM}')
Q_SET_VAR = Variables.update({'value': '{PARAM}'}, condition='name={PARAM}')
Q_ADD_VAR = Variables.insert(['{PARAM}']*2, order='(name, value)')
Q_ADD_ARTICLE = Articles.insert(['{PARAM}']*8,
    order='(title, link, summary, source, fromrss, icon, color, page_number)')
Q_SELECT_FROM_PAGE = Articles.select(condition='page_number={PARAM}')
Q_GET_ARTICLE_FROM_HISTORY = History.select(condition='link={PARAM}',
    what='title, link, summary, fromrss, icon, color, source')
Q_GET_ARTICLE_FROM_BLACKLIST = Blacklist.select(condition='link={PARAM}',
    what='title, link, summary, fromrss, icon, color, source')
Q_GET_BLACKLIST = Blacklist.select('title, link, summary, fromrss, icon, color, source',
    order_by='id DESC')
Q_GET_ARTICLE = Articles.select('title, link, summary, fromrss, icon, color, source',
    condition='link={PARAM}', limit=1)
Q_GET_HISTORY = History.select('title, link, summary, fromrss, icon, color, source',
    order_by='id DESC')
Q_CLEAR_ARTICLES = Articles.delete()
Q_SELECT_ALL_ARTICLES = Articles.select()
