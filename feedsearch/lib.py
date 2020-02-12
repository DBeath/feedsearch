import functools
import logging
import time
from contextlib import contextmanager
from typing import Optional, Union, Tuple

import requests
from bs4 import BeautifulSoup
from requests import Response
from requests.exceptions import RequestException
from werkzeug.local import Local, release_local
from werkzeug.urls import url_parse, url_fix

from .__version__ import __version__

LOCAL_CONTEXT = Local()

logger = logging.getLogger(__name__)

bs4_parser = "html.parser"

default_timeout = 3.05


def get_session():
    """
    Returns the Requests Session for the current local context.
    Creates a Session with default values if none exists.

    :return: Requests Session
    """
    return getattr(LOCAL_CONTEXT, "session", create_requests_session())


def get_timeout():
    """
    Returns the Request timeout for the current local context.

    :return: Request timeout
    """
    return getattr(LOCAL_CONTEXT, "timeout", default_timeout)


def get_exceptions() -> bool:
    """
    Returns the exception handling settings for the current local context.

    :return: Catch exception boolean
    """
    return getattr(LOCAL_CONTEXT, "exceptions", False)


def set_exceptions(value: bool = False) -> None:
    """
    Set the exception hadnling settings for the current local context.

    :return: None
    """
    setattr(LOCAL_CONTEXT, "exceptions", value)


def _user_agent() -> str:
    """
    Return User-Agent string

    :return: str
    """
    return "FeedSerach/{0} (https://github.com/DBeath/feedsearch)".format(__version__)


@contextmanager
def create_requests_session(
    user_agent: str = "",
    max_redirects: int = 30,
    timeout: Union[float, Tuple[float, float]] = default_timeout,
    exceptions: bool = False,
    verify: Union[bool, str] = True,
):
    """
    Creates a Requests Session and sets User-Agent header and Max Redirects

    :param user_agent: User-Agent string
    :param max_redirects: Max number of redirects before failure
    :param timeout: Request Timeout
    :param exceptions: If False, will gracefully handle Requests exceptions and attempt to keep searching.
                       If True, will leave Requests exceptions uncaught to be handled externally.
    :param verify: Verify SSL Certificates.
    :return: Requests session
    """
    # Create a request session
    session = requests.session()

    # Set User-Agent header
    user_agent = user_agent if user_agent else _user_agent()
    session.headers.update({"User-Agent": user_agent})

    session.max_redirects = max_redirects
    session.verify = verify

    # Add request session to local context
    setattr(LOCAL_CONTEXT, "session", session)
    setattr(LOCAL_CONTEXT, "timeout", timeout)
    setattr(LOCAL_CONTEXT, "exceptions", exceptions)

    yield session

    # Close request session
    session.close()

    # Clean up local context
    release_local(LOCAL_CONTEXT)


def requests_session(
    user_agent: str = "",
    max_redirects: int = 30,
    timeout: Union[float, Tuple[float, float]] = default_timeout,
    exceptions: bool = False,
    verify: Union[bool, str] = True,
):
    """
    Wraps a requests session around a function.

    :param user_agent: User Agent for requests
    :param max_redirects: Maximum number of redirects
    :param timeout: Request Timeout
    :param exceptions: If True, rethrow exceptions.
    :param verify: Verify SSL Certificates.
    :return: decorator function
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with create_requests_session(
                user_agent, max_redirects, timeout, exceptions, verify
            ):
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


def get_url(
    url: str,
    timeout: Union[float, Tuple[float, float]] = default_timeout,
    exceptions: bool = False,
    **kwargs
) -> Optional[Response]:
    """
    Performs a GET request on a URL

    :param url: URL string
    :param timeout: Request Timeout
    :param exceptions: If False, will gracefully handle Requests exceptions and attempt to keep searching.
                       If True, will reraise Requests exceptions to be handled externally.
    :return: Requests Response object
    """
    timeout = timeout if timeout else get_timeout()

    logger.info("Fetching URL: %s", url)
    start_time = time.perf_counter()
    try:
        session = get_session()
        response = session.get(url, timeout=timeout, **kwargs)
        response.raise_for_status()
    except RequestException as ex:
        logger.warning("RequestException while getting URL: %s, %s", url, str(ex))
        if exceptions:
            raise
        return None
    finally:
        dur = int((time.perf_counter() - start_time) * 1000)
        logger.debug("Performed fetch of URL: %s in %sms", url, dur)
    return response


def create_soup(text: str) -> BeautifulSoup:
    """
    Parses a string into a BeautifulSoup object

    :param text: Html string
    :return: BeautifulSoup object
    """
    return BeautifulSoup(text, bs4_parser)


def coerce_url(url: str, https: bool = True) -> str:
    """
    Coerce URL to valid format

    :param url: URL
    :param https: Force https if no scheme in url
    :return: str
    """
    url.strip()
    if url.startswith("feed://"):
        return url_fix("http://{0}".format(url[7:]))
    for proto in ["http://", "https://"]:
        if url.startswith(proto):
            return url_fix(url)
    if https:
        return url_fix("https://{0}".format(url))
    else:
        return url_fix("http://{0}".format(url))


def get_site_root(url: str) -> str:
    """
    Find the root domain of a url
    """
    url = coerce_url(url)
    parsed = url_parse(url, scheme="http")
    return parsed.netloc


def timeit(func):
    """
    A decorator used to log the function execution time
    """

    @functools.wraps(func)
    def wrap(*args, **kwargs):
        start = time.perf_counter()

        result = func(*args, **kwargs)

        dur = int((time.perf_counter() - start) * 1000)

        logger.debug("Function name=%s duration=%sms", func.__name__, dur)

        return result

    return wrap


def parse_header_links(value):
    """
    Return a list of Dicts of parsed link headers proxies.
    i.e. Link: <http:/.../front.jpeg>; rel=front; type="image/jpeg",
    <http://.../back.jpeg>; rel=back;type="image/jpeg"

    :param value: HTTP Link header to parse
    :return: List of Dicts
    """

    links = []

    replace_chars = " '\""

    for val in value.split(","):
        try:
            url, params = val.split(";", 1)
        except ValueError:
            url, params = val, ""

        link = {"url": url.strip("<> '\"")}

        for param in params.split(";"):
            try:
                key, value = param.split("=")
            except ValueError:
                break

            link[key.strip(replace_chars)] = value.strip(replace_chars)

        links.append(link)

    return links
