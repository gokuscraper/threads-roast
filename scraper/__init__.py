from scraper.subprocess_client import fetch_all, shutdown
from scraper.models import ThreadsUser, ThreadsPost

__all__ = [
    "fetch_all",
    "ThreadsUser",
    "ThreadsPost",
    "shutdown",
]


def close_browser():
    shutdown()
