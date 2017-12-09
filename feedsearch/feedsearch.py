import logging
import time
from typing import Tuple, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .feedinfo import FeedInfo
from .lib import (create_soup,
                  coerce_url,
                  get_site_root,
                  create_requests_session,
                  default_timeout,
                  set_bs4_parser,
                  timeit)
from .site_meta import SiteMeta
from .url import URL

logger = logging.getLogger(__name__)


class FeedFinder:
    def __init__(self,
                 feed_info: bool=False,
                 favicon_data_uri: bool=False) -> None:
        self.feed_info = feed_info
        self.favicon_data_uri = favicon_data_uri
        self.soup: BeautifulSoup=None
        self.site_meta: SiteMeta=None
        self.feeds: list=[]

    def check_urls(self, urls: List[str]) -> List[FeedInfo]:
        """
        Check if a list of Urls contain feeds

        :param urls: List of Url strings
        :return: list
        """
        feeds = []
        for url_str in urls:
            url = URL(url_str)
            if url.is_feed:
                feed = self.create_feed_info(url)
                feeds.append(feed)

        return feeds

    def create_feed_info(self, url: URL) -> FeedInfo:
        """
        Creates a FeedInfo object from a URL object

        :param url: URL object
        :return: FeedInfo
        """
        info = FeedInfo(url.url, content_type=url.content_type)

        if self.feed_info:
            info.get_info(data=url.data)

            if self.site_meta:
                info.add_site_info(self.site_meta.site_url,
                                   self.site_meta.site_name,
                                   self.site_meta.icon_url,
                                   self.site_meta.icon_data_uri)

        return info

    def search_links(self, url: str) -> List[FeedInfo]:
        """
        Search all links on a page for feeds

        :param url: Url of the soup
        :return: list
        """
        links: List[str]=[]
        for link in self.soup.find_all("link"):
            if link.get("type") in ["application/rss+xml",
                                    "text/xml",
                                    "application/atom+xml",
                                    "application/x.atom+xml",
                                    "application/x-atom+xml",
                                    'application/json']:
                links.append(urljoin(url, link.get("href", "")))

        return self.check_urls(links)

    def search_a_tags(self) -> Tuple[List[str], List[str]]:
        """
        Search all 'a' tags on a page for feeds

        :return: Tuple[list, list]
        """
        local, remote = [], []
        for a in self.soup.find_all("a"):
            href = a.get("href", None)
            if href is None:
                continue
            if "://" not in href and URL.is_feed_url(href):
                local.append(href)
            if URL.is_feedlike_url(href):
                remote.append(href)

        return local, remote

    def get_site_info(self, url: str) -> None:
        """
        Search for site metadata

        :param url: Site Url
        :return: None
        """
        if self.feed_info:
            self.site_meta = SiteMeta(url)
            self.site_meta.parse_site_info(self.favicon_data_uri)


def search(url,
           check_all: bool=False,
           info: bool=False,
           timeout=default_timeout,
           user_agent: str='',
           max_redirects: int=30,
           parser: str='html.parser',
           exceptions: bool=False,
           favicon_data_uri: bool=False):
    """
    Search for RSS or ATOM feeds at a given URL

    :param url: URL
    :param check_all: Check all <link> and <a> tags on page
    :param info: Get Feed and Site Metadata
    :param timeout: Request timeout
    :param user_agent: User-Agent Header string
    :param max_redirects: Maximum Request redirects
    :param parser: BeautifulSoup parser ('html.parser', 'lxml', etc.). Defaults to 'html.parser'
    :param exceptions: If False, will gracefully handle Requests exceptions and attempt to keep searching.
                       If True, will leave Requests exceptions uncaught to be handled externally.
    :param favicon_data_uri: Fetch Favicon and convert to Data Uri
    :return: List of found feeds as FeedInfo objects.
             FeedInfo objects will always have a .url value.
    """

    # Wrap find_feeds in a Requests session
    with create_requests_session(user_agent, max_redirects, timeout, exceptions):
        # Set BeautifulSoup parser
        set_bs4_parser(parser)
        # Find feeds
        return _find_feeds(url, check_all, info, favicon_data_uri)


@timeit
def _find_feeds(url: str,
                check_all: bool=False,
                feed_info: bool=False,
                favicon_data_uri: bool=False) -> List[FeedInfo]:
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
    url = coerce_url(url)

    feeds = []

    start_time = time.perf_counter()

    # Download the requested URL
    logger.info('Finding feeds at URL: %s', url)

    # Get URL and check if feed
    found_url = URL(url)

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug('Searched url in %sms', search_time)

    # If Url is already a feed, create and return FeedInfo
    if found_url.is_feed:
        finder.get_site_info(url)
        found = finder.create_feed_info(found_url)
        feeds.append(found)
        return feeds

    if not found_url.data:
        return []

    # Get site metadata
    finder.get_site_info(url)

    # Parse text with BeautifulSoup
    finder.soup = create_soup(found_url.data)

    # Search for <link> tags
    logger.debug('Looking for <link> tags.')
    found_links = finder.search_links(found_url.url)
    feeds.extend(found_links)
    logger.info('Found %s feed <link> tags.', len(found_links))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug('Searched <link> tags in %sms', search_time)

    if len(feeds) and not check_all:
        return sort_urls(feeds, url)

    # Look for <a> tags.
    logger.debug('Looking for <a> tags.')
    local, remote = finder.search_a_tags()

    # Check the local URLs.
    local = [urljoin(url, l) for l in local]
    found_local = finder.check_urls(local)
    feeds.extend(found_local)
    logger.info('Found %s local <a> links to feeds.', len(found_local))

    # Check the remote URLs.
    remote = [urljoin(url, l) for l in remote]
    found_remote = finder.check_urls(remote)
    feeds.extend(found_remote)
    logger.info('Found %s remote <a> links to feeds.', len(found_remote))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug('Searched <a> links in %sms', search_time)

    # Only guess URLs if check_all is True.
    if not check_all:
        return sort_urls(feeds, url)

    # Guessing potential URLs.
    fns = ["atom.xml", "index.atom", "index.rdf", "rss.xml", "index.xml",
           "index.rss", "index.json"]
    urls = list(urljoin(url, f) for f in fns)
    found_guessed = finder.check_urls(urls)
    feeds.extend(found_guessed)
    logger.info('Found %s guessed links to feeds.', len(found_guessed))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug('Searched guessed urls in %sms', search_time)

    return sort_urls(feeds, url)


def url_feed_score(url: str, original_url: str='') -> int:
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
    if url.startswith('https'):
        score += 9
    return score


def sort_urls(feeds: List[FeedInfo], original_url: str='') -> List[FeedInfo]:
    """
    Sort list of feeds based on Url score

    :param feeds: List of FeedInfo objects
    :param original_url: Searched Url
    :return: List of FeedInfo objects
    """
    for feed in feeds:
        feed.score = url_feed_score(feed.url, original_url)
    sorted_urls = sorted(
        list(set(feeds)),
        key=lambda x: x.score,
        reverse=True)
    logger.info('Returning sorted URLs: %s', sorted_urls)
    return sorted_urls
