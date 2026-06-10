import streamlit as st
import json

from i18n import _
from lib.tweet_utils import summarize_posts
from lib.sidebar import render_sidebar

render_sidebar()

raw = st.session_state.get("scraped_user")
if raw is None or isinstance(raw, tuple):
    st.warning(_("warn_no_session"))
    st.page_link("streamlit_app.py", label=_("goto_home"), use_container_width=True)
    st.stop()

user = st.session_state.scraped_user
posts = st.session_state.scraped_videos or []
result = st.session_state.analysis_result

CARD_CONFIG = [
    ("roast",         "\U0001f525", "#e53e3e",  True,  "str"),
    ("strengths",     "\U0001f4aa", "#dd6b20",  False, "list"),
    ("weaknesses",    "\U0001f494", "#3182ce",  False, "list"),
    ("loveLife",      "\U0001f495", "#e53e3e",  False, "str"),
    ("money",         "\U0001f4b0", "#38a169",  False, "str"),
    ("health",        "\U0001f3c3", "#5a67d8",  False, "str"),
    ("colleaguePerspective", "\U0001f465", "#d69e2e", False, "str"),
    ("biggestGoal",   "\U0001f3af", "#805ad5",  False, "str"),
    ("famousPersonComparison", "\u2b50", "#38a169", False, "str"),
    ("pickupLines",   "\U0001f4ac", "#d53f8c",  False, "arr"),
    ("previousLife",  "\U0001f570\ufe0f", "#718096",  False, "str"),
    ("animal",        "\U0001f43e", "#00a3c4",  False, "str"),
    ("fiftyDollarThing", "\U0001f4b8", "#d53f8c", False, "str"),
    ("career",        "\U0001f4bc", "#d69e2e",  False, "str"),
    ("lifeSuggestion","\U0001f4a1", "#319795",  False, "str"),
]


def _md(t):
    import re
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    t = re.sub(r"\n", "<br>", t)
    return t


def _fmt_content(fmt, val):
    if fmt == "str":
        return _md(str(val))
    if fmt == "arr":
        items = val if isinstance(val, list) else []
        return "<ul style='list-style:none;padding:0;margin:0;'>" + \
               "".join(f"<li style='margin-bottom:0.4rem;'>{_md(str(i))}</li>" for i in items) + "</ul>"
    if fmt == "list":
        items = val if isinstance(val, list) else []
        return "<ul style='list-style:none;padding:0;margin:0;'>" + \
               "".join(
                   f"<li style='margin-bottom:0.6rem;'><strong>{_md(str(i.get('title','')))}:</strong> {_md(str(i.get('subtitle','')))}</li>"
                   for i in items
               ) + "</ul>"
    return str(val)


def _card_html(key_label, emoji, color, wide, fmt, data):
    val = data.get(key_label) if isinstance(data, dict) else None
    eng_key = [k for k, *_rest in CARD_CONFIG if _("card_" + k) == key_label]
    eng_key = eng_key[0] if eng_key else key_label
    val = data.get(eng_key) if isinstance(data, dict) else data
    if not val:
        return ""
    border_c = color + "44"
    col_span = "grid-column: 1 / -1;" if wide else ""
    return f"""
    <div style="border:1px solid {border_c};border-radius:16px;padding:1.2rem 1.5rem;
                background:{color}06;height:100%;{col_span}">
        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.6rem;">
            <span style="font-size:1.3rem;">{emoji}</span>
            <span style="font-weight:600;font-size:1rem;color:{color};">{key_label}</span>
        </div>
        <div style="border-bottom:1px solid #e5e7eb;margin-bottom:0.8rem;"></div>
        <div style="color:#374151;font-size:0.95rem;line-height:1.7;">{_fmt_content(fmt, val)}</div>
    </div>"""


def _render_card(key_label, emoji, color, wide, fmt, data):
    html = _card_html(key_label, emoji, color, wide, fmt, data)
    if html:
        st.markdown(html, unsafe_allow_html=True)


def _estimate_account_value(user, summary: dict, lang: str) -> str:
    base = user.follower_count * 0.23 + summary.get("avg_likes", 0) * 0.3
    symbol = "¥" if lang == "zh" else "$"
    return f"{symbol}{base:,.0f}"


def _build_report_html(result: dict, user, summary: dict, posts: list, lang: str = "zh") -> str:
    display_name = user.full_name or user.username
    avatar_url = user.avatar

    bio = (user.biography[:200] + "...") if len(user.biography) > 200 else user.biography
    stats_row = f"""<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:1rem;margin-top:1rem;
        padding:1rem;background:#f9fafb;border-radius:12px;text-align:center;">
        <div><div style="font-size:1.3rem;font-weight:700;">{user.follower_count:,}</div><div style="font-size:0.8rem;color:#9ca3af;">{_("label_followers")}</div></div>
        <div><div style="font-size:1.3rem;font-weight:700;">{user.post_count:,}</div><div style="font-size:0.8rem;color:#9ca3af;">{_("label_posts")}</div></div>
    </div>"""
    post_stats_html = ""
    if summary["count"]:
        post_stats_html = f"""<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.8rem;margin-top:0.8rem;
            padding:1rem;background:#f9fafb;border-radius:12px;text-align:center;">
            <div><div style="font-size:1.1rem;font-weight:600;">{summary["count"]}</div><div style="font-size:0.8rem;color:#9ca3af;">{_("stat_count")}</div></div>
            <div><div style="font-size:1.1rem;font-weight:600;">{summary["avg_likes"]:,}</div><div style="font-size:0.8rem;color:#9ca3af;">{_("stat_avg_likes")}</div></div>
            <div><div style="font-size:1.1rem;font-weight:600;">{summary["max_likes"]:,}</div><div style="font-size:0.8rem;color:#9ca3af;">{_("stat_max_likes")}</div></div>
        </div>"""

    nickname = result.get("title", "")
    emojis = result.get("emojis", "")
    about = result.get("about", "")
    about_html = _md(about) if about else ""
    post_heading = f"""<div style="font-size:1.1rem;font-weight:600;margin-top:1.5rem;color:#1f2937;">\U0001f4ca {_("post_stats")}</div>""" if post_stats_html else ""
    account_value = _estimate_account_value(user, summary, lang)
    account_value_html = f"""<div style="margin:1.2rem auto;padding:0.8rem 1.5rem;background:linear-gradient(135deg,#1e293b,#334155);border-radius:12px;text-align:center;color:#fff;font-size:1.1rem;max-width:450px;">
        {_("account_value")}：<span style="font-weight:700;font-size:1.4rem;color:#fbbf24;">{account_value}</span>
    </div>"""
    footer_text = "Powered by Threads-Roast (Threads照妖镜) | threads7.streamlit.app"
    nickname_html = f'<div style="text-align:center;font-size:1.6rem;font-weight:800;margin-bottom:1rem;color:#e53e3e;">{nickname}</div>' if nickname else ""
    section1 = f"""
    <div id="report-1" style="padding:20px;">
        {nickname_html or f'<div style="text-align:center;font-size:1.6rem;font-weight:700;margin-bottom:1.2rem;color:#1f2937;">{_("report_title")}</div>'}
        <div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.5rem;">
            <img src="{avatar_url}" style="width:56px;height:56px;border-radius:50%;" onerror="this.style.display='none'">
            <div>
                <div style="font-size:1.4rem;font-weight:700;">{display_name}</div>
                <div style="color:#9ca3af;">@{user.username}</div>
            </div>
        </div>
        <div style="margin:0.5rem 0;color:#4b5563;">{bio}</div>
        {stats_row}
        {post_heading}
        {post_stats_html}
        {account_value_html}
        <div style="text-align:center;margin-top:1.5rem;">
            <div style="font-size:2.5rem;letter-spacing:0.3rem;">{emojis}</div>
            <div style="max-width:700px;margin:1rem auto;color:#4b5563;font-size:1rem;line-height:1.7;">{about_html}</div>
        </div>
        <div class="report-footer">{footer_text}</div>
    </div>"""

    card_groups = [CARD_CONFIG[:3], CARD_CONFIG[3:9], CARD_CONFIG[9:]]
    sections_html = []
    sec_ids = ["report-2", "report-3", "report-4"]
    for gi, group in enumerate(card_groups):
        cards_html = ""
        for ci, (key, emoji, color, wide, fmt) in enumerate(group):
            val = result.get(key)
            if not val:
                continue
            border_c = color + "44"
            col_span = "grid-column: 1 / -1;" if wide else ""
            content = _fmt_content(fmt, val)
            card_fmt = _("card_" + key)
            cards_html += (
                '<div class="card" style="border:1px solid ' + border_c
                + ';border-radius:16px;padding:1.2rem 1.5rem;background:' + color
                + '08;' + col_span + '">'
                '<div class="card-header">'
                '<span class="card-emoji">' + emoji + '</span>'
                '<span class="card-label" style="color:' + color + ';">' + card_fmt + '</span>'
                '</div>'
                '<div class="card-divider"></div>'
                '<div class="card-body">' + content + '</div>'
                '</div>'
            )
        sec_id = sec_ids[gi]
        footer_html = f'<div class="report-footer">{footer_text}</div>'
        sections_html.append(f"""
    <div id="{sec_id}" style="padding:20px;">
        <div class="card-grid">{cards_html}</div>
        {footer_html}
    </div>""")

    buttons = f"""
    <div class="toolbar">
        <button class="btn-download" onclick="capture('report-1','{user.username}_1_profile')">{_("btn_section1")}</button>
        <button class="btn-download" onclick="capture('report-2','{user.username}_2_analysis_a')">{_("btn_section2")}</button>
        <button class="btn-download" onclick="capture('report-3','{user.username}_3_analysis_b')">{_("btn_section3")}</button>
        <button class="btn-download" onclick="capture('report-4','{user.username}_4_analysis_c')">{_("btn_section4")}</button>
        <button class="btn-download btn-all" onclick="downloadAll()">{_("btn_download_all")}</button>
    </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#fafafa; }}
.card-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(380px,1fr)); gap:1.5rem; max-width:900px; margin:0 auto; }}
.card {{ }}
.card-header {{ display:flex; align-items:center; gap:0.5rem; margin-bottom:0.6rem; }}
.card-emoji {{ font-size:1.3rem; }}
.card-label {{ font-weight:600; font-size:1rem; }}
.card-divider {{ border-bottom:1px solid #e5e7eb; margin-bottom:0.8rem; }}
.card-body {{ color:#374151; font-size:0.95rem; line-height:1.7; }}
.card-body ul {{ list-style:none; padding:0; margin:0; }}
.card-body li {{ margin-bottom:0.4rem; }}
.card-body strong {{ font-weight:600; }}
.report-footer {{ text-align:center; margin-top:2rem; padding-top:1rem; border-top:1px solid #e5e7eb; color:#9ca3af; font-size:0.85rem; }}
.toolbar {{ text-align:center; padding:20px; display:flex; flex-wrap:wrap; justify-content:center; gap:0.5rem; }}
.btn-download {{ background:#dc2626; color:#fff; border:none; border-radius:8px; padding:0.6rem 1.2rem; font-size:0.9rem; font-weight:600; cursor:pointer; }}
.btn-download:hover {{ background:#ef4444; }}
.btn-all {{ background:#1f2937; }}
.btn-all:hover {{ background:#374151; }}
</style>
</head>
<body>
{section1}
{sections_html[0]}
{sections_html[1]}
{sections_html[2]}
{buttons}
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script>
var username = '{user.username}';
var dlQueue = [];
function dlAdd(fn) {{ dlQueue.push(fn); if (dlQueue.length===1) dlNext(); }}
function dlNext() {{
    if (!dlQueue.length) return;
    dlQueue[0](function() {{ dlQueue.shift(); setTimeout(dlNext, 800); }});
}}
function capture(id, idx, label) {{
    dlAdd(function(done) {{
        html2canvas(document.getElementById(id), {{ scale:2, useCORS:true }})
            .then(function(canvas) {{
                var link = document.createElement('a');
                link.download = username + '_' + idx + '_' + label + '.png';
                link.href = canvas.toDataURL('image/png');
                link.click();
                done();
            }})
            .catch(function(err) {{
                document.getElementById('err').textContent = '\u622a\u56fe\u5931\u8d25: ' + err.message;
                done();
            }});
    }});
}}
function dlAvatar(idx) {{
    dlAdd(function(done) {{
        fetch('{avatar_url}').then(function(r){{return r.blob()}}).then(function(b){{
            var a=document.createElement('a');
            a.download=username+'_'+idx+'_avatar.png';
            a.href=URL.createObjectURL(b);
            a.click();
            done();
        }}).catch(function(){{done();}});
    }});
}}
function downloadAll() {{
    capture('report-4', 5, 'analysis_c');
    capture('report-3', 4, 'analysis_b');
    capture('report-2', 3, 'analysis_a');
    capture('report-1', 2, 'profile');
    dlAvatar(1);
}}
</script>
<p id="err" style="color:red;text-align:center;padding:0 20px 20px;"></p>
</body>
</html>"""


def _on_analyze():
    from lib.ai import analyze_personality
    from scraper import shutdown

    with st.spinner(_("spinner_ai")):
        shutdown()
        try:
            r = analyze_personality(user, posts, lang=st.session_state.get("lang", "zh"))
            st.session_state.analysis_result = r
            st.rerun()
        except Exception as e:
            st.error(f"{_('ai_error')}: {e}")


# ====== PAGE LAYOUT ======

st.markdown(
    f"<h1 style='margin-bottom:0;'>{_('analysis_title')}</h1>",
    unsafe_allow_html=True,
)
st.caption(f"@{user.username}")

# Profile card
with st.container():
    cols = st.columns([1, 4])
    with cols[0]:
        if user.avatar:
            st.image(user.avatar, width=96)
    with cols[1]:
        display_name = user.full_name or user.username
        sig = (user.biography[:150] + "...") if len(user.biography) > 150 else user.biography
        st.markdown(f"**<span style='font-size:1.3rem'>{display_name}</span>**", unsafe_allow_html=True)
        st.caption(f"@{user.username}")
        st.markdown(sig)

    s1, s2 = st.columns(2)
    s1.metric(_("label_followers"), f"{user.follower_count:,}")
    s2.metric(_("label_posts"), f"{user.post_count:,}")

st.divider()

# Post stats
summary = summarize_posts(posts)
if summary["count"]:
    st.markdown(f"### 📊 {_('post_stats')}")
    r1, r2, r3 = st.columns(3)
    r1.metric(_("stat_count"), summary["count"])
    r2.metric(_("stat_avg_likes"), f"{summary['avg_likes']:,}")
    r3.metric(_("stat_max_likes"), f"{summary['max_likes']:,}")
    st.divider()

# AI Analysis
st.markdown(f"### ✨ {_('ai_section_title')}")

if result:
    report_html = _build_report_html(result, user, summary, posts, lang=st.session_state.get("lang", "zh"))
    st.components.v1.html(report_html, height=1800, scrolling=True)

    st.divider()
    if st.button(_("btn_rerun_ai"), use_container_width=True):
        st.session_state.analysis_result = None
        st.rerun()
else:
    st.info(_("ai_hint"))
    if st.button(_("btn_run_ai"), type="primary", use_container_width=True):
        _on_analyze()

# Footer nav
st.divider()
st.page_link("streamlit_app.py", label=_("goto_home"), use_container_width=True)
