import logging
import time
from typing import List, Tuple, Union
from urllib.parse import urljoin

from requests import ReadTimeout

from .feedfinder import FeedFinder
from .feedinfo import FeedInfo
from .lib import (
    coerce_url,
    create_requests_session_async,
    create_soup,
    default_timeout,
    get_site_root,
    set_bs4_parser,
    timeit,
    get_exceptions,
    set_exceptions
)

logger = logging.getLogger(__name__)


async def search_async(
    url,
    info: bool = False,
    check_all: bool = False,
    cms: bool = True,
    discovery_only: bool = False,
    favicon_data_uri: bool = False,
    as_urls: bool = False,
    timeout: Union[float, Tuple[float, float]] = default_timeout,
    user_agent: str = "",
    max_redirects: int = 30,
    parser: str = "html.parser",
    exceptions: bool = False,
) -> Union[List[FeedInfo], List[str]]:
    """
    Search for RSS or ATOM feeds at a given URL

    :param url: URL
    :param info: Get Feed and Site Metadata
    :param check_all: Check all <link> and <a> tags on page
    :param cms: Check default CMS feed location if site is using a known CMS.
    :param discovery_only: Only search for RSS discovery tags (e.g. <link rel=\"alternate\" href=...>).
    :param favicon_data_uri: Fetch Favicon and convert to Data Uri
    :param as_urls: Return found Feeds as a list of URL strings instead
        of FeedInfo objects
    :param timeout: Request timeout, either a float or (float, float).
        See Requests documentation: http://docs.python-requests.org/en/master/user/advanced/#timeouts
    :param user_agent: User-Agent Header string
    :param max_redirects: Maximum Request redirects
    :param parser: BeautifulSoup parser ('html.parser', 'lxml', etc.).
        Defaults to 'html.parser'
    :param exceptions: If False, will gracefully handle Requests exceptions and
        attempt to keep searching. If True, will leave Requests exceptions
        uncaught to be handled externally.
    :return: List of found feeds as FeedInfo objects or URL strings (depending on "as_url" parameter).
        FeedInfo objects will always have a "url" value.
    """
    # Wrap find_feeds in a Requests session
    async with create_requests_session_async(
        user_agent=user_agent,
        max_redirects=max_redirects,
        timeout=timeout,
        exceptions=exceptions,
    ):
        # Set BeautifulSoup parser
        set_bs4_parser(parser)
        # Find feeds
        feeds = await _find_feeds_async(
            url,
            feed_info=info,
            check_all=check_all,
            cms=cms,
            discovery_only=discovery_only,
            favicon_data_uri=favicon_data_uri,
        )
        # If as_urls is true, return only URL strings
        if as_urls:
            return list(f.url for f in feeds)
        else:
            return feeds


@timeit
async def _find_feeds_async(
    url: str,
    feed_info: bool = False,
    check_all: bool = False,
    cms: bool = True,
    discovery_only: bool = False,
    favicon_data_uri: bool = False,
) -> List[FeedInfo]:
    """
    Finds feeds

    :param url: URL
    :param check_all: Check all the pages of <a> tags for feeds
    :param feed_info: Get Feed and Site Metadata
    :param favicon_data_uri: Fetch Favicon and convert to Data Uri
    :param cms: Check default CMS feed location if site is using a known CMS.
    :param discovery_only: Only search for RSS discovery tags (e.g. <link rel=\"alternate\" href=...>).
    :return: List of found feeds as FeedInfo objects.
    """
    # Format the URL properly. Use HTTPS
    coerced_url: str = coerce_url(url)

    # Create Feedfinder
    finder = FeedFinder(
        coerced_url, feed_info=feed_info, favicon_data_uri=favicon_data_uri
    )

    # Initialise List of found Feeds
    feeds: list = []

    start_time = time.perf_counter()

    # Download the requested URL
    logger.info("Finding feeds at URL: %s", coerced_url)

    # Get URL and check if feed
    found_url = None

    # If the Caller provided an explicit HTTPS URL or asked for exceptions
    # to be raised, then make the first fetch without explicit exception
    # handling, as we don't want to retry with HTTP only.
    if url.startswith("https://") or get_exceptions():
        found_url = await finder.get_url_async(coerced_url)
    # Else, we perform the fetch with exception handling, so we can retry
    # with an HTTP URL if we had a ReadTimeout using HTTPS.
    else:
        try:
            # Set context to raise RequestExceptions on first fetch.
            set_exceptions(True)
            found_url = await finder.get_url_async(coerced_url)
        except ReadTimeout as ex:
            # Set Local Context exception settings back to Caller provided settings.
            set_exceptions(False)
            # Coerce URL with HTTP instead of HTTPS
            coerced_url = coerce_url(url, https=False)
            finder.coerced_url = coerced_url
            found_url = await finder.get_url_async(coerced_url)
        finally:
            # Always set Local Context exception settings back to Caller provided settings.
            set_exceptions(False)

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug("Searched url in %sms", search_time)

    # If URL is valid, then get site info if feed_info is True
    if found_url and found_url.is_valid:
        if feed_info:
            await finder.get_site_info_async(found_url)
    # Return nothing if there is no data from the URL
    else:
        return []

    # If URL is already a feed, create and return FeedInfo
    if found_url.is_feed:
        found = await finder.create_feed_info_async(found_url)
        feeds.append(found)
        return feeds

    # Parse text with BeautifulSoup
    finder.soup = create_soup(found_url.data)

    # If discovery_only, then search for <link rel=\"alternate\"> tags and return
    if discovery_only and not check_all:
        logger.debug('Looking for <link rel="alternate"> tags.')
        links = finder.search_links(finder.soup, found_url.url)
        found_links = await finder.check_urls_async(links)
        feeds.extend(found_links)
        logger.info('Found %s feed <link rel="alternate" > tags.', len(found_links))
        return sort_urls(feeds, url)

    # Search for <link> tags
    logger.debug("Looking for <link> tags.")
    links = finder.search_links(finder.soup, found_url.url)
    found_links = await finder.check_urls_async(links)
    feeds.extend(found_links)
    logger.info("Found %s feed <link> tags.", len(found_links))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug("Searched <link> tags in %sms", search_time)

    # Return if feeds are already found and check_all is False.
    if feeds and not check_all:
        return sort_urls(feeds, url)

    # Search for default CMS feeds.
    if cms or check_all:
        if not finder.site_meta:
            await finder.get_site_info_async(coerced_url)
        logger.debug("Looking for CMS feeds.")
        cms_urls = finder.site_meta.cms_feed_urls()
        found_cms = await finder.check_urls_async(cms_urls)
        logger.info("Found %s CMS feeds.", len(found_cms))
        feeds.extend(found_cms)

    # Return if feeds are already found and check_all is False.
    if feeds and not check_all:
        return sort_urls(feeds, url)

    # Look for <a> tags.
    logger.debug("Looking for <a> tags.")
    local, remote = finder.search_a_tags(finder.soup)

    # Check the local URLs.
    local: list = [urljoin(coerced_url, l) for l in local]
    # Check the remote URLs.
    remote: list = [urljoin(coerced_url, l) for l in remote]
    hrefs = local + remote
    found_hrefs = await finder.check_urls_async(hrefs)
    feeds.extend(found_hrefs)
    logger.info("Found %s <a> links to feeds.", len(found_hrefs))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug("Searched <a> links in %sms", search_time)

    # Only check internal pages if check_all is True.
    if not check_all:
        return sort_urls(feeds, url)

    # Check all possible internal urls that may point to a feed page.
    internal = finder.internal_feedlike_urls()
    found_internal = await finder.check_url_data_async(internal)
    feeds.extend(found_internal)

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug("Searched internal pages in %sms", search_time)

    # Return if feeds are found. Guessing URLs is a last resort.
    if feeds:
        return sort_urls(feeds, url)

    # Guessing potential URLs.
    fns = [
        "atom.xml",
        "index.atom",
        "index.rdf",
        "rss.xml",
        "index.xml",
        "index.rss",
        "index.json",
    ]
    urls = list(urljoin(coerced_url, f) for f in fns)
    found_guessed = await finder.check_urls_async(urls)
    feeds.extend(found_guessed)
    logger.info("Found %s guessed links to feeds.", len(found_guessed))

    search_time = int((time.perf_counter() - start_time) * 1000)
    logger.debug("Searched guessed urls in %sms", search_time)

    return sort_urls(feeds, url)


def url_feed_score(url: str, original_url: str = "") -> int:
    """
    Return a Score based on estimated relevance of the feed Url
    to the original search Url

    :param url: Feed Url
    :param original_url: Searched Url
    :return: Score integer
    """
    score = 0

    if original_url:
        url_domain = get_site_root(url)
        original_domain = get_site_root(original_url)

        if original_domain not in url_domain:
            score -= 17

    if "comments" in url:
        score -= 15
    if "georss" in url:
        score -= 9
    if "alt" in url:
        score -= 7
    kw = ["atom", "rss", ".xml", "feed", "rdf"]
    for p, t in zip(range(len(kw) * 2, 0, -2), kw):
        if t in url:
            score += p
    if url.startswith("https"):
        score += 9
    return score


def sort_urls(feeds: List[FeedInfo], original_url: str = "") -> List[FeedInfo]:
    """
    Sort list of feeds based on Url score

    :param feeds: List of FeedInfo objects
    :param original_url: Searched Url
    :return: List of FeedInfo objects
    """
    for feed in feeds:
        feed.score = url_feed_score(feed.url, original_url)
    sorted_urls = sorted(list(set(feeds)), key=lambda x: x.score, reverse=True)
    logger.info("Returning sorted URLs: %s", sorted_urls)
    return sorted_urls
