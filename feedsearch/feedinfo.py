import json
import logging
from typing import Tuple, Any

import feedparser
from bs4 import BeautifulSoup

from .lib import bs4_parser
from .url import URL

logger = logging.getLogger(__name__)


class FeedInfo:
    def __init__(self,
                 url: str,
                 site_url: str='',
                 title: str='',
                 description: str='',
                 site_name: str='',
                 favicon_url: str='',
                 hub: str='',
                 is_push: bool=False,
                 content_type: str='',
                 version: str='',
                 self_url: str='',
                 score: int=0,
                 bozo: int=0,
                 favicon_data_uri: str='') -> None:
        self.url = url
        self.site_url = site_url
        self.title = title
        self.description = description
        self.site_name = site_name
        self.favicon = favicon_url
        self.hub = hub
        self.is_push = is_push
        self.content_type = content_type
        self.version = version
        self.self_url = self_url
        self.bozo = bozo
        self.score = score
        self.favicon_data_uri = favicon_data_uri

    def __repr__(self):
        return f'{self.__class__.__name__}({self.url!r})'

    def __eq__(self, other):
        return self.url == other.url

    def __hash__(self):
        return hash(self.url)

    def get_info(self, data: Any=None) -> None:
        """
        Get Feed info from data.

        :param data: Feed data, XML string or JSON object
        :return: None
        """
        logger.debug('Getting FeedInfo for %s', self.url)

        if not data:
            url = URL(self.url)
            if url.is_feed:
                return self.update_from_url(url.url, url.content_type, url.data)

        # Try to parse data as JSON
        try:
            json_data = json.loads(data)
            logger.debug('%s data is JSON', self)
            self.content_type = 'application/json'
            return self.parse_json(json_data)
        except json.JSONDecodeError:
            pass

        # Parse data with feedparser
        # Don't wrap this in try/except, feedparser eats errors and returns bozo instead
        parsed = self.parse_feed(data)
        if not parsed or parsed.get('bozo') == 1:
            self.bozo = 1
            logger.warning('No valid feed data in %s', self.url)
            return

        feed = parsed.get('feed')

        self.hub, self.self_url = self.pubsubhubbub_links(feed)

        if self.hub and self.self_url:
            self.is_push = True

        self.version = parsed.get('version')
        self.title = self.feed_title(feed)
        self.description = self.feed_description(feed)


    def parse_json(self, data: dict) -> None:
        """
        Get info from JSON feed.

        :param data: JSON object
        :return: None
        """
        self.version = data.get('version')
        if 'https://jsonfeed.org/version/' not in self.version:
            self.bozo = 1
            return

        feed_url = data.get('feed_url')
        # Check URL from feed data if mismatch
        if feed_url and feed_url != self.url:
            url = URL(feed_url)
            if url.is_feed:
                return self.update_from_url(url.url, url.content_type, url.data)

        self.title = data.get('title')
        self.description = data.get('description')

        favicon = data.get('favicon')
        if favicon:
            self.favicon = favicon

        try:
            self.hub = data.get('hubs', [])[0].get('url')
        except (IndexError, AttributeError):
            pass

        if self.hub:
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
    def feed_title(feed: dict)-> str:
        """
        Get feed title

        :param feed: feed dict
        :return: str
        """
        title = feed.get('title', None)
        if not title:
            return ''
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
                title = title[:1020] + u'...'
            return title
        except Exception as e:
            logger.exception('Failed to clean title: %s', e)
            return ''

    @staticmethod
    def feed_description(feed: dict) -> str:
        """
        Get feed description.

        :param feed: feed dict
        :return: str
        """
        subtitle = feed.get('subtitle', None)
        if subtitle:
            return subtitle
        else:
            return feed.get('description', None)

    @staticmethod
    def pubsubhubbub_links(feed: dict) -> Tuple[str, str]:
        """
        Returns a tuple containing the hub url and the self url for
        a parsed feed.

        :param parsed: An RSS feed parsed by feedparser
        :type parsed: dict
        :return: tuple
        """

        hub_url = None
        self_url = None

        try:
            for link in feed.get('links'):
                if link['rel'] == 'hub':
                    hub_url = link['href']
                if link['rel'] == 'self':
                    self_url = link['href']
        except AttributeError as e:
            logger.warning('Attribute Error getting feed links: %s', e)
            return '', ''

        return hub_url, self_url

    def add_site_info(self,
                      url: str='',
                      name: str='',
                      icon: str='',
                      icon_data_uri: str=''):
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

    def update_from_url(self, url: str, content_type: str='', data: Any=None):
        """
        Update a FeedInfo object from a Url

        :param url: Url string
        :param content_type: Content-Type of returned Url
        :param data: Data from returned Url
        :return: None
        """
        self.url = url
        self.content_type = content_type
        self.get_info(data)

    @classmethod
    def create_from_url(cls, url: str, content_type: str=''):
        """
        Create a FeedInfo object from a Url
        :param url: Url string
        :param content_type: Content-Type of returned Url
        :return: FeedInfo
        """
        return cls(url=url, content_type=content_type)

    def serialize(self):
        """
        Attempt to serialize FeedInfo to JSON string

        :return: JSON
        """
        return json.dumps(
            self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
