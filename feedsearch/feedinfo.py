import base64
import json
import logging
from typing import Tuple
from urllib import parse as urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from marshmallow import Schema, fields, post_load

from feedsearch.lib import get_url, bs4_parser


class FeedInfoSchema(Schema):
    url = fields.Url()
    site_url = fields.Url(allow_none=True)
    title = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    site_name = fields.String(allow_none=True)
    site_icon_url = fields.Url(allow_none=True)
    subscribed = fields.Boolean(allow_none=True)
    hub = fields.Url(allow_none=True)
    score = fields.Integer(allow_none=True)
    site_icon_datauri = fields.String(allow_none=True)

    @post_load
    def make_feed_info(self, data):
        return FeedInfo(**data)


class FeedInfo:
    def __init__(self,
                 url: str = None,
                 site_url: str = None,
                 title: str = None,
                 description: str = None,
                 site_name: str = None,
                 site_icon_url: str = None,
                 hub: str = None,
                 subscribed: bool = False,
                 is_push: bool = False) -> None:
        self.url = url
        self.site_url = site_url
        self.title = title
        self.description = description
        self.site_name = site_name
        self.site_icon_url = site_icon_url
        self.hub = hub
        self.subscribed = subscribed
        self.is_push = is_push
        self.score = None
        self.site_icon_datauri = None

    def __repr__(self):
        return 'FeedInfo: {0}'.format(self.url)

    def __eq__(self, other):
        return self.url == other.url

    def __hash__(self):
        return hash(self.url)

    def get_info(self, text: str=None, soup=None, finder=None):
        if finder:
            self.finder = finder

        if text:
            parsed = self.parse_feed(text)
            self.title = self.feed_title(parsed)
            self.description = self.feed_description(parsed)
            self.hub, self_url = self.pubsubhubbub_links(parsed)
            if self.hub and self_url:
                self.is_push = True

            if self_url and self.finder is not None:
                if self_url != self.url:
                    text = self.finder.is_feed(self_url)
                    if text:
                        self.url = self_url
                        return self.get_info(text, soup)

        if soup:
            self.site_name = self.find_site_name(soup)
            self.site_url = self.find_site_url(soup, self.site_url)
            domain = self.domain(self.site_url)
            self.site_icon_url = self.find_site_icon_url(soup, domain)
            # if self.site_icon_url:
            #     self.site_icon_datauri = self.create_data_uri(self.site_icon_url)

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
            logging.exception(u'Failed to clean title: {0}'.format(e))
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
    def find_site_name(soup) -> str:
        site_name_meta = [
            'og:site_name',
            'og:title',
            'application:name',
            'twitter:app:name:iphone'
        ]

        for p in site_name_meta:
            try:
                name = soup.find(name='meta', property=p).get('content')
                if name:
                    return name
            except AttributeError:
                pass
        return ''

    @staticmethod
    def find_site_url(soup, url: str) -> str:
        canonical = soup.find(name='link', rel='canonical')
        try:
            site = canonical.get('href')
            if site:
                return site
        except AttributeError:
            pass

        meta = soup.find(name='meta', property='og:url')
        try:
            site = meta.get('content')
            if site:
                return site
        except AttributeError:
            return url

    def find_site_icon_url(self, soup, url) -> str:
        icon_rel = ['apple-touch-icon', 'shortcut icon', 'icon']

        icon = ''
        for r in icon_rel:
            rel = soup.find(name='link', rel=r)
            if rel:
                icon = rel.get('href', None)
                if icon[0] == '/':
                    icon = '{0}{1}'.format(url, icon)
                if icon == 'favicon.ico':
                    icon = '{0}/{1}'.format(url, icon)
        if not icon:
            send_url = url + '/favicon.ico'
            print('Trying url {0} for favicon'.format(send_url))
            r = get_url(send_url)
            if r:
                print('Received url {0}'.format(r.url))
                if r.status_code == requests.codes.ok:
                    icon = r.url
        return icon

    @staticmethod
    def domain(url: str) -> str:
        parsed = urlparse.urlparse(url)
        domain = '{uri.scheme}://{uri.netloc}'.format(uri=parsed)
        return domain

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
            logging.warning(u'No feed links found')
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
            logging.warning(u'Attribute Error getting feed links: {0}'
                           .format(e))
            return '', ''

        if not hub_url and autodiscovery_url:
            return FeedInfo.pubsubhubbub_links(autodiscovery_url)

        return hub_url, self_url

    @staticmethod
    def create_data_uri(img_url):
        r = get_url(img_url)
        if not r or not r.content:
            return None

        uri = None
        try:
            encoded = base64.b64encode(r.content)
            uri = "data:image/png;base64," + encoded.decode("utf-8")
        except Exception as e:
            logging.warning(u'Failure encoding image: {0}'.format(e))

        return uri

    def serialize(self):
        return json.dumps(
            self, default=lambda o: o.__dict__, sort_keys=True, indent=4)