import json
import logging
from typing import Tuple

import feedparser
from bs4 import BeautifulSoup

from .lib import (bs4_parser,
                  is_feed)

logger = logging.getLogger(__name__)


class FeedInfo:
    def __init__(self,
                 url: str=None,
                 site_url: str=None,
                 title: str=None,
                 description: str=None,
                 site_name: str=None,
                 site_icon_url: str=None,
                 hub: str=None,
                 is_push: bool=False) -> None:
        self.url = url
        self.site_url = site_url
        self.title = title
        self.description = description
        self.site_name = site_name
        self.site_icon_url = site_icon_url
        self.hub = hub
        self.is_push = is_push
        self.score = None
        self.site_icon_data_uri = None

    def __repr__(self):
        return 'FeedInfo: <{0}>'.format(self.url)

    def __eq__(self, other):
        return self.url == other.url

    def __hash__(self):
        return hash(self.url)

    def get_info(self, text: str=None, soup=None):
        if text:
            parsed = self.parse_feed(text)
            self.title = self.feed_title(parsed)
            self.description = self.feed_description(parsed)
            self.hub, self_url = self.pubsubhubbub_links(parsed)
            if self.hub and self_url:
                self.is_push = True

            if self_url:
                if self_url != self.url:
                    text = is_feed(self_url)
                    if text:
                        self.url = self_url
                        return self.get_info(text, soup)

    @staticmethod
    def parse_feed(text: str) -> dict:
        return feedparser.parse(text)

    @staticmethod
    def feed_title(parsed: dict)-> str:
        feed = parsed.get('feed', None)
        title = feed.get('title', None)
        if not title:
            return ''
        return FeedInfo.clean_title(title)

    @staticmethod
    def clean_title(title: str) -> str:
        try:
            title = BeautifulSoup(title, bs4_parser).get_text()
            if len(title) > 1024:
                title = title[:1020] + u'...'
            return title
        except Exception as e:
            logger.exception('Failed to clean title: %s', e)
            return ''

    @staticmethod
    def feed_description(parsed: dict) -> str:
        feed = parsed.get('feed', None)
        subtitle = feed.get('subtitle', None)
        if subtitle:
            return subtitle
        else:
            return feed.get('description', None)

    @staticmethod
    def pubsubhubbub_links(parsed: dict) -> Tuple[str, str]:
        """
        Returns a tuple containing the hub url and the self url for
        a parsed feed.

        :param parsed: An RSS feed parsed by feedparser
        :type parsed: dict
        :return: tuple
        """

        hub_url = None
        self_url = None
        autodiscovery_url = None

        feed = parsed.get('feed', None)
        links = feed.get('links', None)
        if links is None:
            logger.warning('No feed links found')
            return '', ''

        try:
            for link in links:
                if link['rel'] == 'hub':
                    hub_url = link['href']
                if link['rel'] == 'self':
                    self_url = link['href']
                if link.get('id', None) == 'auto-discovery':
                    autodiscovery_url = link['href']
        except AttributeError as e:
            logger.warning('Attribute Error getting feed links: %s', e)
            return '', ''

        if not hub_url and autodiscovery_url:
            return FeedInfo.pubsubhubbub_links(autodiscovery_url)

        return hub_url, self_url

    def add_site_info(self, url, name, icon, icon_data_uri):
        self.site_url = url
        self.site_name = name
        self.site_icon_url = icon
        self.site_icon_data_uri = icon_data_uri

    def serialize(self):
        return json.dumps(
            self, default=lambda o: o.__dict__, sort_keys=True, indent=4)