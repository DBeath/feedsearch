import functools
import logging

import requests
from bs4 import BeautifulSoup
from werkzeug.local import Local, release_local

REQUEST_SESSION = Local()

logger = logging.getLogger('feedsearch')

bs4_parser = 'html.parser'


def get_session():
    """
    Returns the Requests Session for the current local context.
    Creates a Session with default values if none exists.

    :return: Requests Session
    """
    return getattr(REQUEST_SESSION, 'session', _create_request_session())


def _user_agent():
    """
    Return User-Agent string

    :return: str
    """
    return "FeedSearch/0.1 (https://github.com/DBeath/feedsearch)"


def _create_request_session(user_agent=None, max_redirects=30):
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
    setattr(REQUEST_SESSION, 'session', session)

    return session

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
            _create_request_session(user_agent, max_redirects)

            # Call wrapped function
            result = func(*args, **kwargs)

            # Close request session
            get_session().close()

            # Clean up local context
            release_local(REQUEST_SESSION)

            return result

        return wrapper

    return decorator


def get_url(url, timeout=(10.05, 30)):
    """
    Performs a GET request on a URL

    :param url: URL string
    :param timeout: Optional Timeout Tuple
    :return: Requests Response object
    """
    try:
        response = get_session().get(url, timeout=timeout)
    except Exception as e:
        logger.warning(u'Error while getting URL: {0}, {1}'
                       .format(url, str(e)))
        return None
    return response


def create_soup(text: str) -> BeautifulSoup:
    """
    Parses a string into a BeautifulSoup object

    :param text: Html string
    :return: BeautifulSoup object
    """
    return BeautifulSoup(text, bs4_parser)

def set_bs4_parser(parser: str) -> None:
    """
    Sets the parser used by BeautifulSoup

    :param parser: BeautifulSoup parser
    :return: None
    """
    if parser:
        global bs4_parser
        bs4_parser = parser