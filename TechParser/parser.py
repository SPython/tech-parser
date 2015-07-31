#!/usr/bin/env python
# -*- coding: utf-8 -*-

import grab, re, feedparser
from grab.error import GrabError
from lxml.html import fromstring, tostring
from lxml.etree import Error as LXMLError
from lxml import etree

from TechParser.py2x import unicode_, urlparse

def absolutize_link(link, site_url):
    if link.startswith("//"):
        link = "http:" + link
    elif link.startswith("/"):
        link = "http://" + site_url + link
    
    return link

def escape_title(s):
    s = s.replace('&', '&amp;')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    s = s.replace('"', '&quot;')
    s = s.replace(u'»', '&raquo;')
    s = s.replace(u'«', '&laquo;')
    
    return s

def createGrab():
    g = grab.Grab()
    g.config['connect_timeout'] = 15
    g.config['timeout'] = 30
    
    return g

def parse_article_image(article, site_url=''):
    try:
        img = article.cssselect('img:first-child')[0]
        img.set('class', '')
        img.set('id', '')
        img.set('align', '')
        img.set('src', absolutize_link(img.get('src', ''), site_url))
        return tostring(img).strip()
    except IndexError:
        return b''
    except AttributeError:
        try:
            g = grab.Grab(article.encode('utf-8'))
            img = g.doc.tree.cssselect('img:first-child')[0]
        except GrabError:
            return b''
        except IndexError:
            return b''
        img.set('class', '')
        img.set('id', '')
        img.set('align', '')
        img.set('src', absolutize_link(img.get('src', ''), site_url))
        return tostring(img).strip()

def get_articles(grab_object, title_path, link_path, source, site_url="",
        summary_path=''):
    posts = []
        
    post_links = grab_object.doc.tree.cssselect(link_path)
    post_titles = grab_object.doc.tree.cssselect(title_path)
    if summary_path:
        summary = grab_object.doc.tree.cssselect(summary_path)
        for i in summary:
            for j in i.cssselect('script') + i.cssselect('style'):
                j.drop_tree()
    else:
        summary = []
    
    while len(summary) < len(post_links):
        summary.append(u'')
    
    zip_object = zip(post_links, post_titles, summary)
    
    for (title, link, summary_text) in zip_object:
        title = unicode_(title.text_content()).strip()
        link = grab_object.make_url_absolute(link.get("href"))
        
        posts.append(
            {"title": escape_title(title),
            "link": unicode_(link),
            "source": source,
            "summary": summary_text})
    
    return posts

def parse_rss(url, source, icon='', color='#000'):
    result = get_articles_from_rss(url, source, put_grab=True)
    entries = result[1]
    
    g = result[0]
    
    if not icon:
        icon = g.config['icon_path']
    
    return [{'fromrss': 1,
            'icon': icon,
            'color': color,
            'title': i['title'],
            'link': i['link'],
            'source': source,
            'summary': i['summary']} for i in entries]

def parse_icon(grab_object, default=None):
    elem_list = grab_object.doc.tree.cssselect('link[rel~="icon"], link[rel~="ICON"]')
    if elem_list:
        new_icon = grab_object.make_url_absolute(elem_list[0].attrib.get('href'))
        if new_icon:
            return new_icon
    
    parsed_url = urlparse(grab_object.config['url'])
            
    if parsed_url.path in {'/', ''}:
        if default is None:
            default = grab_object.make_url_absolute('/favicon.ico')
        elem_list = grab_object.doc.tree.cssselect('link[rel~="icon"], link[rel~="ICON"]')
        if elem_list:
            new_icon = grab_object.make_url_absolute(elem_list[0].attrib.get('href'))
            if new_icon:
                return new_icon
            else:
                return default

        return default
    else:
        domain = '{0}://{1}'.format(parsed_url.scheme, parsed_url.netloc)
        grab_object.go(domain)
        if default is None:
            default = grab_object.make_url_absolute('/favicon.ico')
        elem_list = grab_object.doc.tree.cssselect('link[rel~="icon"], link[rel~="ICON"]')
        if elem_list:
            new_icon = grab_object.make_url_absolute(elem_list[0].attrib.get('href'))
            if new_icon:
                return new_icon
            else:
                return default
        return default

def findFeedLink(grab_object):
    elements = grab_object.doc.tree.cssselect('a[href]')
    for element in elements:
        words = set(element.text_content().strip().lower().split())
        if words.intersection({'atom', 'rss', 'feed', 'subscribe'}):
            return grab_object.make_url_absolute(element.attrib.get('href', 'about:blank'))
    return 'about:blank'

def makeLinksAbsolute(g):
    g.doc.tree.rewrite_links(lambda x: g.make_url_absolute(x))
    for i in g.doc.tree.cssselect('img'):
        i.attrib['src'] = i.attrib.get('src', 'about:blank')

def makeImageLinksAbsolute(entry, g):
    try:
        summary_element = fromstring(entry['summary'])
    except KeyError:
        return
    for i in summary_element.cssselect('img'):
        i.attrib['src'] = g.make_url_absolute(i.attrib.get('src', 'about:blank'))
    entry['summary'] = tostring(summary_element).decode()

def extractEntries(grab_object, source, parse_image=True):
    entries = []
    
    parsed_entries = feedparser.parse(grab_object.doc.body).entries
    
    for entry in parsed_entries:
        makeImageLinksAbsolute(entry, grab_object)
        try:
            cleaned = clean_text(entry['summary'], parse_image)
            text, image = cleaned
            if parse_image and not len(image):
                for link in entry['links']:
                    if link.get('type', '').startswith('image/'):
                        image = '<img src="{0}" />'.format(grab_object.make_url_absolute(link['href']))
                        text = image + text
                        break
        except KeyError:
            text = ''
        
        entry = {'title': escape_title(entry['title']),
                 'link': entry['link'],
                 'source': source,
                 'summary': text}
        
        entries.append(entry)
    
    return entries

def get_articles_from_rss(url, source, parse_image=True, put_grab=False):
    g = createGrab()
    g.go(url)
    makeLinksAbsolute(g)
    
    content_type = g.doc.headers.get_content_type()
    
    if 'application/rss' not in content_type and 'application/xml' not in content_type and 'application/atom' not in content_type and not 'text/xml' in content_type:
        elem_list = g.doc.tree.cssselect('link[type="application/xml"], link[type="application/rss"], link[type="application/rss+xml"], link[type="application/atom+xml"], link[type="application/atom"]')
        
        if elem_list:
            new_url = g.make_url_absolute(elem_list[0].attrib.get('href'))
            if new_url:
                url = new_url
            else:
                entries = extractEntries(g, source, parse_image)
                
                g.config['icon_path'] = parse_icon(g)
                
                return (g, entries) if put_grab else entries
        else:
            entries = extractEntries(g, source, parse_image)

            link = findFeedLink(g)
            
            g.config['icon_path'] = parse_icon(g, default='')
            
            if not entries and link != 'about:blank':
                g.go(link)
                makeLinksAbsolute(g)
                
                entries = extractEntries(g, source, parse_image)
                
                if not g.config['icon_path']:
                    g.config['icon_path'] = parse_icon(g)
                
            return (g, entries) if put_grab else entries
    
    g.config['icon_path'] = parse_icon(g)
    
    # Reset grab object. Weird things happen (in this case) if you don't do that.
    # And g.reset() doesn't fix that
    g2 = createGrab()
    g2.config['icon_path'] = g.config['icon_path']
    g = g2
    
    # Remove useless object
    del g2
    
    g.go(url)
    makeLinksAbsolute(g)
    
    parsed_entries = feedparser.parse(g.doc.body).entries
    
    entries = extractEntries(g, source, parse_image)
    
    return (g, entries) if put_grab else entries

def remove_bad_tags(s):
    elmt = fromstring(s)
    for bad in elmt.cssselect('script, style, iframe'):
        bad.drop_tree()
    
    return tostring(elmt).decode()

def clean_text(s, parse_image=True):
    try:
        image = parse_article_image(s).decode() if parse_image else ''
        return (remove_bad_tags(s), image)
    except LXMLError:
        return ('', '')

def get_articles_using_xml(filename=None, xml=None, sites_element=None, site_element=None):
    if filename:
        root = etree.parse(filename)
    elif xml:
        root = etree.fromstring(xml)
    if root.tag == 'Sites':
        sites_element = root
        result = {}
        root = sites_element
        site_elements = root.xpath('Site')
        for site_element in site_elements:
            url = site_element.attrib.get('url')
            source = site_element.attrib.get('source')
            css_path_elements = site_element.xpath('CSSPath')
            css_paths = {}
            for i in css_path_elements:
                path_name = i.attrib.get('name')
                base = i.attrib.get('base')
                if base:
                    base_css_path = site_element.xpath('CSSPath[@name="{0}"]'.format(base))[0].text
                    i.text = base_css_path + i.text if i.text else base_css_path
                css_paths[path_name] = i.text
            g = grab.Grab()
            setup_grab(g)
            g.go(url)
        
            result[source] = get_articles(g, css_paths['title'], css_paths['link'], source, css_paths['summary'])
        return result
    elif root.tag == 'Site':
        site_element = root
    
        url = site_element.attrib.get('url')
        source = site_element.attrib.get('source')
        css_path_elements = site_element.xpath('CSSPath')
        css_paths = {}
        for i in css_path_elements:
            path_name = i.attrib.get('name')
            base = i.attrib.get('base')
            if base:
                base_css_path = site_element.xpath('CSSPath[@name="{0}"]'.format(base))[0].text
                i.text = base_css_path + i.text if i.text else base_css_path
            css_paths[path_name] = i.text
        g = grab.Grab()
        setup_grab(g)
        g.go('url')

        return get_articles(g, css_paths['title'], css_paths['link'], source, css_paths['summary'])
