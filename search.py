import logging
from pprint import pprint
import sys

import click

from feedsearch import search as search_feeds


@click.command()
@click.argument('url')
@click.option('--checkall/--no-checkall', default=False, help='Search all potential locations for feeds')
@click.option('--info/--no-info', default=False, help='Return additional feed details')
@click.option('--parser', default='html.parser', type=click.Choice(['html.parser', 'lxml', 'xml', 'html5lib']),
              help="BeautifulSoup parser ('html.parser', 'lxml', 'xml', or 'html5lib'). Defaults to 'html.parser'")
def search(url, checkall, info, parser):
    click.echo('Searching URL {0}'.format(url))
    feeds = search_feeds(url=url, check_all=checkall, info=info, parser=parser)
    for feed in feeds:
        print()
        pprint(vars(feed))


if __name__ == '__main__':
    search()
