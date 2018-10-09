import logging
from typing import List, Tuple, Union
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .feedinfo import FeedInfo
from .site_meta import SiteMeta
from .url import URL

logger = logging.getLogger(__name__)


class FeedFinder:
    def __init__(self, feed_info: bool = False, favicon_data_uri: bool = False) -> None:
        self.get_feed_info: bool = feed_info
        self.favicon_data_uri: bool = favicon_data_uri
        self.soup: BeautifulSoup = None
        self.site_meta: SiteMeta = None
        self.feeds: list = []

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

        if self.get_feed_info:
            info.get_info(data=url.data)

            if self.site_meta:
                info.add_site_info(
                    self.site_meta.site_url,
                    self.site_meta.site_name,
                    self.site_meta.icon_url,
                    self.site_meta.icon_data_uri,
                )

        return info

    def search_links(self, url: str) -> List[str]:
        """
        Search all links on a page for feeds

        :param url: Url of the soup
        :return: list
        """
        links: List[str] = []
        for link in self.soup.find_all("link"):
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
