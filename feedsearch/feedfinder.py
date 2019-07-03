import logging
from typing import List, Tuple, Union
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .feedinfo import FeedInfo
from .site_meta import SiteMeta
from .url import URL
from .lib import create_soup

logger = logging.getLogger(__name__)


class FeedFinder:
    def __init__(
        self, coerced_url: str, feed_info: bool = False, favicon_data_uri: bool = False
    ) -> None:
        self.get_feed_info = feed_info  # type: bool
        self.favicon_data_uri = favicon_data_uri  # type: bool
        self.soup = None
        self.site_meta = None
        self.feeds = []  # type: list
        self.urls = []  # type: List[URL]
        self.coerced_url = coerced_url  # type: str

    def check_urls(self, urls: List[str]) -> List[FeedInfo]:
        """
        Check if a list of Urls contain feeds

        :param urls: List of Url strings
        :return: List of FeedInfo objects
        """
        feeds = []
        for url_str in urls:
            url = self.get_url(url_str)
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

        if self.get_feed_info:
            info.get_info(data=url.data, headers=url.headers)

            if self.site_meta:
                info.add_site_info(
                    self.site_meta.site_url,
                    self.site_meta.site_name,
                    self.site_meta.icon_url,
                    self.site_meta.icon_data_uri,
                )

        return info

    @staticmethod
    def search_links(soup: BeautifulSoup, url: str, rel: bool = False) -> List[str]:
        """
        Search all links on a page for feeds

        :param soup: BeautifulSoup dict
        :param url: Url of the soup
        :param rel: If true, only search for RSS discovery type "alternate" links
        :return: list
        """
        links = []  # type: List[str]
        if rel:
            link_tags = soup.find_all("link", rel="alternate")
        else:
            link_tags = soup.find_all("link")
        for link in link_tags:
            if link.get("type") in [
                "application/rss+xml",
                "text/xml",
                "application/atom+xml",
                "application/x.atom+xml",
                "application/x-atom+xml",
                "application/json",
            ]:
                links.append(urljoin(url, link.get("href", "")))

        return links

    @staticmethod
    def search_a_tags(soup: BeautifulSoup) -> Tuple[List[str], List[str]]:
        """
        Search all 'a' tags on a page for feeds

        :return: Tuple[list, list]
        """
        local, remote = [], []
        for a in soup.find_all("a"):
            href = a.get("href", None)
            if href is None:
                continue
            if "://" not in href and URL.is_feed_url(href):
                local.append(href)
            if URL.is_feedlike_url(href):
                remote.append(href)

        return local, remote

    def get_site_info(self, url: Union[str, URL]) -> None:
        """
        Search for site metadata

        :param url: Site Url
        :return: None
        """
        if isinstance(url, str):
            self.site_meta = SiteMeta(url)
        elif isinstance(url, URL):
            self.site_meta = SiteMeta(url.url, data=url.data)
        if self.site_meta:
            self.site_meta.parse_site_info(self.favicon_data_uri)

    def get_url(self, url: Union[str, URL]) -> URL:
        """
        Return a unique URL object containing fetched URL data

        :param url: URL string or URL object
        :return: URL object
        """
        if isinstance(url, str):
            if "://" not in url:
                url = urljoin(self.coerced_url, url)
            url = URL(url, immediate_get=False)
        if url in self.urls:
            url = self.urls[self.urls.index(url)]
        else:
            self.urls.append(url)
        if not url.data:
            url.get_is_feed(url.url)
        return url

    def internal_feedlike_urls(self) -> List[URL]:
        """
        Return a list of URLs that point to internal pages
        which may contain feeds.

        :return: List of URL objects
        """
        internal = []  # type: List[URL]
        parsed_coerced = urlparse(self.coerced_url)
        for url in self.urls:
            if not url.is_feed and url.fetched and url.feedlike_url:
                parsed = urlparse(url.url)
                # We want to check that the url is internal.
                # The coerced netloc is likely to be less complete (i.e. missing www subdomain)
                # than the netloc of the fetched url.
                if parsed_coerced.netloc in parsed.netloc:
                    internal.append(url)
        return internal

    def check_url_data(self, urls: List[URL]) -> List[FeedInfo]:
        """
        Check the data of each URL for links which may be feeds,
        then check the links and return any found feeds.

        :return: List of FeedInfo objects
        """
        found = []  # type: List[FeedInfo]

        for url in urls:
            if not url.is_feed and url.data:
                to_search = []  # type: List[str]
                url_soup = create_soup(url.data)
                to_search.extend(self.search_links(url_soup, url.url))
                local, remote = self.search_a_tags(url_soup)
                to_search.extend(local)
                to_search.extend(remote)
                found.extend(self.check_urls(to_search))

        return found
