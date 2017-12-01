import logging
from pprint import pprint

import click

from feedsearch import search as search_feeds


@click.command()
@click.argument('url')
@click.option('--checkall/--no-checkall', default=False, help='Search all potential locations for feeds')
@click.option('--info/--no-info', default=False, help='Return additional feed details')
@click.option('--parser', default='html.parser', type=click.Choice(['html.parser', 'lxml', 'xml', 'html5lib']),
              help="BeautifulSoup parser ('html.parser', 'lxml', 'xml', or 'html5lib'). Defaults to 'html.parser'")
@click.option('-v', '--verbose', is_flag=True, help='Show logging')
@click.option('--exceptions/--no-exceptions', default=False,
              help='If False, will gracefully handle Requests exceptions and attempt to keep searching.'
                   'If True, will leave Requests exceptions uncaught to be handled externally.')
@click.option('--timeout', default=30, type=click.FLOAT, help='Request timeout')
def search(url, checkall, info, parser, verbose, exceptions, timeout):
    if verbose:
        logger = logging.getLogger('feedsearch')
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    click.echo('\nSearching URL {0}\n'.format(url))
    try:
        feeds = search_feeds(url=url, check_all=checkall, info=info, parser=parser, exceptions=exceptions, timeout=timeout)
        for feed in feeds:
            print()
            pprint(vars(feed))
    except Exception as e:
        click.echo('Exception: {0}\n'.format(e))


if __name__ == '__main__':
    search()
