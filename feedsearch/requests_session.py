import requests
import functools


def get_user_agent():
    """
    Return User Agent string
    """
    return "FeedSearch (https://github.com/DBeath/feedsearch)"


class RequestsSession:
    """
    Set default User-Agent and max_redirects for a Requests session
    """
    def __init__(self,
                 user_agent=None,
                 max_redirects=30):
        self.user_agent = user_agent or get_user_agent()
        self.max_redirects = max_redirects or 30

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self.session.max_redirects = self.max_redirects

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()


def requests_session(*optional_args, **optional_kwargs):
    """
    Wraps a requests session around a function.
    Optional keyword arguments are passed to wrapped function.

    :param optional_kwargs: Optional keyword arguments
    :return: decorator function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            kwargs.update(optional_kwargs)
            with RequestsSession(kwargs.get('user_agent'),
                                 kwargs.get('max_redirects')) as session:
                kwargs['session'] = session
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator
