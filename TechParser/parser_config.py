#!/usr/bin/env python
# -*- coding: utf-8 -*-

from TechParser.parsers import *

sites_to_parse = {
	"Habrahabr": { # habrahabr.ru
		"module": habrahabr,
		"kwargs": {"hubs": []},
		"enabled": True,
        "priority": 1.0
	},
	
	"VentureBeat": { # venturebeat.com
		"module": venturebeat,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Engadget": { # engadget.com
		"module": engadget,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Slashdot": { # slashdot.org
		"module": slashdot,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Gizmodo": { # gizmodo.com
		"module": gizmodo,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"TechCrunch": { # techcrunch.com
		"module": techcrunch,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Read/Write Web": { # readwrite.com
		"module": readwrite,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Tech Republic": { # techrepublic.com
		"module": techrepublic,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Smashing Magazine": { # www.smashingmagazine.com
		"module": smashingmagazine,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Android Central": { # www.androidcentral.com
		"module": androidcentral,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"The Verge": { # www.theverge.com
		"module": verge,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Top Design Magazine": { # www.topdesignmag.com
		"module": topdesignmag,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Flowa": { # flowa.fi
		"module": flowa,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"IT Toolbox": { # it.toolbox.com
		"module": ittoolbox,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"DZone": { # www.dzone.com
		"module": dzone,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Code Project": { # www.codeproject.com
		"module": codeproject,
		"kwargs": {'categories': ['all']}, # 'web', 'android', 'c#', 'c++' and 'ios'
		"enabled": True,
        "priority": 1.0
	},
	
	"Hacker News": { # news.ycombinator.com
		"module": hackernews,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Mashable": { # mashable.com
		"module": mashable,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Make Tech Easier": { # www.maketecheasier.com
		"module": maketecheasier,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Digg": { # digg.com
		"module": digg,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Wired": { # www.wired.com
		"module": wired,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Medium": { # medium.com
		"module": medium,
		"kwargs": {"collections": []},
		"enabled": True,
        "priority": 1.0
	},
	
	"Planet Clojure": { # planet.clojure.in
		"module": planetclojure,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Reddit": { # www.reddit.com
		"module": reddit,
		"kwargs": {"reddits": ["tech"]},
		"enabled": True,
        "priority": 1.0
	},
	
	"Trashbox": { # trashbox.ru
		"module": trashbox,
		# all, articles, news, main_page, games, programs, themes, questions
		"kwargs": {'categories': ['all']},
		"enabled": True,
        "priority": 1.0
	},
	
	"Droider": { # droider.ru
		"module": droider,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Redroid": { # redroid.ru
		"module": redroid,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"3DNews": { # www.3dnews.ru
		"module": threednews,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
		
	"IXBT": { # www.ixbt.ru
		"module": ixbt,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Mobile Review": { # mobile-review.com
		"module": mobilereview,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Helpix": { # helpix.ru
		"module": helpix,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"Re/code": { # recode.net
		"module": recode,
		"kwargs": {},
		"enabled": True,
        "priority": 1.0
	},
	
	"ZDNet": { # www.zdnet.com
		"module": zdnet,
		"kwargs": {'categories': ['all']}, # 'news', 'reviews' and 'downloads',
		"enabled": True,
        "priority": 1.0
	},
		
	"Geektimes": { # geektimes.ru
		"module": geektimes,
		"kwargs": {'hubs': []},
		"enabled": True,
        "priority": 1.0
	}
}

# RSS feeds
rss_feeds = {
	# 'Feed name': {
	#	'short-name': 'feed-name',
	#	'icon': 'http://<address-to-feed>.com/<address-to-feed-icon>',
	#	'color': '#123ABC' # CSS color for titles
	#	'enabled': True # or False to disable
	#}
}

# Words that you're interested in
interesting_words = []

# Words that you find boring
boring_words = []

update_interval = 1800 # Parse articles every 30 minutes

# Database for keeping history
# Must be sqlite or postgresql
db = 'sqlite'
# If You're using PostgreSQL make sure
# to set database url as environment variable <db_path_variable>
# like this: postgres://user:password@host:port/dbname
# or just set db_path equal to that database url.
# Example 1:
#  db_path_variable = 'DATABASE_URL'
#  db_path = os.environ.get(db_path_variable)
# Example 2:
#  db_path_variable = 'DATABASE_URL'
#  db_path = postgres://user:password@localhost:5432/mydb
db_path_variable = 'DATABASE_URL'
db_path = os.environ.get(db_path_variable, '')
host = '0.0.0.0' # Server host
port = '8080' # Server port

num_threads = 2 # Number of threads for parsing articles

# Server to use
# It's recommended to use tornado.
# You can install it by running pip install tornado
# See http://bottlepy.org/docs/dev/deployment.html#switching-the-server-backend
server = "auto"

# Save articles to the database at <archive_db_path>.
save_articles = False

# Environment variable that stores path to archive database
archive_db_path_variable = 'ARCHIVE_DATABASE_URL'

# Should look like 'sqlite:///PATH' or 'postgres://user:password@host:port/dbname'
# 'default' means 'sqlite:///<your-home-directory>/.tech-parser/archive.db'
archive_db_path = os.environ.get(archive_db_path_variable, 'default')

# Format to be used when dumping articles.
# Can be 'pickle', 'json' or 'db'.
# It's recommended to set data_format to 'db' (database) because it's a lot faster.
# Pickle is set by default for compatibility with previous versions of TechParser
data_format = 'pickle'

# Environment variable to keep your password
password_variable = 'TechParser_PASSWORD'

# Password
password = os.environ.get(password_variable, '')

# Show Pocket button under every article.
# Disabled by default because it slows down page loading.
# Besides, you can save links to Pocket with a plugin for your browser.
enable_pocket = False

# If json_config is set to True it will allow you to edit configuration in your browser
json_config = True

# Range of target word counts.
# The closer word count of article to one of these numbers, the higher score it has
perfect_word_count = (25, 50, 100, 150, 300, 600, 1200)

# Enable page caching
enable_caching = True

# Raise this number to make classifier more accurate
###########################################################
# Keep in mind that bigger number means bigger disk usage #
###########################################################
ngrams = 1

# Show random articles at the bottom
enable_random = True
