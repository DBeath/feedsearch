import json
import logging
from typing import Tuple, Any, List

import feedparser
from bs4 import BeautifulSoup

from .lib import bs4_parser, parse_header_links
from .url import URL

logger = logging.getLogger(__name__)


class FeedInfo:
    def __init__(
        self,
        url: str,
        site_url: str = "",
        title: str = "",
        description: str = "",
        site_name: str = "",
        favicon: str = "",
        hubs: list = None,
        is_push: bool = False,
        content_type: str = "",
        version: str = "",
        self_url: str = "",
        score: int = 0,
        bozo: int = 0,
        favicon_data_uri: str = "",
    ) -> None:
        self.url = url
        self.site_url = site_url
        self.title = title
        self.description = description
        self.site_name = site_name
        self.favicon = favicon
        self.hubs = hubs or []
        self.is_push = is_push
        self.content_type = content_type
        self.version = version
        self.self_url = self_url
        self.bozo = bozo
        self.score = score
        self.favicon_data_uri = favicon_data_uri

    def __repr__(self):
        return "{0}({1})".format(self.__class__.__name__, self.url.__repr__)

    def __eq__(self, other):
        return self.url == other.url

    def __hash__(self):
        return hash(self.url)

    def get_info(self, data: Any = None, headers: dict = None) -> None:
        """
        Get Feed info from data.

        :param data: Feed data, XML string or JSON object
        :param headers: HTTP Headers of the Feed Url
        :return: None
        """
        logger.debug("Getting FeedInfo for %s", self.url)

        # Get data from URL if no data provided
        url_object = None
        if not data:
            url_object = URL(self.url)
            if url_object.is_feed:
                self.update_from_url(
                    url_object.url,
                    url_object.content_type,
                    url_object.data,
                    url_object.headers,
                )

        if not headers and url_object:
            headers = url_object.headers

        # Check link headers first for WebSub content discovery
        # https://www.w3.org/TR/websub/#discovery
        if headers:
            self.hubs, self.self_url = self.header_links(headers)

        # Try to parse data as JSON
        try:
            json_data = json.loads(data)
            logger.debug("%s data is JSON", self)
            self.content_type = "application/json"
            self.parse_json(json_data)
            return
        except json.JSONDecodeError:
            pass

        self.parse_xml(data)

    def parse_xml(self, data: str) -> None:
        """
        Get info from XML (RSS or ATOM) feed.
        :param data: XML string
        :return: None
        """
        # Parse data with feedparser
        # Don't wrap this in try/except, feedparser eats errors and returns bozo instead
        parsed = self.parse_feed(data)
        if not parsed or parsed.get("bozo") == 1:
            self.bozo = 1
            logger.warning("No valid feed data in %s", self.url)
            return

        feed = parsed.get("feed")

        # Only search if no hubs already present from headers
        if not self.hubs:
            self.hubs, self.self_url = self.websub_links(feed)

        if self.hubs and self.self_url:
            self.is_push = True

        self.version = parsed.get("version")
        self.title = self.feed_title(feed)
        self.description = self.feed_description(feed)

    def parse_json(self, data: dict) -> None:
        """
        Get info from JSON feed.

        :param data: JSON object
        :return: None
        """
        self.version = data.get("version")
        if "https://jsonfeed.org/version/" not in self.version:
            self.bozo = 1
            return

        feed_url = data.get("feed_url")
        # Check URL from feed data if mismatch
        if feed_url and feed_url != self.url:
            url = URL(feed_url)
            if url.is_feed:
                self.update_from_url(url.url, url.content_type, url.data)
                return

        self.title = data.get("title")
        self.description = data.get("description")

        favicon = data.get("favicon")
        if favicon:
            self.favicon = favicon

        # Only search if no hubs already present from headers
        if not self.hubs:
            try:
                self.hubs = list(hub.get("url") for hub in data.get("hubs", []))
            except (IndexError, AttributeError):
                pass

        if self.hubs:
            self.is_push = True

    @staticmethod
    def parse_feed(text: str) -> dict:
        """
        Parse feed with feedparser.

        :param text: Feed string
        :return: dict
        """
        return feedparser.parse(text)

    @staticmethod
    def feed_title(feed: dict) -> str:
        """
        Get feed title

        :param feed: feed dict
        :return: str
        """
        title = feed.get("title", None)
        if not title:
            return ""
        return FeedInfo.clean_title(title)

    @staticmethod
    def clean_title(title: str) -> str:
        """
        Cleans title string, and shortens if too long.
        Have had issues with dodgy feed titles.

        :param title: Title string
        :return: str
        """
        try:
            title = BeautifulSoup(title, bs4_parser).get_text()
            if len(title) > 1024:
                title = title[:1020] + "..."
            return title
        except Exception as ex:
            logger.exception("Failed to clean title: %s", ex)
            return ""

    @staticmethod
    def feed_description(feed: dict) -> str:
        """
        Get feed description.

        :param feed: feed dict
        :return: str
        """
        subtitle = feed.get("subtitle", None)
        if subtitle:
            return subtitle
        return feed.get("description", None)

    @staticmethod
    def websub_links(feed: dict) -> Tuple[List[str], str]:
        """
        Returns a tuple containing the hub url and the self url for
        a parsed feed.

        :param feed: An RSS feed parsed by feedparser
        :return: tuple
        """
        links = feed.get("links", [])
        return FeedInfo.find_hubs_and_self_links(links)

    def add_site_info(
        self, url: str = "", name: str = "", icon: str = "", icon_data_uri: str = ""
    ) -> None:
        """
        Adds site meta info to FeedInfo

        :param url: Site URL
        :param name: Site Name
        :param icon: Site Favicon
        :param icon_data_uri: Site Favicon as Data Uri
        :return: None
        """
        self.site_url = url
        self.site_name = name
        self.favicon = icon
        self.favicon_data_uri = icon_data_uri

    def update_from_url(
        self, url: str, content_type: str = "", data: Any = None, headers: dict = None
    ) -> None:
        """
        Update a FeedInfo object from a Url object

        :param url: Url string
        :param content_type: Content-Type of returned Url
        :param data: Data from returned Url
        :param headers: Dict of headers
        :return: None
        """
        self.url = url
        self.content_type = content_type
        self.get_info(data, headers)

    @classmethod
    def create_from_url(cls, url: str, content_type: str = ""):
        """
        Create a FeedInfo object from a Url

        :param url: Url string
        :param content_type: Content-Type of returned Url
        :return: FeedInfo
        """
        return cls(url=url, content_type=content_type)

    def serialize(self) -> str:
        """
        Attempt to serialize FeedInfo to JSON string

        :return: JSON
        """
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    @staticmethod
    def header_links(headers: dict) -> Tuple[List[str], str]:
        """
        Attempt to get self and hub links from HTTP headers
        https://www.w3.org/TR/websub/#x4-discovery

        :param headers: Dict of HTTP headers
        :return: None
        """
        link_header = headers.get("Link")
        links = []  # type: list
        if link_header:
            links = parse_header_links(link_header)
        return FeedInfo.find_hubs_and_self_links(links)

    @staticmethod
    def find_hubs_and_self_links(links: List[dict]) -> Tuple[List[str], str]:
        """
        Parses a list of links into self and hubs urls

        :param links: List of parsed HTTP Link Dicts
        :return: Tuple
        """
        hub_urls = []  # type: List[str]
        self_url = ""  # type: str

        if not links:
            return [], ""

        for link in links:
            try:
                if link["rel"] == "hub":
                    href = link["href"]  # type: str
                    hub_urls.append(href)
                elif link["rel"] == "self":
                    self_url = link["href"]
            except KeyError:
                continue

        return hub_urls, self_url
