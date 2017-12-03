import base64
import logging

from requests import codes
from werkzeug.urls import url_parse

from .lib import (get_url,
                  coerce_url,
                  create_soup,
                  get_timeout,
                  get_exceptions)

logger = logging.getLogger(__name__)


class SiteMeta:
    def __init__(self, url, soup=None):
        self.url = url
        self.soup = soup
        self.site_url = None
        self.site_name = None
        self.icon_url = None
        self.icon_data_uri = None

    def parse_site_info(self, favicon_data_uri: bool=False):
        """
        Finds Site Info from root domain of site

        :return: None
        """
        self.domain = self.domain(self.url)

        response = get_url(self.domain, get_timeout(), get_exceptions())
        if not response or not response.text:
            return

        self.soup = create_soup(response.text)


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
        icon_rel = ['apple-touch-icon', 'shortcut icon', 'icon']

        icon = ''
        for r in icon_rel:
            rel = self.soup.find(name='link', rel=r)
            if rel:
                icon = rel.get('href', None)
                if icon[0] == '/':
                    icon = '{0}{1}'.format(url, icon)
                if icon == 'favicon.ico':
                    icon = '{0}/{1}'.format(url, icon)
        if not icon:
            send_url = url + '/favicon.ico'
            logger.debug('Trying url %s for favicon', send_url)
            r = get_url(url, get_timeout(), get_exceptions())
            if r:
                logger.debug('Received url %s for favicon', r.url)
                if r.status_code == codes.ok:
                    icon = r.url
        return icon

    @staticmethod
    def find_site_name(soup) -> str:
        """
        Attempts to find Site Name

        :param soup: BeautifulSoup of site
        :return: str
        """
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
        """
        Attempts to find the canonical Url of the Site

        :param soup: BeautifulSoup of site
        :param url: Current Url of site
        :return: str
        """
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

    @staticmethod
    def domain(url: str) -> str:
        """
        Finds root domain of Url, including scheme

        :param url: URL string
        :return: str
        """
        url = coerce_url(url)
        parsed = url_parse(url)
        domain = '{url.scheme}://{url.netloc}'.format(url=parsed)
        return domain

    @staticmethod
    def create_data_uri(img_url: str) -> str:
        """
        Creates a Data Uri for a Favicon

        :param img_url: Url of Favicon
        :return: str
        """
        with get_url(img_url, get_timeout(), get_exceptions(), stream=True) as r:
            if not r or int(r.headers['content-length']) > 500000:
                return ''

            uri = ''
            try:
                encoded = base64.b64encode(r.content)
                uri = "data:image/png;base64," + encoded.decode("utf-8")
            except Exception as e:
                logger.warning('Failure encoding image: %s', e)

            return uri