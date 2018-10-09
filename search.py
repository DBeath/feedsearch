import logging
import traceback
from pprint import pprint

import click

from feedsearch import search as search_feeds


@click.command()
@click.argument("url")
@click.option(
    "--checkall/--no-checkall",
    default=False,
    help="Search all potential locations for feeds",
)
@click.option("--info/--no-info", default=False, help="Return additional feed details")
@click.option(
    "--parser",
    default="html.parser",
    type=click.Choice(["html.parser", "lxml", "xml", "html5lib"]),
    help="BeautifulSoup parser ('html.parser', 'lxml', 'xml', or 'html5lib'). Defaults to 'html.parser'",
)
@click.option("-v", "--verbose", is_flag=True, help="Show logging")
@click.option(
    "--exceptions/--no-exceptions",
    default=False,
    help="If False, will gracefully handle Requests exceptions and attempt to keep searching."
    "If True, will leave Requests exceptions uncaught to be handled externally.",
)
@click.option("--timeout", default=30, type=click.FLOAT, help="Request timeout")
@click.option(
    "--favicon/--no-favicon", default=False, help="Convert Favicon into Data Uri"
)
@click.option(
    "--urls/--no-urls",
    default=False,
    help="Return found Feeds as a list of URL strings instead of FeedInfo objects.",
)
def search(url, checkall, info, parser, verbose, exceptions, timeout, favicon, urls):
    if verbose:
        logger = logging.getLogger("feedsearch")
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s [in %(pathname)s:%(lineno)d]"
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    click.echo("\nSearching URL {0}\n".format(url))
    try:
        feeds = search_feeds(
            url=url,
            check_all=checkall,
            info=info,
            parser=parser,
            exceptions=exceptions,
            timeout=timeout,
            favicon_data_uri=favicon,
            as_urls=urls,
        )
        for feed in feeds:
            if not urls:
                pprint(vars(feed))
                print()
            else:
                click.echo("{0}".format(feed))

        return feeds
    except Exception as e:
        click.echo("Exception: {0}\n".format(e))
        click.echo(traceback.format_exc())

    return []


if __name__ == "__main__":
    search()
