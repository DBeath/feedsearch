import logging
from typing import Any

from .lib import get_url_async, get_timeout, get_exceptions

logger = logging.getLogger(__name__)


class URL:
    def __init__(self, url: str, data: Any = None, immediate_get: bool = False) -> None:
        """
        Initialise URL object and immediately fetch URL to check if feed.

        :param url: URL string
        """
        self.url: str = url
        self.data: Any = data
        self.is_feed: bool = False
        self.content_type: str = ""
        self.headers: dict = {}
        self.links: dict = {}
        self.fetched: bool = False
        self.feedlike_url: bool = self.is_feedlike_url(self.url)

        if immediate_get and not self.fetched:
            self.get_is_feed(self.url)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.url!r})"

    def __eq__(self, other):
        return self.url == other.url

    @staticmethod
    def is_feed_url(url: str) -> bool:
        """
        Return True if URL ending contains valid feed file format.

        :param url: URL string
        :return: bool
        """
        return any(
            map(url.lower().endswith, [".rss", ".rdf", ".xml", ".atom", ".json"])
        )

    @staticmethod
    def is_feedlike_url(url: str) -> bool:
        """
        Return True any part of URL might identify as feed.

        :param url: URL string
        :return: bool
        """
        return any(
            map(url.lower().count, ["rss", "rdf", "xml", "atom", "feed", "json"])
        )

    @staticmethod
    def is_json_feed(json: dict) -> bool:
        """
        Return True if JSON contains valid JSON Feed version.

        :param json: Parsed JSON
        :return: bool
        """
        version = json.get("version")
        if not version or "https://jsonfeed.org/version/" not in version:
            return False
        return True

    @staticmethod
    def is_feed_data(text: str, content_type: str) -> bool:
        """
        Return True if text string has valid feed beginning.

        :param text: Possible feed text
        :param content_type: MimeType of text
        :return: bool
        """
        data = text.lower()
        if not data:
            return False
        if data[:100].count("<html"):
            return False
        if "json" in content_type and data.count("jsonfeed.org"):
            return True
        return bool(
            data.count("<rss")
            + data.count("<rdf")
            + data.count("<feed")
        )

    async def get_is_feed(self, url: str) -> None:
        """
        Gets a URL and checks if it might be a feed.

        :param url: URL string
        :return: None
        """
        response = await get_url_async(url, get_timeout(), get_exceptions())

        self.fetched = True

        if not response or not response.text:
            logger.debug("Nothing found at %s", url)
            return

        self.url = str(response.url)
        self.content_type = response.headers.get("content-type")

        self.data = await response.text()
        self.headers = response.headers
        self.links = response.links
        self.is_feed = self.is_feed_data(self.data, self.content_type)

    @property
    def is_valid(self) -> bool:
        """
        Check if URL returned valid response

        :return: bool
        """
        if self.url and self.data:
            return True
        return False
