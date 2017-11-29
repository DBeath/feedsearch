import logging
import time
from typing import Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .feedinfo import FeedInfo
from .lib import (get_url,
                  create_soup,
                  coerce_url,
                  get_site_root,
                  is_feed,
                  is_feedlike_url,
                  is_feed_url,
                  is_feed_data,
                  create_requests_session,
                  default_timeout,
                  set_bs4_parser)
from .site_meta import SiteMeta

logger = logging.getLogger(__name__)


class FeedFinder:
    def __init__(self,
                 get_feed_info=False):
        self.get_feed_info = get_feed_info
        self.parsed_soup = None
        self.site_meta = None

    def check_urls(self, urls: list) -> list:
        feeds = []
        for url in urls:
            url_text = is_feed(url)
            if url_text:
                feed = self.create_feed_info(url, url_text)
                feeds.append(feed)

        return feeds

    def create_feed_info(self, url: str, text: str) -> FeedInfo:
        info = FeedInfo(url)

        if self.get_feed_info:
            logger.debug('Getting FeedInfo for %s', url)
            info.get_info(text=text, soup=self.soup)

            if self.site_meta:
                info.add_site_info(self.site_meta.site_url,
                                   self.site_meta.site_name,
                                   self.site_meta.icon_url,
                                   self.site_meta.icon_data_uri)

        return info

    @property
    def soup(self) -> BeautifulSoup:
        return self.parsed_soup

    def search_links(self, url: str) -> list:
        links = []
        for link in self.soup.find_all("link"):
            if link.get("type") in ["application/rss+xml",
                                    "text/xml",
                                    "application/atom+xml",
                                    "application/x.atom+xml",
                                    "application/x-atom+xml"]:
                links.append(urljoin(url, link.get("href", "")))

        return self.check_urls(links)

    def search_a_tags(self, url: str) -> Tuple[list, list]:
        local, remote = [], []
        for a in self.soup.find_all("a"):
            href = a.get("href", None)
            if href is None:
                continue
            if "://" not in href and is_feed_url(href):
                local.append(href)
            if is_feedlike_url(href):
                remote.append(href)

        return local, remote

    def get_site_info(self, url):
        if self.get_feed_info:
            self.site_meta = SiteMeta(url)
            self.site_meta.parse_site_info()


def search(url,
           check_all=False,
           info=False,
           timeout=default_timeout,
           user_agent=None,
           max_redirects=30,
           parser='html.parser'):
    """
    Search for RSS or ATOM feeds at a given URL

    :param url: URL
    :param check_all: Check all <link> and <a> tags on page
    :param info: Get Feed and Site Metadata
    :param timeout: Request timeout
    :param user_agent: User-Agent Header string
    :param max_redirects: Maximum Request redirects
    :param parser: BeautifulSoup parser ('html.parser', 'lxml', etc.). Defaults to 'html.parser'
    :return: List of found feeds as FeedInfo objects.
             FeedInfo objects will always have a .url value.
    """

    # Wrap find_feeds in a Requests session
    with create_requests_session(user_agent, max_redirects, timeout):
        # Set BeautifulSoup parser
        set_bs4_parser(parser)
        # Find feeds
        return find_feeds(url, check_all, info)


def find_feeds(url: str,
               check_all: bool=False,
               get_feed_info: bool=False) -> list:

    finder = FeedFinder(get_feed_info=get_feed_info)

    # Format the URL properly.
    url = coerce_url(url)

    feeds = []

    start_time = time.perf_counter()

    # Download the requested URL
    logger.info('Finding feeds at URL: %s', url)
    response = get_url(url)
    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug('Searched url in %sms', search_time)

    if not response or not response.text:
        return []

    text = response.text

    # Parse text with BeautifulSoup
    finder.parsed_soup = create_soup(text)

    # Get site metadata
    finder.get_site_info(url)

    # Check if it is already a feed.
    if is_feed_data(text):

        found = finder.create_feed_info(url, text)
        feeds.append(found)
        return feeds

    # Search for <link> tags
    logger.debug('Looking for <link> tags.')
    found_links = finder.search_links(url)
    feeds.extend(found_links)
    logger.info('Found %s feed <link> tags.', len(found_links))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug('Searched <link> tags in %sms', search_time)

    if len(feeds) and not check_all:
        return sort_urls(feeds, url)

    # Look for <a> tags.
    logger.debug('Looking for <a> tags.')
    local, remote = finder.search_a_tags(url)

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

    if len(feeds) and not check_all:
        return sort_urls(feeds, url)

    # Guessing potential URLs.
    fns = ["atom.xml", "index.atom", "index.rdf", "rss.xml", "index.xml",
           "index.rss"]
    urls = list(urljoin(url, f) for f in fns)
    found_guessed = finder.check_urls(urls)
    feeds.extend(found_guessed)
    logger.info('Found %s guessed links to feeds.', len(found_guessed))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug('Searched guessed urls in %sms', search_time)

    return sort_urls(feeds, url)


def url_feed_score(url: str, original_url: str=None) -> int:
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


def sort_urls(feeds, original_url=None):
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
