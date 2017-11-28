import logging
import time
from typing import Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from feedsearch.feedinfo import FeedInfo
from feedsearch.lib import (get_url,
                            create_soup,
                            coerce_url,
                            get_site_root,
                            is_feed,
                            is_feedlike_url,
                            is_feed_url,
                            is_feed_data,
                            create_requests_session,
                            default_timeout)
from feedsearch.site_meta import SiteMeta


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
            logging.info(u'Getting FeedInfo for {0}'.format(url))
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
        logging.info("Looking for <a> tags.")
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


def find(url, check_all=False, get_feed_info=False, timeout=default_timeout, user_agent=None, max_redirects=30):
    """
    Find RSS or ATOM feeds at a given URL

    :param url: URL
    :param check_all: Check all <link> and <a> tags on page
    :param get_feed_info: Get Feed and Site Metadata
    :param timeout: Request timeout
    :param user_agent: User-Agent Header string
    :param max_redirects: Maximum Request redirects
    :return: List of found feeds as FeedInfo objects.
             FeedInfo objects will always have a .url value.
    """
    with create_requests_session(user_agent, max_redirects, timeout):
        return find_feeds(url, check_all, get_feed_info)


def find_feeds(url: str,
               check_all: bool=False,
               get_feed_info: bool=False) -> list:

    finder = FeedFinder(get_feed_info=get_feed_info)

    # Format the URL properly.
    url = coerce_url(url)

    feeds = []

    start_time = time.perf_counter()

    # Download the requested URL
    logging.info('Finding feeds at URL: {0}'.format(url))
    response = get_url(url)
    search_time = int((time.perf_counter() - start_time) * 1000)
    logging.debug("Searched url in {0}ms".format(search_time))

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
    logging.info("Looking for <link> tags.")
    found_links = finder.search_links(url)
    feeds.extend(found_links)
    logging.info("Found {0} feed <link> tags.".format(len(found_links)))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logging.debug("Searched <link> tags in {0}ms".format(search_time))

    if len(feeds) and not check_all:
        return sort_urls(feeds, url)

    # Look for <a> tags.
    logging.info("Looking for <a> tags.")
    local, remote = finder.search_a_tags(url)

    # Check the local URLs.
    local = [urljoin(url, l) for l in local]
    found_local = finder.check_urls(local)
    feeds.extend(found_local)
    logging.info("Found {0} local <a> links to feeds."
                .format(len(found_local)))

    # Check the remote URLs.
    remote = [urljoin(url, l) for l in remote]
    found_remote = finder.check_urls(remote)
    feeds.extend(found_remote)
    logging.info("Found {0} remote <a> links to feeds."
                .format(len(found_remote)))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logging.debug("Searched <a> links in {0}ms".format(search_time))

    if len(feeds) and not check_all:
        return sort_urls(feeds, url)

    # Guessing potential URLs.
    fns = ["atom.xml", "index.atom", "index.rdf", "rss.xml", "index.xml",
           "index.rss"]
    urls = list(urljoin(url, f) for f in fns)
    found_guessed = finder.check_urls(urls)
    feeds.extend(found_guessed)
    logging.info("Found {0} guessed links to feeds."
                .format(len(found_guessed)))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logging.debug("Searched guessed urls in {0}ms".format(search_time))

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

        if url_domain not in original_domain:
            score -= 17

    if "comments" in url:
        score -= 15
    if "georss" in url:
        score -= 9
    if "alt" in url:
        score -= 7
    kw = ["rss", "atom", ".xml", "feed", "rdf"]
    for p, t in zip(range(len(kw) * 2, 0, -2), kw):
        if t in url:
            score += p
    if url.startswith('https'):
        score += 9
    print('Url: {0}, Score: {1}'.format(url, score))
    return score


def sort_urls(feeds, original_url=None):
    """
    Sort list of feeds based on Url score

    :param feeds: List of FeedInfo objects
    :param original_url: Searched Url
    :return: List of FeedInfo objects
    """
    print('Sorting feeds: {0}'.format(feeds))
    for feed in feeds:
        feed.score = url_feed_score(feed.url, original_url)
    sorted_urls = sorted(
        list(set(feeds)),
        key=lambda x: x.score,
        reverse=True)
    logging.info(u'Returning sorted URLs: {0}'.format(sorted_urls))
    return sorted_urls
