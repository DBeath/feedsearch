import logging

from .feedsearch import search_async

logging.getLogger(__name__).addHandler(logging.NullHandler())
