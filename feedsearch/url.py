import logging

from .lib import (get_url,
                  get_timeout,
                  get_exceptions)

logger = logging.getLogger(__name__)


class URL:
    def __init__(self, url: str, data: any=None):
        """
        Initialise URL object and immediately fetch URL to check if feed.

        :param url: URL string
        """
        self.url = url
        self.data = data
        self.is_feed = False
        self.content_type = None

        self.get_is_feed(self.url)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.url!r})'

    @staticmethod
    def is_feed_url(url: str) -> bool:
        """
        Return True if URL ending contains valid feed file format.

        :param url: URL string
        :return: bool
        """
        return any(map(url.lower().endswith, ['.rss',
                                              '.rdf',
                                              '.xml',
                                              '.atom',
                                              '.json']))

    @staticmethod
    def is_feedlike_url(url: str) -> bool:
        """
        Return True any part of URL might identify as feed.

        :param url: URL string
        :return: bool
        """
        return any(map(url.lower().count, ['rss',
                                           'rdf',
                                           'xml',
                                           'atom',
                                           'feed',
                                           'json']))

    @staticmethod
    def is_json_feed(json: dict) -> bool:
        """
        Return True if JSON contains valid JSON Feed version.

        :param json: Parsed JSON
        :return: bool
        """
        version = json.get('version')
        if not version or not 'https://jsonfeed.org/version/' in version:
            return False
        return True

    @staticmethod
    def is_feed_data(text: str) -> bool:
        """
        Return True if text string has valid feed beginning.

        :param text: Possible feed text
        :return: bool
        """
        data = text.lower()
        if data.count('<html'):
            return False
        return bool(data.count('<rss') +
                    data.count('<rdf') +
                    data.count('<feed'))

    def get_is_feed(self, url: str) -> None:
        """
        Gets a URL and checks if it might be a feed.

        :param url: URL string
        :return: None
        """
        response = get_url(url, get_timeout(), get_exceptions())

        if not response or not response.text:
            logger.warning('Nothing found at %s', url)
            return

        self.url = response.url
        self.content_type = response.headers.get('content-type')

        # Attempt to parse response as JSON
        try:
            self.data = response.json()
            self.is_feed = self.is_json_feed(self.data)
            self.content_type = 'application/json'
        # If not valid JSON then parse as text string
        except ValueError:
            self.data = response.text
            self.is_feed = self.is_feed_data(response.text)
