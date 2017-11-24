import click
from feedsearch.feedfinder import find_feeds
from pprint import pprint
import logging

@click.command()
@click.argument('url')
@click.option('--checkall', default=False, type=click.BOOL, help='Search all potential locations for feeds')
@click.option('--feedinfo', default=False, type=click.BOOL, help='Return additional feed details')
def search(url, checkall, feedinfo):
    logging.basicConfig(level=logging.INFO)
    click.echo('Searching URL {0}'.format(url))
    feeds = find_feeds(url=url, check_all=checkall, get_feed_info=feedinfo)
    for feed in feeds:
        pprint(vars(feed))


if __name__ == '__main__':
    search()
