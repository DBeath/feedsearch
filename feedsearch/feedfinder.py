import logging
import time
from typing import Tuple
from urllib.parse import urlsplit, urljoin

from bs4 import BeautifulSoup

from feedsearch.feedinfo import FeedInfo
from feedsearch.lib import (requests_session,
                            get_url,
                            create_soup)


def coerce_url(url: str) -> str:
    url = url.strip()
    if url.startswith("feed://"):
        return "http://{0}".format(url[7:])
    for proto in ["http://", "https://"]:
        if url.startswith(proto):
            return url
    return "https://{0}".format(url)


def get_site_root(url: str) -> str:
    """
    Find the root domain of a url
    """
    url = coerce_url(url)
    parsed = urlsplit(url)
    return parsed.netloc


class FeedFinder:
    def __init__(self,
                 get_feed_info=False,
                 timeout=(3.05, 10)):
        self.get_feed_info = get_feed_info
        self.timeout = timeout
        self.parsed_soup = None

    @staticmethod
    def is_feed_data(text: str) -> bool:
        data = text.lower()
        if data.count('<html'):
            return False
        return bool(data.count('<rss') +
                    data.count('<rdf') +
                    data.count('<feed'))

    def is_feed(self, url: str) -> str:
        response = get_url(url)

        if not response or not response.text or not self.is_feed_data(response.text):
            return ''

        return response.text

    @staticmethod
    def is_feed_url(url: str) -> bool:
        return any(map(url.lower().endswith, [".rss",
                                              ".rdf",
                                              ".xml",
                                              ".atom"]))

    @staticmethod
    def is_feedlike_url(url: str) -> bool:
        return any(map(url.lower().count, ["rss",
                                           "rdf",
                                           "xml",
                                           "atom",
                                           "feed"]))

    def check_urls(self, urls: list) -> list:
        feeds = []
        for url in urls:
            url_text = self.is_feed(url)
            if url_text:
                feed = self.create_feed_info(url, url_text)
                feeds.append(feed)

        return feeds

    def create_feed_info(self, url: str, text: str) -> FeedInfo:
        info = FeedInfo(url)

        if self.get_feed_info:
            logging.info(u'Getting FeedInfo for {0}'.format(url))
            info.get_info(text=text, soup=self.soup, finder=self)

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
            if "://" not in href and self.is_feed_url(href):
                local.append(href)
            if self.is_feedlike_url(href):
                remote.append(href)

        return local, remote


@requests_session()
def find_feeds(url: str,
               check_all: bool=False,
               get_feed_info: bool=False,
               timeout: tuple=(3.05, 10)) -> list:

    finder = FeedFinder(get_feed_info=get_feed_info, timeout=timeout)

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

    # Check if it is already a feed.
    if finder.is_feed_data(text):

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
