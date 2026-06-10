from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ThreadsUser:
    username: str
    full_name: str
    avatar: str
    biography: str
    follower_count: int
    following_count: int
    post_count: int
    verified: bool = False
    raw: dict = field(default_factory=dict)


@dataclass
class ThreadsPost:
    post_id: str
    text: str
    created_at: int
    like_count: int
    reply_count: int
    repost_count: int
    image_urls: list = field(default_factory=list)
    is_top: bool = False
    raw: dict = field(default_factory=dict)
