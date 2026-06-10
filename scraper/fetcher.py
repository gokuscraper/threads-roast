import re

from scraper.client import fetch_data
from scraper.models import ThreadsUser, ThreadsPost
from scraper.parser import parse_user, parse_posts
from scraper.storage import save_raw


_URL_RE = re.compile(r"https?://[\w.-]*threads\.[\w./?=&%-@]+")


def _extract_url(text: str) -> str:
    m = _URL_RE.search(text)
    if m:
        return m.group(0)
    raise ValueError(f"未找到 Threads 链接: {text[:60]}")


def extract_username(text: str) -> str:
    """从 Threads 用户链接中提取用户名。"""
    url = _extract_url(text.strip())
    # Support threads.net/@user, threads.com/@user, or bare /@user
    m = re.search(r"threads\.(?:net|com)/@([^/?]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"threads\.(?:net|com)/([^/?]+)", url)
    if m:
        return m.group(1)
    raise ValueError(f"无法从链接提取用户名: {url}")


def fetch_all(url: str) -> tuple[ThreadsUser, list[ThreadsPost]]:
    """采集 Threads 用户信息 + 帖子列表。"""
    username = extract_username(url)
    user_raw, posts_raw = fetch_data(username)
    save_raw(username, user_raw, {"posts": posts_raw})
    return parse_user(user_raw), parse_posts(posts_raw)
