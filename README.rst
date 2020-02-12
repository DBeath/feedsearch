Feedsearch
==========
.. image:: https://img.shields.io/pypi/v/feedsearch.svg
    :target: https://pypi.python.org/pypi/feedsearch

.. image:: https://img.shields.io/pypi/l/feedsearch.svg
    :target: https://pypi.python.org/pypi/feedsearch
    
.. image:: https://img.shields.io/pypi/pyversions/feedsearch.svg
    :target: https://pypi.python.org/pypi/feedsearch

.. image:: https://pepy.tech/badge/feedsearch
    :target: https://pepy.tech/project/feedsearch

Feedsearch is a Python library for searching websites for RSS, Atom, and JSON feeds.

It was originally based on
`Feedfinder2 <https://github.com/dfm/feedfinder2>`_ written by
`Dan Foreman-Mackey <http://dfm.io/>`_, which in turn is based on
`feedfinder <http://www.aaronsw.com/2002/feedfinder/>`_ - originally written by
`Mark Pilgrim <http://en.wikipedia.org/wiki/Mark_Pilgrim_(software_developer)>`_
and subsequently maintained by
`Aaron Swartz <http://en.wikipedia.org/wiki/Aaron_Swartz>`_ until his untimely death.

Feedsearch now differs a lot with Feedfinder2, in that Feedsearch supports JSON feeds, allows for 
optional fetching of Feed and Site metadata, and optionally searches the content of internal linked pages
and default CMS feed locations.

**Please Note:** Development of this library is no longer ongoing except in the case of fixing reported bugs.
Further development of Feedsearch functionality has now moved to
`Feedsearch Crawler <https://github.com/DBeath/feedsearch-crawler>`_.

Usage
-----

Feedsearch is called with the single function ``search``:

.. code-block:: python

    >>> from feedsearch import search
    >>> feeds = search('xkcd.com')
    >>> feeds
    [FeedInfo('https://xkcd.com/atom.xml'), FeedInfo('https://xkcd.com/rss.xml')]
    >>> feeds[0].url
    'http://xkcd.com/atom.xml'

To get Feed and Site metadata:

.. code-block:: python

    >>> feeds = search('propublica.org', info=True)
    >>> feeds
    [FeedInfo('http://feeds.propublica.org/propublica/main')]
    >>> pprint(vars(feeds[0]))
    {'bozo': 0,
     'content_type': 'text/xml; charset=UTF-8',
     'description': 'Latest Articles and Investigations from ProPublica, an '
                    'independent, non-profit newsroom that produces investigative '
                    'journalism in the public interest.',
     'favicon': 'https://assets.propublica.org/prod/v3/images/favicon.ico',
     'favicon_data_uri': '',
     'hubs': ['http://feedpress.superfeedr.com/'],
     'is_push': True,
     'score': 4,
     'self_url': 'http://feeds.propublica.org/propublica/main',
     'site_name': 'ProPublica',
     'site_url': 'https://www.propublica.org/',
     'title': 'Articles and Investigations - ProPublica',
     'url': 'http://feeds.propublica.org/propublica/main',
     'version': 'rss20'}

Search will always return a list of *FeedInfo* objects, each of which will always have a *url* property.
Feeds are sorted by the *score* value from highest to lowest, with a higher score theoretically indicating
a more relevant feed compared to the original URL provided.

If you only want the raw urls, then use a list comprehension on the result, or set the
*as_urls* parameter to *True*:

.. code-block:: python

    >>> feeds = search('http://jsonfeed.org')
    >>> feeds
    [FeedInfo('https://jsonfeed.org/xml/rss.xml'), FeedInfo('https://jsonfeed.org/feed.json')]
    >>> urls = [f.url for f in feeds]
    >>> urls
    ['https://jsonfeed.org/xml/rss.xml', 'https://jsonfeed.org/feed.json']

    >>> feeds = search('http://jsonfeed.org', as_urls=True)
    >>> feeds
    >>> ['https://jsonfeed.org/xml/rss.xml', 'https://jsonfeed.org/feed.json']

In addition to the URL, the ``search`` function takes the following optional keyword arguments:

- **info**: *bool*: Get Feed and Site Metadata. Defaults False.
- **check_all**: *bool*: Check all internally linked pages of <a> tags for feeds, and default CMS feeds.
  Only checks one level down. Defaults False. May be very slow.
- **user_agent**: *str*: User-Agent Header string. Defaults to Package name.
- **timeout**: *float* or *tuple(float, float)*: Timeout for each request in the search (not a timeout for the ``search``
  method itself). Defaults to 3 seconds. See
  `Requests timeout documentation <http://docs.python-requests.org/en/master/user/advanced/#timeouts>`_ for more info.
- **max_redirects**: *int*: Maximum number of redirects for each request. Defaults to 30.
- **parser**: *str*: BeautifulSoup parser for HTML parsing. Defaults to 'html.parser'.
- **exceptions**: *bool*: If False, will gracefully handle Requests exceptions and attempt to keep searching. 
  If True, will leave Requests exceptions uncaught to be handled by the caller. Defaults False.
- **verify**: *bool* or *str*: Verify SSL Certificates. See
  `Requests SSL documentation <https://requests.readthedocs.io/en/master/user/advanced/#ssl-cert-verification>`_ for more info.
- **favicon_data_uri**: *bool*: Convert Favicon to Data Uri. Defaults False.
- **as_urls**: *bool*: Return found Feeds as a list of URL strings instead of FeedInfo objects.
- **cms**: *bool*: Check default CMS feed location if no feeds already found and site is using a known CMS. Defaults True.
- **discovery_only**: *bool*: Only search for RSS discovery tags (e.g. <link rel="alternate" href=...>). Defaults False.
  Overridden by **check_all** if **check_all** is True.

FeedInfo Values
---------------

FeedInfo objects may have the following values if *info* is *True*:

- **bozo**: *int*: Set to 1 when feed data is not well formed or may not be a feed. Defaults 0.
- **content_type**: *str*: Content-Type value of the returned feed.
- **description**: *str*: Feed description.
- **favicon**: *str*: Url of site Favicon.
- **favicon_data_uri**: *str*: Data Uri of site Favicon.
- **hubs**: *List[str]*: List of `Websub <https://en.wikipedia.org/wiki/WebSub>`_ hubs of feed if available.
- **is_push**: *bool*: True if feed contains valid Websub data.
- **score**: *int*: Computed relevance of feed url value to provided URL. May be safely ignored.
- **self_url**: *str*: *ref="self"* value returned from feed links. In some cases may be different from feed url.
- **site_name**: *str*: Name of feed's website.
- **site_url**: *str*: URL of feed's website.
- **title**: *str*: Feed Title.
- **url**: *str*: URL location of feed.
- **version**: *str*: Feed version `XML values <https://pythonhosted.org/feedparser/version-detection.html>`_,
  or `JSON feed <https://jsonfeed.org/version/1>`_.


Search Order
------------

Feedsearch searches for feeds in the following order:

1. If the URL points directly to a feed, then return that feed.
2. If **discovery_only** is True, search only <link rel="alternate"> tags. Return unless **check_all** is True.
3. Search all <link> tags. Return if feeds are found and **check_all** is False.
4. If **cms** or **check_all** is True, search for default CMS feeds if the site is using a known CMS. Return if feeds are found and **check_all** is False.
5. Search all <a> tags. Return if **check_all** is False.
6. This point will only be reached if **check_all** is True.
7. Fetch the content of all internally pointing <a> tags whose URL paths indicate they may contain feeds. (e.g. /feed /rss /atom). All <link> tags and <a> tags of the content are searched, although not recusively. Return if feeds are found. This step may be very slow, so be sure whether you want **check_all** enabled.
8. If step 7 failed to find feeds, then as a last resort we make a few guesses for potential feed urls.
