import base64
import logging
import re

from typing import List, Set, Dict, Any
from bs4 import BeautifulSoup, ResultSet
from werkzeug.urls import url_parse

from .lib import get_url, coerce_url, create_soup, get_timeout, get_exceptions

logger = logging.getLogger(__name__)


WORDPRESS_URLS = ["/feed"]


class SiteMeta:
    def __init__(self, url: str, data: Any = None, soup: BeautifulSoup = None) -> None:
        self.url = url  # type: str
        self.data = data  # type: Any
        self.soup = soup  # type: BeautifulSoup
        self.site_url = ""  # type: str
        self.site_name = ""  # type: str
        self.icon_url = ""  # type: str
        self.icon_data_uri = ""  # type: str
        self.domain = ""  # type: str

    def parse_site_info(self, favicon_data_uri: bool = False):
        """
        Finds Site Info from root domain of site

        :return: None
        """
        self.domain = self.get_domain(self.url)

        # Only fetch url again if domain is different from provided url or if
        # no site data already provided.
        if self.domain != self.url.strip("/") or not self.data:
            logger.debug(
                "Domain %s is different from URL %s. Fetching domain.",
                self.domain,
                self.url,
            )
            response = get_url(self.domain, get_timeout(), get_exceptions())
            if not response or not response.text:
                return
            self.data = response.text

        if not self.soup:
            self.soup = create_soup(self.data)

        self.site_url = self.find_site_url(self.soup, self.domain)
        self.site_name = self.find_site_name(self.soup)
        self.icon_url = self.find_site_icon_url(self.domain)

        if favicon_data_uri and self.icon_url:
            self.icon_data_uri = self.create_data_uri(self.icon_url)

    def find_site_icon_url(self, url: str) -> str:
        """
        Attempts to find Site Favicon

        :param url: Root domain Url of Site
        :return: str
        """
        icon_rel = ["apple-touch-icon", "shortcut icon", "icon"]

        icon = ""
        for rel in icon_rel:
            link = self.soup.find(name="link", rel=rel)
            if link:
                icon = link.get("href", None)
                if icon[0] == "/":
                    icon = "{0}{1}".format(url, icon)
                if icon == "favicon.ico":
                    icon = "{0}/{1}".format(url, icon)
        if not icon:
            send_url = url + "/favicon.ico"
            logger.debug("Trying url %s for favicon", send_url)
            response = get_url(send_url, get_timeout(), get_exceptions())
            if response and response.status_code == 200:
                logger.debug("Received url %s for favicon", response.url)
                icon = response.url
        return icon

    @staticmethod
    def find_site_name(soup) -> str:
        """
        Attempts to find Site Name

        :param soup: BeautifulSoup of site
        :return: str
        """
        site_name_meta = [
            "og:site_name",
            "og:title",
            "application:name",
            "twitter:app:name:iphone",
        ]

        for p in site_name_meta:
            try:
                name = soup.find(name="meta", property=p).get("content")
                if name:
                    return name
            except AttributeError:
                pass

        try:
            title = soup.find(name="title").text
            if title:
                return title
        except AttributeError:
            pass

        return ""

    @staticmethod
    def find_site_url(soup, url: str) -> str:
        """
        Attempts to find the canonical Url of the Site

        :param soup: BeautifulSoup of site
        :param url: Current Url of site
        :return: str
        """
        canonical = soup.find(name="link", rel="canonical")
        try:
            site = canonical.get("href")
            if site:
                return site
        except AttributeError:
            pass

        meta = soup.find(name="meta", property="og:url")
        try:
            site = meta.get("content")
        except AttributeError:
            return url
        return site

    @staticmethod
    def get_domain(url: str) -> str:
        """
        Finds root domain of Url, including scheme

        :param url: URL string
        :return: str
        """
        url = coerce_url(url)
        parsed = url_parse(url)
        domain = "{0}://{1}".format(parsed.scheme, parsed.netloc)
        return domain

    @staticmethod
    def create_data_uri(img_url: str) -> str:
        """
        Creates a Data Uri for a Favicon

        :param img_url: Url of Favicon
        :return: str
        """
        response = get_url(img_url, get_timeout(), get_exceptions(), stream=True)
        if not response or int(response.headers["content-length"]) > (1024 * 1024):
            response.close()
            return ""

        uri = ""
        try:
            encoded = base64.b64encode(response.content)
            uri = "data:image/png;base64," + encoded.decode("utf-8")
        except Exception as e:
            logger.warning("Failure encoding image: %s", e)

        response.close()
        return uri

    def cms_feed_urls(self) -> List[str]:
        """
        Checks if a site is using a popular CMS, and returns
        a list of default feed urls to check.

        :return: List[str]
        """

        site_feeds = {"WordPress": ["/feed"]}  # type: Dict[str, List[str]]

        possible_urls = set()  # type: Set[str]
        if not self.soup:
            return []

        site_names = set()  # type: Set[str]

        metas = self.soup.find_all(name="meta")
        site_names.update(self.check_meta(metas))

        links = self.soup.find_all(name="link")
        site_names.update(self.check_links(links))

        for name in site_names:
            urls = site_feeds.get(name)  # type: List[str]
            if urls:
                possible_urls.update(urls)

        # Return urls appended to the root domain to allow searching
        urls = []  # type: List[str]
        for url in possible_urls:
            urls.append(self.domain + url)
        return urls

    @staticmethod
    def check_meta(metas: ResultSet) -> Set[str]:
        """
        Check site meta to find possible CMS values.

        :param metas: ResultSet of Site Meta values
        :return: Set of possible CMS names
        """
        meta_tests = {"generator": {"WordPress": "WordPress\\s*(.*)"}}

        results = set()  # type: Set[str]

        def get_meta_value(inner_type: str, inner_metas: ResultSet):
            for meta in inner_metas:
                if inner_type in meta.get("property", ""):
                    yield meta.get("content")

        for test_type, tests in meta_tests.items():
            meta_values = list(get_meta_value(test_type, metas))
            for meta_value in meta_values:
                for site_name, pattern in tests.items():
                    if re.search(pattern, meta_value, flags=re.I):
                        results.add(site_name)

        return results

    @staticmethod
    def check_links(links: ResultSet) -> Set[str]:
        link_tests = {"WordPress": "/wp-content/"}

        results = set()  # type: Set[str]

        def get_link_href(inner_links: ResultSet):
            for link in inner_links:
                yield link.get("href")

        link_hrefs = list(get_link_href(links))
        for site_name, pattern in link_tests.items():
            for href in link_hrefs:
                if re.search(pattern, href, flags=re.I):
                    results.add(site_name)

        return results
