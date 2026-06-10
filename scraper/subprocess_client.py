import json
import subprocess
import sys
from pathlib import Path

from scraper.models import ThreadsUser, ThreadsPost

_WORKER = str(Path(__file__).resolve().parent / "worker.py")


def _parse_user(d: dict) -> ThreadsUser:
    return ThreadsUser(
        username=d.get("username", ""),
        full_name=d.get("full_name", ""),
        avatar=d.get("avatar", ""),
        biography=d.get("biography", ""),
        follower_count=d.get("follower_count", 0),
        following_count=d.get("following_count", 0),
        post_count=d.get("post_count", 0),
        verified=d.get("verified", False),
        raw=d.get("raw", {}),
    )


def _parse_post(d: dict) -> ThreadsPost:
    return ThreadsPost(
        post_id=d.get("post_id", ""),
        text=d.get("text", ""),
        created_at=d.get("created_at", 0),
        like_count=d.get("like_count", 0),
        reply_count=d.get("reply_count", 0),
        repost_count=d.get("repost_count", 0),
        image_urls=d.get("image_urls", []),
        raw=d.get("raw", {}),
    )


def fetch_all(url: str) -> tuple[ThreadsUser, list[ThreadsPost]]:
    """在子进程中运行爬虫，返回 (ThreadsUser, list[ThreadsPost])。"""
    proc = subprocess.Popen(
        [sys.executable, _WORKER],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )

    cmd = json.dumps({"url": url})
    out_b, err_b = proc.communicate(input=cmd.encode("utf-8"), timeout=300)

    out = out_b.decode("utf-8", errors="replace")
    err = err_b.decode("utf-8", errors="replace")

    user = None
    posts = []

    for line in out.strip().split("\n"):
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        t = msg.get("type")
        if t == "error":
            raise RuntimeError(msg.get("message", "Unknown error"))
        elif t == "result":
            user = _parse_user(msg.get("user", {}))
            posts = [_parse_post(v) for v in msg.get("posts", [])]

    if user is None:
        raise RuntimeError("Worker did not return a result")

    return user, posts


def shutdown():
    pass
