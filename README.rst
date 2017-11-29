Feedsearch
==========

Feedsearch is a Python library for searching websites for RSS feeds.

It was originally based on
`Feedfinder2 <https://github.com/dfm/feedfinder2>`_ written by
`Dan Foreman-Mackey <http://dfm.io/>`_, which in turn is based on
`feedfinder <http://www.aaronsw.com/2002/feedfinder/>`_ - originally written by
`Mark Pilgrim <http://en.wikipedia.org/wiki/Mark_Pilgrim_(software_developer)>`_
and subsequently maintained by
`Aaron Swartz <http://en.wikipedia.org/wiki/Aaron_Swartz>`_ until his untimely death.

The main difference with Feedfinder2 is that Feedsearch allows for optional fetching of Feed and Site metadata.

Usage
-----

Feedsearch is called with the single function ``search``:

.. code-block:: python

    >>> from feedsearch import search
    >>> feeds = search('xkcd.com')
    >>> feeds
    [FeedInfo: <http://xkcd.com/atom.xml>, FeedInfo: <http://xkcd.com/rss.xml>]
    >>> feeds[0].url
    'http://xkcd.com/atom.xml'

To get Feed and Site metadata:

.. code-block:: python

    >>> feeds = search('propublica.org', info=True)
    >>> feeds
    [FeedInfo: http://feeds.propublica.org/propublica/main]
    >>> pprint(vars(feeds[0]))
    {'description': 'Latest Articles and Investigations from ProPublica, an '
                    'independent, non-profit newsroom that produces investigative '
                    'journalism in the public interest.',
    'hub': 'http://feedpress.superfeedr.com/',
    'is_push': True,
    'score': 4,
    'site_icon_url': 'https://assets.propublica.org/prod/v3/images/favicon.ico',
    'site_name': 'ProPublica',
    'site_url': 'https://www.propublica.org/',
    'title': 'Articles and Investigations - ProPublica',
    'url': 'http://feeds.propublica.org/propublica/main'}

Search will always return a list of FeedInfo objects, each of which will always have a *url* property.
Feeds are sorted by the *score* value from highest to lowest, with a higher score theoretically indicating
a more relevant feed, but whatever you do don't take this seriously.

If you only want the raw urls, then simply use a list comprehension on the result:

.. code-block:: python

    >>> feeds
    [FeedInfo: http://xkcd.com/atom.xml, FeedInfo: http://xkcd.com/rss.xml]
    >>> urls = [f.url for f in feeds]
    >>> urls
    ['http://xkcd.com/atom.xml', 'http://xkcd.com/rss.xml']

In addition to the URL, the ``search`` function takes the following optional keyword arguments:

- **info**: *bool*: Get Feed and Site Metadata. Defaults False.
- **check_all**: *bool*: Check all <link> and <a> tags on page. Defaults False.
- **user_agent**: *str*: User-Agent Header string. Defaults to Package name.
- **timeout**: *int* or *tuple*: Timeout for each request in the search (not a timeout for the ``search``
  method itself). Defaults to 30 seconds.
- **max_redirects**: *int*: Maximum number of redirects for each request. Defaults to 30.
- **parser**: *str*: BeautifulSoup parser for HTML parsing. Defaults to 'html.parser'.
