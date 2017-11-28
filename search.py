import logging
from pprint import pprint

import click

from feedsearch import find
from feedsearch.lib import set_bs4_parser


@click.command()
@click.argument('url')
@click.option('--checkall', default=False, type=click.BOOL, help='Search all potential locations for feeds')
@click.option('--feedinfo', default=False, type=click.BOOL, help='Return additional feed details')
@click.option('--parser', default='html.parser', type=str,
              help="BeautifulSoup parser ('html.parser', 'lxml', etc.). Defaults to 'html.parser'")
def search(url, checkall, feedinfo, parser):
    logging.basicConfig(level=logging.INFO)
    set_bs4_parser(parser)
    click.echo('Searching URL {0}'.format(url))
    feeds = find(url=url, check_all=checkall, get_feed_info=feedinfo)
    for feed in feeds:
        print()
        pprint(vars(feed))


if __name__ == '__main__':
    search()
