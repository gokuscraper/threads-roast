from scraper.models import ThreadsPost


def format_posts_md(posts: list[ThreadsPost]) -> str:
    parts = []
    for p in posts:
        text_indented = "\n> ".join(p.text.split("\n"))
        parts.append(
            f">{text_indented}\n\n"
            f"likes: {p.like_count}"
        )
    return "\n---\n\n".join(parts)


def summarize_posts(posts: list[ThreadsPost]) -> dict:
    """返回帖子统计摘要。只统计有真实互动数据的帖子（来自 JSON，有 post_id）。"""
    if not posts:
        return {"count": 0}
    real = [p for p in posts if p.post_id]
    likes = [p.like_count for p in real]
    replies = [p.reply_count for p in real]
    reposts = [p.repost_count for p in real]
    return {
        "count": len(posts),
        "avg_likes": round(sum(likes) / len(likes)) if likes else 0,
        "max_likes": max(likes) if likes else 0,
        "avg_replies": round(sum(replies) / len(replies)) if replies else 0,
        "avg_reposts": round(sum(reposts) / len(reposts)) if reposts else 0,
    }
