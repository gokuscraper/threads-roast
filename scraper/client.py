import asyncio
import atexit
import json
import re
import sys
import threading
import time

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass

from cloakbrowser import launch

from scraper.config import BASE_URL, HEADLESS, VIEWPORT, PAGE_LOAD_TIMEOUT, USER_AGENT

_browser = None
_context = None
_page = None
_lock = threading.Lock()


def get_browser():
    global _browser
    if _browser is None:
        with _lock:
            if _browser is None:
                _browser = launch(headless=HEADLESS)
                atexit.register(shutdown)
    return _browser


def shutdown():
    global _browser, _context, _page
    if _page:
        try:
            _page.close()
        except Exception:
            pass
        _page = None
    if _context:
        try:
            _context.close()
        except Exception:
            pass
        _context = None
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None


def _get_page():
    global _context, _page
    if _page is None or _page.is_closed():
        browser = get_browser()
        _context = browser.new_context(viewport=VIEWPORT, user_agent=USER_AGENT)
        _page = _context.new_page()
        _page.set_default_timeout(PAGE_LOAD_TIMEOUT)
    return _page


def _parse_og_title(og_title: str) -> tuple[str, str]:
    if not og_title:
        return "", ""
    m = re.search(r'[（(]@([^)）]+)[)）]', og_title)
    username = m.group(1) if m else ""
    full_name = re.sub(r'\s*[（(]@[^)）]+[)）]\s*[•·].*$', '', og_title).strip()
    if not full_name:
        full_name = re.sub(r'\s*[（(]@[^)）]+[)）].*$', '', og_title).strip()
    return full_name, username


def _parse_count(text: str) -> int:
    """解析 '1.2M' → 1200000, '3000万' → 30000000, '291.9 万' → 2919000"""
    text = text.strip().upper()
    # Normalize "291.9 万" → "291.9万" (remove space between number and unit)
    text = re.sub(r'(\d+(?:\.\d+)?)\s+([KMW万亿])', r'\1\2', text)
    m = re.match(r"(\d+(?:\.\d+)?)\s*([KMW万亿]?)", text)
    if not m:
        return 0
    try:
        num = float(m.group(1))
    except ValueError:
        return 0
    unit = m.group(2)
    multipliers = {"K": 1000, "M": 1000000, "W": 10000, "万": 10000, "亿": 100000000}
    return int(num * multipliers.get(unit, 1))


def _parse_og_description(desc: str) -> tuple[str, int, int, int]:
    follower_count = 0
    following_count = 0
    post_count = 0
    biography = desc
    if not desc:
        return biography, follower_count, following_count, post_count

    parts = re.split(r'\s*[•·]\s*', desc, maxsplit=4)
    if len(parts) >= 2:
        m = re.search(r'(\d+(?:\.\d+)?)\s*([KkMm万亿]?)\s*(?:位?粉丝|follower)s?', parts[0])
        if m:
            follower_count = _parse_count(m.group(1) + m.group(2))
        if len(parts) >= 2:
            m = re.search(r'(\d+(?:\.\d+)?)\s*([KkMm万亿]?)\s*(?:条?串文|post)s?', parts[1])
            if m:
                post_count = _parse_count(m.group(1) + m.group(2))
        if len(parts) >= 3:
            biography = " • ".join(parts[2:])
        else:
            biography = parts[0]
    else:
        m = re.search(r'(\d+(?:\.\d+)?)\s*([KkMm万亿]?)\s*follower', parts[0], re.IGNORECASE)
        if m:
            follower_count = _parse_count(m.group(1) + m.group(2))

    biography = re.sub(
        r'[。，]\s*查看\s*@\S+\s*参与的最新对话[\s。，]*$', '', biography
    ).strip()
    return biography.strip(), follower_count, following_count, post_count


def _extract_embedded_posts(page) -> list[dict]:
    """从页面嵌入的 JSON script 中提取帖子。"""
    return page.evaluate("""
() => {
    const results = [];
    const scripts = document.querySelectorAll('script[type="application/json"]');
    for (const script of scripts) {
        const text = script.textContent;
        if (!text.includes('BarcelonaProfileThreadsTabDirectQueryRelayPreloader')) continue;
        try {
            const parsed = JSON.parse(text);
            const outer = parsed && parsed.require;
            if (!outer || !outer[0] || !outer[0][3]) continue;
            const outerBbox = outer[0][3][0];
            if (!outerBbox || !outerBbox.__bbox) continue;
            const inner = outerBbox.__bbox.require;
            if (!inner || !inner[0] || !inner[0][3]) continue;
            const innerBbox = inner[0][3][1];
            if (!innerBbox || !innerBbox.__bbox) continue;
            const resultData = innerBbox.__bbox.result;
            if (!resultData || !resultData.data) continue;
            const mediaData = resultData.data.mediaData;
            if (!mediaData) continue;
            const edges = mediaData.edges || [];

            for (const edge of edges) {
                const node = edge.node || {};
                const threadItems = node.thread_items || [];
                for (const item of threadItems) {
                    const post = item.post || item;
                    if (!post.pk && !post.id) continue;
                    const caption = post.caption || {};
                    const postText = (typeof caption === 'string')
                        ? caption : (caption.text || '');
                    const imageVersions = post.image_versions2 || {};
                    const candidates = imageVersions.candidates || [];
                    const images = candidates.filter(c => c && c.url).map(c => c.url);
                    results.push({
                        post_id: String(post.pk || post.id || ''),
                        text: postText,
                        created_at: post.taken_at || 0,
                        like_count: post.like_count || 0,
                        reply_count: post.reply_count || 0,
                        repost_count: post.repost_count || 0,
                        image_urls: images,
                        is_top: false,
                    });
                }
            }
        } catch(e) {}
    }
    return results;
}
""") or []


def _extract_posts_from_dom(page) -> list[dict]:
    """从页面 DOM 提取帖子。

    策略：找到所有直接包含长文本的 <span>（帖子段落），
    然后向上找到共同的容器 div，合并多段落文本。
    """
    js_code = r"""
() => {
    const results = [];
    const seenKeys = new Set();

    // Find all leaf spans with substantial text (post paragraphs)
    const spans = [];
    const all = document.querySelectorAll('span');
    for (const s of all) {
        const t = s.textContent.trim();
        if (t.length < 40) continue;
        if (s.children.length > 0) continue;
        // Skip UI text
        if (/^(翻译|赞\d*|评论\d*|转发\d*|分享\d*|回复|关注|提及|串文|影音|内容|首页|搜索|创建|通知|返回|更多|登录|注册|切换)$/i.test(t.replace(/\s/g,''))) continue;
        spans.push(s);
    }

    // Group spans by their closest DIV ancestor
    const groups = new Map();
    for (const span of spans) {
        let parent = span.parentElement;
        let container = null;
        for (let i = 0; i < 10 && parent && parent !== document.body; i++) {
            if (parent.tagName === 'DIV' || parent.tagName === 'ARTICLE') {
                container = parent;
                break;  // use closest container, not furthest
            }
            parent = parent.parentElement;
        }
        if (!container) continue;
        if (!groups.has(container)) groups.set(container, []);
        groups.get(container).push(span.textContent.trim());
    }

    // Now for each group, combine the text and create a post entry
    for (const [container, texts] of groups) {
        // Dedup spans within same container
        const unique = [];
        const seen = new Set();
        for (const t of texts) {
            const k = t.slice(0, 60);
            if (seen.has(k)) continue;
            seen.add(k);
            unique.push(t);
        }

        let combined = unique.join('\n');
        // Clean the combined text
        // Remove username/time/emoji prefix patterns
        combined = combined.replace(/^[A-Za-z0-9_\u4e00-\u9fff]+(\d+(小时|分钟|天|秒|刚刚)?)?\u00b7?更多\s*/, '');
        // Remove trailing UI actions
        combined = combined.replace(/\s*(翻译|赞\d*|评论\d*|转发\d*|分享\d*)\s*$/, '');
        // Remove "更多" at start of paragraphs
        combined = combined.replace(/^更多\s*/gm, '');
        // Clean up newlines
        combined = combined.replace(/\n{3,}/g, '\n\n').trim();

        // Skip bio: text has greeting pattern + no links/images structure
        if (/^(Hi|Hello|I.m|\u60a8\u597d)/i.test(combined)) continue;
        // Skip if too short
        if (combined.length < 30) continue;
        // Skip nav/header fragments
        if (/^(关注|提及|串文|回复|影音|内容|返回|更多|登录|注册)/.test(combined)) continue;

        const key = combined.replace(/\s+/g, ' ').slice(0, 100);
        if (seenKeys.has(key)) continue;
        seenKeys.add(key);

        results.push({
            post_id: '',
            text: combined,
            created_at: 0,
            like_count: 0,
            reply_count: 0,
            repost_count: 0,
            image_urls: [],
            is_top: false,
        });
    }
    return results;
}
"""
    return page.evaluate(js_code) or []


def _merge_posts(existing, new_posts, seen_ids):
    """合并新帖子到已有列表，去重。

    如果新帖子的文本是已有帖子文本的子串，则跳过。
    """
    for p in new_posts:
        pid = p.get("post_id", "")
        text = p.get("text", "")
        text_norm = text.replace(" ", "").replace("\n", "")

        if pid:
            if pid in seen_ids:
                continue
            seen_ids.add(pid)

        # Check if text is substring of any existing post
        is_dup = False
        for e in existing:
            e_text_norm = e.get("text", "").replace(" ", "").replace("\n", "")
            if text_norm in e_text_norm or e_text_norm in text_norm:
                is_dup = True
                break
        if is_dup:
            continue

        existing.append(p)


def fetch_data(username: str) -> tuple[dict, list[dict]]:
    """访问 Threads 用户主页，提取资料和帖子。"""
    page = _get_page()
    url = f"{BASE_URL}/@{username}"

    # Intercept GraphQL responses for post data
    graphql_responses = []

    def on_graphql_response(response):
        try:
            if "/api/graphql" in response.url:
                j = response.json()
                if isinstance(j, dict):
                    graphql_responses.append(j)
        except Exception:
            pass

    page.on("response", on_graphql_response)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
    except Exception as e:
        _page = None  # force recreate on next call
        raise

    # Check for 404 or error pages
    page_title = page.title()
    if "Page not found" in page_title or "找不到" in page_title:
        raise RuntimeError(f"用户不存在: @{username}")
    if "Log in" in page_title or "登录" in page_title:
        # Might be a login wall — still try to extract meta tags
        pass

    # Wait for meta tags to populate
    for _ in range(20):
        page.wait_for_timeout(1000)
        og_title = page.evaluate(
            """() => document.querySelector('meta[property="og:title"]')?.content || ''"""
        )
        if og_title:
            break

    # --- Extract user info from meta tags ---
    meta_info = page.evaluate("""() => {
        const getMeta = (name) => {
            const el = document.querySelector('meta[property="' + name + '"], meta[name="' + name + '"]');
            return el ? el.getAttribute('content') : '';
        };
        return { ogTitle: getMeta('og:title'), ogDescription: getMeta('og:description'), ogImage: getMeta('og:image') };
    }""")

    full_name = ""
    extracted_username = username
    if meta_info.get("ogTitle"):
        full_name, extracted_username = _parse_og_title(meta_info["ogTitle"])
    if not extracted_username:
        extracted_username = username
    if not full_name:
        full_name = extracted_username

    biography, follower_count, following_count, post_count = _parse_og_description(
        meta_info.get("ogDescription", "")
    )

    user_data = {
        "username": extracted_username,
        "full_name": full_name,
        "avatar": meta_info.get("ogImage", ""),
        "biography": biography,
        "follower_count": follower_count,
        "following_count": following_count,
        "post_count": post_count,
        "verified": False,
    }

    # --- Extract posts ---
    seen_ids = set()
    posts_data = []

    # 1. Embedded JSON (structured, has IDs)
    json_posts = _extract_embedded_posts(page)
    _merge_posts(posts_data, json_posts, seen_ids)

    # 2. DOM extraction from visible SSR content (catches posts not in embedded JSON)
    dom_posts = _extract_posts_from_dom(page)
    _merge_posts(posts_data, dom_posts, seen_ids)

    # 3. Scroll + wait for more content
    for _ in range(6):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)

        more_json = _extract_embedded_posts(page)
        _merge_posts(posts_data, more_json, seen_ids)

        dom_posts = _extract_posts_from_dom(page)
        _merge_posts(posts_data, dom_posts, seen_ids)

    # 4. Final DOM sweep
    final_dom = _extract_posts_from_dom(page)
    _merge_posts(posts_data, final_dom, seen_ids)

    if not user_data.get("username"):
        raise RuntimeError(f"无法获取 Threads 用户数据: {username}")

    return user_data, posts_data
