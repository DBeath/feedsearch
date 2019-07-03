import logging
from typing import Any

from .lib import get_url, get_timeout, get_exceptions

logger = logging.getLogger(__name__)


class URL:
    def __init__(self, url: str, data: Any = None, immediate_get: bool = True) -> None:
        """
        Initialise URL object and immediately fetch URL to check if feed.

        :param url: URL string
        """
        self.url = url  # type: str
        self.data = data  # type: Any
        self.is_feed = False  # type: bool
        self.content_type = ""  # type: str
        self.headers = {}  # type: dict
        self.links = {}  # type: dict
        self.fetched = False  # type: bool
        self.feedlike_url = self.is_feedlike_url(self.url)  # type: bool

        if immediate_get and not self.fetched:
            self.get_is_feed(self.url)

    def __repr__(self):
        return "{0}({1})".format(self.__class__.__name__, self.url.__repr__)

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

    def get_is_feed(self, url: str) -> None:
        """
        Gets a URL and checks if it might be a feed.

        :param url: URL string
        :return: None
        """
        response = get_url(url, get_timeout(), get_exceptions())

        self.fetched = True

        if not response or not response.text:
            logger.debug("Nothing found at %s", url)
            return

        self.url = response.url
        self.content_type = response.headers.get("content-type")

        self.data = response.text
        self.headers = response.headers
        self.links = response.links
        self.is_feed = self.is_feed_data(response.text, self.content_type)

    @property
    def is_valid(self) -> bool:
        """
        Check if URL returned valid response

        :return: bool
        """
        if self.url and self.data:
            return True
        return False
