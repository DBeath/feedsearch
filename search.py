import logging
from pprint import pprint

import click

from feedsearch import search as search_feeds


@click.command()
@click.argument('url')
@click.option('--checkall', default=False, type=click.BOOL, help='Search all potential locations for feeds')
@click.option('--feedinfo', default=False, type=click.BOOL, help='Return additional feed details')
@click.option('--parser', default='html.parser', type=str,
              help="BeautifulSoup parser ('html.parser', 'lxml', etc.). Defaults to 'html.parser'")
def search(url, checkall, feedinfo, parser):
    logging.basicConfig(level=logging.INFO)
    click.echo('Searching URL {0}'.format(url))
    feeds = search_feeds(url=url, check_all=checkall, info=feedinfo, parser=parser)
    for feed in feeds:
        print()
        pprint(vars(feed))


if __name__ == '__main__':
    search()
