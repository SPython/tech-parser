#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    chr = unichr
    range = xrange
    unicode__ = unicode
    def unicode_(s):
        try:
            return unicode(s, 'utf8')
        except TypeError:
            return s
    def find_shared(keys1, keys2):
        return {i for i in keys1 if i in keys2}
except NameError:
    chr = chr
    range = range
    unicode_, unicode__ = str, str
    def find_shared(keys1, keys2):
        return keys1 & keys2

def encodestr(string):
    return string.encode('utf8')

def decodestr(string):
    return string.decode('utf8')

try:
    dict_keys = dict.iterkeys
    dict_values = dict.itervalues
except AttributeError:
    dict_keys = dict.keys
    dict_values = dict.values

try:
    import htmlentitydefs
except ImportError:
    from html import entities as htmlentitydefs

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

try:
    from urllib.parse import urlencode, parse_qs
except ImportError:
    from urllib import urlencode
    from urlparse import parse_qs

try:
	from itertools import zip_longest
except ImportError:
	from itertools import izip_longest as zip_longest

try:
	import cPickle as pickle
except ImportError:
	import pickle
