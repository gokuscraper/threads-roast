from scraper.models import ThreadsUser, ThreadsPost


def parse_user(raw: dict) -> ThreadsUser:
    return ThreadsUser(
        username=raw.get("username", ""),
        full_name=raw.get("full_name", ""),
        avatar=raw.get("avatar", ""),
        biography=raw.get("biography", ""),
        follower_count=int(raw.get("follower_count", 0)),
        following_count=int(raw.get("following_count", 0)),
        post_count=int(raw.get("post_count", 0)),
        verified=bool(raw.get("verified", False)),
        raw=raw,
    )


def parse_posts(raw_list: list[dict]) -> list[ThreadsPost]:
    posts = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        posts.append(ThreadsPost(
            post_id=str(item.get("post_id", "")),
            text=item.get("text", ""),
            created_at=int(item.get("created_at", 0)),
            like_count=int(item.get("like_count", 0)),
            reply_count=int(item.get("reply_count", 0)),
            repost_count=int(item.get("repost_count", 0)),
            image_urls=item.get("image_urls", []),
            raw=item,
        ))
    return posts
