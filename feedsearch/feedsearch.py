import logging
import time
from typing import List, Tuple, Union
from urllib.parse import urljoin

from .feedfinder import FeedFinder
from .feedinfo import FeedInfo
from .lib import (
    coerce_url,
    create_requests_session,
    create_soup,
    default_timeout,
    get_site_root,
    set_bs4_parser,
    timeit,
)
from .url import URL

logger = logging.getLogger(__name__)


def search(
    url,
    check_all: bool = False,
    info: bool = False,
    timeout: Tuple[int, int] = default_timeout,
    user_agent: str = "",
    max_redirects: int = 30,
    parser: str = "html.parser",
    exceptions: bool = False,
    favicon_data_uri: bool = False,
    as_urls: bool = False,
) -> Union[List[FeedInfo], List[str]]:
    """
    Search for RSS or ATOM feeds at a given URL

    :param url: URL
    :param check_all: Check all <link> and <a> tags on page
    :param info: Get Feed and Site Metadata
    :param timeout: Request timeout
    :param user_agent: User-Agent Header string
    :param max_redirects: Maximum Request redirects
    :param parser: BeautifulSoup parser ('html.parser', 'lxml', etc.).
        Defaults to 'html.parser'
    :param exceptions: If False, will gracefully handle Requests exceptions and
        attempt to keep searching. If True, will leave Requests exceptions
        uncaught to be handled externally.
    :param favicon_data_uri: Fetch Favicon and convert to Data Uri
    :param as_urls: Return found Feeds as a list of URL strings instead
        of FeedInfo objects
    :return: List of found feeds as FeedInfo objects.
             FeedInfo objects will always have a .url value.
    """
    # Wrap find_feeds in a Requests session
    with create_requests_session(user_agent, max_redirects, timeout, exceptions):
        # Set BeautifulSoup parser
        set_bs4_parser(parser)
        # Find feeds
        feeds = _find_feeds(url, check_all, info, favicon_data_uri)
        if as_urls:
            return [f.url for f in feeds]
        else:
            return feeds


@timeit
def _find_feeds(
    url: str,
    check_all: bool = False,
    feed_info: bool = False,
    favicon_data_uri: bool = False,
) -> List[FeedInfo]:
    """
    Finds feeds

    :param url: URL
    :param check_all: Check all <link> and <a> tags on page
    :param feed_info: Get Feed and Site Metadata
    :param favicon_data_uri: Fetch Favicon and convert to Data Uri
    :return: list
    """

    finder = FeedFinder(feed_info=feed_info, favicon_data_uri=favicon_data_uri)

    # Format the URL properly.
    url: str = coerce_url(url)

    feeds: list = []

    start_time = time.perf_counter()

    # Download the requested URL
    logger.info("Finding feeds at URL: %s", url)

    # Get URL and check if feed
    found_url = URL(url)

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug("Searched url in %sms", search_time)

    # If URL is valid, then get site info if feed_info is True
    if found_url.is_valid:
        if feed_info:
            finder.get_site_info(found_url)
    # Return nothing if there is no data from the URL
    else:
        return []

    # If URL is already a feed, create and return FeedInfo
    if found_url.is_feed:
        found = finder.create_feed_info(found_url)
        feeds.append(found)
        return feeds

    # Parse text with BeautifulSoup
    finder.soup = create_soup(found_url.data)

    # Search for <link> tags
    logger.debug("Looking for <link> tags.")
    links = finder.search_links(found_url.url)
    found_links = finder.check_urls(links)
    feeds.extend(found_links)
    logger.info("Found %s feed <link> tags.", len(found_links))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug("Searched <link> tags in %sms", search_time)

    # Return if feeds are already found and check_all is False.
    if feeds and not check_all:
        return sort_urls(feeds, url)

    # Search for default CMS feeds.
    # We run this only if feeds are not already found in the <link> tags, as
    # any good CMS should advertise feeds in the site meta.
    if not finder.site_meta:
        finder.get_site_info(url)
    logger.debug("Looking for CMS feeds.")
    cms_urls = finder.site_meta.cms_feed_urls()
    found_cms = finder.check_urls(cms_urls)
    feeds.extend(found_cms)

    # Return if feeds are already found and check_all is False.
    if feeds and not check_all:
        return sort_urls(feeds, url)

    # Look for <a> tags.
    logger.debug("Looking for <a> tags.")
    local, remote = finder.search_a_tags()

    # Check the local URLs.
    local: list = [urljoin(url, l) for l in local]
    found_local = finder.check_urls(local)
    feeds.extend(found_local)
    logger.info("Found %s local <a> links to feeds.", len(found_local))

    # Check the remote URLs.
    remote: list = [urljoin(url, l) for l in remote]
    found_remote = finder.check_urls(remote)
    feeds.extend(found_remote)
    logger.info("Found %s remote <a> links to feeds.", len(found_remote))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug("Searched <a> links in %sms", search_time)

    # Only guess URLs if check_all is True.
    if not check_all:
        return sort_urls(feeds, url)

    # Guessing potential URLs.
    fns = [
        "atom.xml",
        "index.atom",
        "index.rdf",
        "rss.xml",
        "index.xml",
        "index.rss",
        "index.json",
    ]
    urls = list(urljoin(url, f) for f in fns)
    found_guessed = finder.check_urls(urls)
    feeds.extend(found_guessed)
    logger.info("Found %s guessed links to feeds.", len(found_guessed))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug("Searched guessed urls in %sms", search_time)

    return sort_urls(feeds, url)


def url_feed_score(url: str, original_url: str = "") -> int:
    """
    Return a Score based on estimated relevance of the feed Url
    to the original search Url

    :param url: Feed Url
    :param original_url: Searched Url
    :return: Score integer
    """
    score = 0

    if original_url:
        url_domain = get_site_root(url)
        original_domain = get_site_root(original_url)

        if original_domain not in url_domain:
            score -= 17

    if "comments" in url:
        score -= 15
    if "georss" in url:
        score -= 9
    if "alt" in url:
        score -= 7
    kw = ["atom", "rss", ".xml", "feed", "rdf"]
    for p, t in zip(range(len(kw) * 2, 0, -2), kw):
        if t in url:
            score += p
    if url.startswith("https"):
        score += 9
    return score


def sort_urls(feeds: List[FeedInfo], original_url: str = "") -> List[FeedInfo]:
    """
    Sort list of feeds based on Url score

    :param feeds: List of FeedInfo objects
    :param original_url: Searched Url
    :return: List of FeedInfo objects
    """
    for feed in feeds:
        feed.score = url_feed_score(feed.url, original_url)
    sorted_urls = sorted(list(set(feeds)), key=lambda x: x.score, reverse=True)
    logger.info("Returning sorted URLs: %s", sorted_urls)
    return sorted_urls
