import functools
import requests
import logging
from werkzeug.local import Local, release_local

REQUEST_SESSION = Local()

logger = logging.getLogger('feedsearch')

def get_session():
    return getattr(REQUEST_SESSION, 'session', None)


def get_user_agent():
    """
    Return User Agent string
    """
    return "FeedSearch/0.1 (https://github.com/DBeath/feedsearch)"


def requests_session(user_agent=get_user_agent(), max_redirects=30):
    """
    Wraps a requests session around a function.

    :param user_agent: User Agent for requests
    :param max_redirects: Maximum number of redirects
    :return: decorator function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a request session
            session = requests.session()
            session.headers.update({"User-Agent": user_agent})
            session.max_redirects = max_redirects

            # Add request session to local context
            setattr(REQUEST_SESSION, 'session', session)

            # Call wrapped function
            result = func(*args, **kwargs)

            # Close request session
            get_session().close()

            # Clean up local context
            release_local(REQUEST_SESSION)

            return result

        return wrapper

    return decorator


def get_url(url, timeout=(3.05, 10)):
    try:
        response = get_session().get(url, timeout=timeout)
    except Exception as e:
        logger.warning(u'Error while getting URL: {0}, {1}'
                       .format(url, str(e)))
        return None
    return response
