"""
scraper/worker.py — 在独立进程中运行爬虫，通过 stdin/stdout JSON 通信。

协议：
  主进程 → stdin:  {"url": "..."}
  主进程 ← stdout: {"type": "log",  "message": "..."}      (进度消息)
  主进程 ← stdout: {"type": "result", "user": {...}, "posts": [...]}  (最终结果)
  主进程 ← stdout: {"type": "error", "message": "..."}      (错误)
"""

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.fetcher import fetch_all
from scraper.client import shutdown
from scraper.models import ThreadsUser, ThreadsPost


def _log(msg: str):
    _send({"type": "log", "message": msg})


def _send(data: dict):
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _user_to_dict(u: ThreadsUser) -> dict:
    return {
        "username": u.username,
        "full_name": u.full_name,
        "avatar": u.avatar,
        "biography": u.biography,
        "follower_count": u.follower_count,
        "following_count": u.following_count,
        "post_count": u.post_count,
        "verified": u.verified,
        "raw": u.raw,
    }


def _post_to_dict(p: ThreadsPost) -> dict:
    return {
        "post_id": p.post_id,
        "text": p.text,
        "created_at": p.created_at,
        "like_count": p.like_count,
        "reply_count": p.reply_count,
        "repost_count": p.repost_count,
        "image_urls": p.image_urls,
        "raw": p.raw,
    }


def main():
    line = sys.stdin.readline()
    if not line:
        return

    try:
        cmd = json.loads(line)
        url = cmd.get("url", "")
    except json.JSONDecodeError as e:
        _send({"type": "error", "message": f"Invalid command: {e}"})
        return

    if not url:
        _send({"type": "error", "message": "Missing 'url' field"})
        return

    _log("Launching browser...")
    _log("Scraping Threads profile...")

    try:
        user, posts = fetch_all(url)
    except Exception as e:
        try:
            shutdown()
        except Exception:
            pass
        _send({"type": "error", "message": str(e)})
        return

    _log(f"Done: {len(posts)} posts for {user.full_name or user.username}")

    try:
        shutdown()
    except Exception:
        pass

    _send({
        "type": "result",
        "user": _user_to_dict(user),
        "posts": [_post_to_dict(p) for p in posts],
    })


if __name__ == "__main__":
    main()
