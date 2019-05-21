import asyncio
import logging
from typing import List, Tuple, Union
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .feedinfo import FeedInfo
from .lib import create_soup
from .site_meta import SiteMeta
from .url import URL

logger = logging.getLogger(__name__)


class FeedFinder:
    def __init__(
        self, coerced_url: str, feed_info: bool = False, favicon_data_uri: bool = False
    ) -> None:
        self.get_feed_info: bool = feed_info
        self.favicon_data_uri: bool = favicon_data_uri
        self.soup: BeautifulSoup = None
        self.site_meta: SiteMeta = None
        self.feeds: list = []
        self.urls: List[URL] = []
        self.seen_urls: List[str] = []
        self.coerced_url: str = coerced_url

    async def check_urls_async(self, urls: List[str]) -> List[FeedInfo]:
        """
        Check if a list of Urls contain feeds

        :param urls: List of Url strings
        :return: List of FeedInfo objects
        """
        async def get_feed_async(url: str) -> FeedInfo:
            url_obj = await self.get_url_async(url)
            if url_obj.is_feed:
                feed = await self.create_feed_info_async(url_obj)
                return feed

        tasks = []
        for url_str in urls:
            if url_str not in self.seen_urls:
                self.seen_urls.append(url_str)
                tasks.append(get_feed_async(url_str))

        logger.debug("FeedInfo Tasks: %s", len(tasks))
        feeds = await asyncio.gather(*tasks)
        feeds = [f for f in feeds if isinstance(f, FeedInfo)]
        return feeds

    async def create_feed_info_async(self, url: URL) -> FeedInfo:
        """
        Creates a FeedInfo object from a URL object

        :param url: URL object
        :return: FeedInfo
        """
        info = FeedInfo(url.url, content_type=url.content_type)

        if self.get_feed_info:
            await info.get_info_async(data=url.data, headers=url.headers)

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

        :param url: Url of the soup
        :param rel: If true, only search for RSS discovery type "alternate" links
        :return: list
        """
        links: List[str] = []
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
                href = link.get("href", "")
                links.append(urljoin(url, href))

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

    async def get_site_info_async(self, url: Union[str, URL]) -> None:
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
            await self.site_meta.parse_site_info_async(self.favicon_data_uri)

    async def get_url_async(self, url: Union[str, URL]) -> URL:
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
            await url.get_is_feed(url.url)
        return url

    def internal_feedlike_urls(self) -> List[URL]:
        """
        Return a list of URLs that point to internal pages
        which may contain feeds.

        :return: List of URL objects
        """
        internal: List[URL] = []
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

    async def check_url_data_async(self, urls: List[URL]) -> List[FeedInfo]:
        """
        Check the data of each URL for links which may be feeds,
        then check the links and return any found feeds.

        :return: List of FeedInfo objects
        """

        tasks = []
        for url in urls:
            if not url.is_feed and url.data:
                to_search: List[str] = []
                url_soup = create_soup(url.data)
                to_search.extend(self.search_links(url_soup, url.url))
                local, remote = self.search_a_tags(url_soup)
                to_search.extend(local)
                to_search.extend(remote)
                tasks.append(self.check_urls_async(to_search))

        results = await asyncio.gather(*tasks)
        found: List[FeedInfo] = []
        for feeds in results:
            found.extend([f for f in feeds if isinstance(f, FeedInfo)])
        return found
