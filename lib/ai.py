import json
import os
import time
import traceback
from openai import OpenAI

from scraper.models import ThreadsUser, ThreadsPost
from lib.tweet_utils import format_posts_md

ANALYSIS_PROMPT = """You are the most savage, sharp, hilarious Threads content analyst on the planet. You roast creators so accurately that even the target wants to repost it. Every report should be a screenshot-worthy masterpiece that people feel compelled to share.

Analyze the user's profile JSON and post list, then output STRICT JSON with exactly these fields:

- "about": 2-3 paragraphs. A vivid summary of who this creator is on Threads. What's their vibe? What kind of posts do they write? What's their content style and niche? (Markdown)
- "roast": 1-2 paragraphs. The centerpiece. Be ruthless — call out contradictions between their bio/signature and their posts, cringe patterns, insecure flexes, overused topics. Quote their own posts against them. Make it sting but make it hilarious. This is the part people screenshot. (Markdown)
- "title": A short (2-6 chars), punchy, roast-style nickname that captures this creator's core personality or biggest meme-able trait. NOT a description, NOT a niche label. Use real internet / social media slang and common viral nicknames. NO forced word combinations. It should feel like something a fan or hater would naturally call them in a Threads comment war. (string, plain text, no markdown)
- "emojis": 3-5 emojis that capture their personality, e.g. "🔥💪🚀"
- "strengths": 3-5 items. Each item is {{"title": "Short title (2-5 words)", "subtitle": "1-2 sentence explanation"}}. What are they genuinely good at in content creation?
- "weaknesses": 3-5 items. Same format as strengths. What holds them back or annoys readers? Be blunt.
- "pickupLines": 3 funny/clever pickup lines based on their personality or posting style. Array of strings.
- "loveLife": 1-2 paragraphs. What do their posts and bio reveal about their attitude toward love and relationships? (Markdown)
- "money": 1-2 paragraphs. Their relationship with money, spending, or work ethic visible in their content. (Markdown)
- "health": 1-2 paragraphs. Health, fitness, lifestyle patterns visible in their posts or bio. (Markdown)
- "biggestGoal": 1-2 paragraphs. What seems to be their biggest life goal or driving motivation? (Markdown)
- "colleaguePerspective": 1-2 paragraphs. How would a collaborator or fellow creator describe them? (Markdown)
- "famousPersonComparison": 1 paragraph. What famous person or internet celebrity are they similar to and why? (Markdown)
- "previousLife": 1 paragraph. What might they have been in a previous life? Be creative. (Markdown)
- "animal": 1 paragraph. What animal represents them and why? (Markdown)
- "fiftyDollarThing": 1 paragraph. The weirdest/most characteristic thing they'd spend $50 on. (Markdown)
- "career": 1-2 paragraphs. What career path actually suits them best (not necessarily their current content direction)? (Markdown)
- "lifeSuggestion": 1 paragraph. One actionable, specific life suggestion based on their personality and content style. (Markdown)

Rules:
- All string fields support Markdown (**bold**, *italic*, line breaks)
- Be specific — reference actual post topics, engagement numbers, or patterns from the data
- Keep it personal and unique to this creator, not generic
- Write in the user's language ({lang}). If Chinese → 地道中文, 充满网感, 像评论区神评一样有传播力; If English → natural, witty, meme-aware, like a viral social media comment section
- Output ONLY valid JSON, no other text before or after"""


def _get_key(name: str) -> str:
    key = os.getenv(name, "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get(name, "")
        except Exception:
            pass
    return key


def _call_api(key: str, base_url: str, model: str, lang: str, user_json: str, posts_md: str, max_tokens: int = 4096) -> str:
    client = OpenAI(api_key=key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": ANALYSIS_PROMPT.format(lang=lang)},
            {
                "role": "user",
                "content": f"## Profile JSON\n{user_json}\n\n## Posts\n{posts_md}",
            },
        ],
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    return json.loads(raw.strip())


def analyze_personality(user: ThreadsUser, posts: list[ThreadsPost], lang: str = "zh") -> dict:
    posts_md = format_posts_md(posts)
    user_json = json.dumps({
        "full_name": user.full_name,
        "username": user.username,
        "biography": user.biography,
        "follower_count": user.follower_count,
        "post_count": user.post_count,
    }, ensure_ascii=False)

    # Try OpenCode free channel first (retry 3 times)
    free_key = _get_key("OPENCODE_API_KEY")
    if free_key:
        for attempt in range(3):
            try:
                raw = _call_api(
                    key=free_key,
                    base_url="https://opencode.ai/zen/v1",
                    model="deepseek-v4-flash-free",
                    lang=lang,
                    user_json=user_json,
                    posts_md=posts_md,
                    max_tokens=8192,
                )
                return _parse_json(raw)
            except Exception:
                if attempt < 2:
                    time.sleep(0.5)
                    continue
                traceback.print_exc()

    # Fall back to SiliconFlow
    key = _get_key("SILICON_API_KEY")
    if not key:
        raise RuntimeError(
            "AI 分析结果异常，请稍后重新尝试"
        )

    raw = _call_api(
        key=key,
        base_url="https://api.siliconflow.cn/v1",
        model="deepseek-ai/DeepSeek-V4-Flash",
        lang=lang,
        user_json=user_json,
        posts_md=posts_md,
    )
    return _parse_json(raw)
