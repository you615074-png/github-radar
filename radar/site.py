"""根据 data/ 生成公开网站 site/（首页归档 + 每日页面）。demo 文件由 generate / 深挖脚本直接写入 site/。"""
import html
import json

import markdown

from . import config

CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#78716c;--card:#fff;--line:#e7e5e4;--accent:#0f766e}
@media (prefers-color-scheme:dark){:root{--bg:#0c0a09;--fg:#f5f5f4;--muted:#a8a29e;--card:#1c1917;--line:#292524;--accent:#2dd4bf}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans SC",sans-serif}
main{max-width:860px;margin:0 auto;padding:40px 16px 80px}a{color:var(--accent)}
h1{font-size:28px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 32px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:14px 0}
.card h3{margin:0 0 6px;font-size:18px}.meta{color:var(--muted);font-size:14px}
.tag{display:inline-block;font-size:12px;padding:1px 8px;border:1px solid var(--line);border-radius:99px;margin-right:6px}
.shot{width:100%;border:1px solid var(--line);border-radius:10px;margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top}
"""


CATEGORY_EN = {"AI应用": "AI apps", "AI基础设施": "AI infra", "开发者工具": "Dev tools",
               "效率工具": "Productivity", "数据分析": "Data", "多媒体创作": "Media & creative",
               "安全": "Security", "运维部署": "DevOps", "教育学习": "Education",
               "生活娱乐": "Lifestyle", "其他": "Other"}


def cat(c: str) -> str:
    return CATEGORY_EN.get(c, c)


def title_of(d: dict) -> str:
    return d.get("title_en") or d.get("headline") or d["pick"]["full_name"]


def pitch(x: dict) -> str:
    """英文一句话定位；旧数据只有中文就用中文。"""
    return x.get("tagline_en") or x.get("one_liner_en") or x.get("one_liner", "")


def byline() -> str:
    if not config.X_HANDLE:
        return ""
    h = e(config.X_HANDLE)
    return f' · by <a href="https://x.com/{h}">@{h}</a>'


def page(title: str, body: str) -> str:
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>')


def e(s) -> str:
    return html.escape(str(s or ""))


def md(text: str) -> str:
    """模型写的 Markdown 先转义 HTML 再渲染，防止 README 注入的脚本混进公开页面。"""
    return markdown.markdown(html.escape(text or "", quote=False))


def top_table(top: list[dict]) -> str:
    rows = "".join(
        f'<tr><td>{i}</td><td><a href="{e(t["url"])}">{e(t["full_name"])}</a><br>'
        f'<span class="meta">{e(pitch(t))}</span></td>'
        f'<td>{t["content"]}</td><td>{t["startup"]}</td><td>{t["final"]}</td></tr>'
        for i, t in enumerate(top, 1))
    return f"<table><tr><th>#</th><th>Repo</th><th>Buzz</th><th>Startup</th><th>Overall</th></tr>{rows}</table>"


def daily_page(d: dict) -> str:
    p = d["pick"]
    demo = ""
    if d.get("demo_path"):
        demo = (f'<p><a href="../{e(d["demo_path"])}/">👉 Try the concept demo</a></p>'
                f'<a href="../{e(d["demo_path"])}/"><img class="shot" src="../{e(d["demo_path"])}/screenshot.png" alt="demo screenshot"></a>')
    body = (f'<p class="meta"><a href="../">← GitHub Radar</a> · {e(d["date"])}{byline()}</p>'
            f'<h1>{e(title_of(d))}</h1>'
            f'<p class="sub"><a href="{e(p["url"])}">{e(p["full_name"])}</a> · '
            f'<span class="tag">{e(cat(p["category"]))}</span><span class="tag">{e(p["license"])}</span>'
            f'⭐ {p["stars"]:,}</p>'
            f'{demo}<div class="card">{md(d.get("summary_md", ""))}</div>'
            f'<h2>Today\'s top {len(d["top"])}</h2>{top_table(d["top"])}')
    return page(f'{title_of(d)} · GitHub Radar', body)


def build():
    (config.SITE / "daily").mkdir(parents=True, exist_ok=True)
    days = sorted((config.DATA / "daily").glob("*.json"), reverse=True)
    cards = []
    for f in days:
        d = json.loads(f.read_text())
        (config.SITE / "daily" / f"{d['date']}.html").write_text(daily_page(d))
        p = d["pick"]
        demo = f' · <a href="{e(d["demo_path"])}/">demo</a>' if d.get("demo_path") else ""
        cards.append(
            f'<div class="card"><div class="meta">{e(d["date"])} · <span class="tag">{e(cat(p["category"]))}</span></div>'
            f'<h3><a href="daily/{e(d["date"])}.html">{e(title_of(d))}</a></h3>'
            f'<div>{e(pitch({**p, "tagline_en": d.get("tagline_en")}))}</div>'
            f'<div class="meta"><a href="{e(p["url"])}">{e(p["full_name"])}</a> · score {p["final"]}{demo}</div></div>')

    deep_file = config.DATA / "deep.json"
    deep = json.loads(deep_file.read_text()) if deep_file.exists() else []
    deep_html = "".join(
        f'<div class="card"><div class="meta">{e(x["date"])}</div>'
        f'<h3><a href="deep/{e(x["slug"])}/">{e(x["full_name"])}</a></h3>'
        f'<div class="meta"><a href="{e(x["url"])}">original repo</a></div></div>' for x in reversed(deep))

    follow = (f' Follow along on X: <a href="https://x.com/{e(config.X_HANDLE)}">@{e(config.X_HANDLE)}</a>.'
              if config.X_HANDLE else "")
    body = ('<h1>📡 GitHub Radar</h1><p class="sub">One open-source project a day that could become a product, '
            'picked from trending GitHub repos by an automated pipeline, with a concept demo built for it. '
            f'Demos are unofficial concepts, not the authors\' products.{follow}</p>'
            + (f"<h2>Deep dives</h2>{deep_html}" if deep_html else "")
            + "<h2>Daily picks</h2>" + ("".join(cards) or '<p class="meta">Nothing yet</p>')
            + '<p class="meta">Older entries are in Chinese.</p>')
    (config.SITE / "index.html").write_text(page("GitHub Radar", body))
    (config.SITE / ".nojekyll").write_text("")
