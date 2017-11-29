import functools
import logging
from contextlib import contextmanager

import requests
from bs4 import BeautifulSoup
from werkzeug.local import Local, release_local
from werkzeug.urls import url_parse, url_fix

from .__version__ import __version__

LOCAL_CONTEXT = Local()

logger = logging.getLogger(__name__)

bs4_parser = 'html.parser'

default_timeout = (10.05, 30)


def get_session():
    """
    Returns the Requests Session for the current local context.
    Creates a Session with default values if none exists.

    :return: Requests Session
    """
    return getattr(LOCAL_CONTEXT, 'session', create_requests_session())

def get_timeout():
    """
    Returns the Request timeout for the current local context.

    :return: Request timeout
    """
    return getattr(LOCAL_CONTEXT, 'timeout', default_timeout)


def _user_agent():
    """
    Return User-Agent string

    :return: str
    """
    return 'FeedSearch/{0} (https://github.com/DBeath/feedsearch)'.format(__version__)


@contextmanager
def create_requests_session(user_agent=None, max_redirects=30, timeout=default_timeout):
    """
    Creates a Requests Session and sets User-Agent header and Max Redirects

    :param user_agent: User-Agent string
    :param max_redirects: Max number of redirects before failure
    :return: Requests session
    """
    # Create a request session
    session = requests.session()

    # Set User-Agent header
    user_agent = user_agent if user_agent else _user_agent()
    session.headers.update({ "User-Agent": user_agent })

    session.max_redirects = max_redirects

    # Add request session to local context
    setattr(LOCAL_CONTEXT, 'session', session)
    setattr(LOCAL_CONTEXT, 'timeout', timeout)

    yield session

    # Close request session
    session.close()

    # Clean up local context
    release_local(LOCAL_CONTEXT)


def requests_session(user_agent=None, max_redirects=30):
    """
    Wraps a requests session around a function.

    :param user_agent: User Agent for requests
    :param max_redirects: Maximum number of redirects
    :return: decorator function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with create_requests_session(user_agent, max_redirects):
                # Call wrapped function
                return func(*args, **kwargs)

        return wrapper

    return decorator


def set_bs4_parser(parser: str) -> None:
    """
    Sets the parser used by BeautifulSoup

    :param parser: BeautifulSoup parser
    :return: None
    """
    if parser:
        global bs4_parser
        bs4_parser = parser


def get_url(url, timeout=None):
    """
    Performs a GET request on a URL

    :param url: URL string
    :param timeout: Optional Request Timeout
    :return: Requests Response object
    """
    timeout = timeout if timeout else get_timeout()
    try:
        response = get_session().get(url, timeout=timeout)
    except Exception as e:
        logger.warning('Error while getting URL: %s, %s', url, e)
        return None
    return response


def create_soup(text: str) -> BeautifulSoup:
    """
    Parses a string into a BeautifulSoup object

    :param text: Html string
    :return: BeautifulSoup object
    """
    return BeautifulSoup(text, bs4_parser)


def coerce_url(url: str) -> str:
    """
    Coerce URL to valid format

    :param url: URL
    :return: str
    """
    url.strip()
    if url.startswith("feed://"):
        return url_fix("http://{0}".format(url[7:]))
    for proto in ["http://", "https://"]:
        if url.startswith(proto):
            return url_fix(url)
    return url_fix("http://{0}".format(url))


def get_site_root(url: str) -> str:
    """
    Find the root domain of a url
    """
    url = coerce_url(url)
    parsed = url_parse(url, scheme='http')
    return parsed.netloc


def is_feed_data(text: str) -> bool:
    data = text.lower()
    if data.count('<html'):
        return False
    return bool(data.count('<rss') +
                data.count('<rdf') +
                data.count('<feed'))


def is_feed(url: str) -> str:
    response = get_url(url)

    if not response or not response.text or not is_feed_data(response.text):
        return ''

    return response.text


def is_feed_url(url: str) -> bool:
    return any(map(url.lower().endswith, [".rss",
                                          ".rdf",
                                          ".xml",
                                          ".atom"]))


def is_feedlike_url(url: str) -> bool:
    return any(map(url.lower().count, ["rss",
                                       "rdf",
                                       "xml",
                                       "atom",
                                       "feed"]))