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


def page(title: str, body: str) -> str:
    return (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
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
        f'<span class="meta">{e(t["one_liner"])}</span></td>'
        f'<td>{t["content"]}</td><td>{t["startup"]}</td><td>{t["final"]}</td></tr>'
        for i, t in enumerate(top, 1))
    return f"<table><tr><th>#</th><th>项目</th><th>传播</th><th>创业</th><th>综合</th></tr>{rows}</table>"


def daily_page(d: dict) -> str:
    p = d["pick"]
    demo = ""
    if d.get("demo_path"):
        demo = (f'<p><a href="../{e(d["demo_path"])}/">👉 打开在线 demo</a></p>'
                f'<a href="../{e(d["demo_path"])}/"><img class="shot" src="../{e(d["demo_path"])}/screenshot.png" alt="demo 截图"></a>')
    body = (f'<p class="meta"><a href="../">← GitHub 雷达</a> · {e(d["date"])}</p>'
            f'<h1>{e(d["headline"] or p["full_name"])}</h1>'
            f'<p class="sub"><a href="{e(p["url"])}">{e(p["full_name"])}</a> · '
            f'<span class="tag">{e(p["category"])}</span><span class="tag">{e(p["license"])}</span>'
            f'⭐ {p["stars"]:,}</p>'
            f'{demo}<div class="card">{md(d.get("summary_md", ""))}</div>'
            f'<h2>今日 Top {len(d["top"])}</h2>{top_table(d["top"])}')
    return page(f'{d["date"]} {p["full_name"]} · GitHub 雷达', body)


def build():
    (config.SITE / "daily").mkdir(parents=True, exist_ok=True)
    days = sorted((config.DATA / "daily").glob("*.json"), reverse=True)
    cards = []
    for f in days:
        d = json.loads(f.read_text())
        (config.SITE / "daily" / f"{d['date']}.html").write_text(daily_page(d))
        p = d["pick"]
        demo = f' · <a href="{e(d["demo_path"])}/">在线 demo</a>' if d.get("demo_path") else ""
        cards.append(
            f'<div class="card"><div class="meta">{e(d["date"])} · <span class="tag">{e(p["category"])}</span></div>'
            f'<h3><a href="daily/{e(d["date"])}.html">{e(d["headline"] or p["full_name"])}</a></h3>'
            f'<div>{e(p["one_liner"])}</div>'
            f'<div class="meta"><a href="{e(p["url"])}">{e(p["full_name"])}</a> · 综合 {p["final"]}{demo}</div></div>')

    deep_file = config.DATA / "deep.json"
    deep = json.loads(deep_file.read_text()) if deep_file.exists() else []
    deep_html = "".join(
        f'<div class="card"><div class="meta">{e(x["date"])}</div>'
        f'<h3><a href="deep/{e(x["slug"])}/">{e(x["full_name"])}</a></h3>'
        f'<div class="meta"><a href="{e(x["url"])}">原仓库</a></div></div>' for x in reversed(deep))

    body = ('<h1>📡 GitHub 雷达</h1><p class="sub">每天从 GitHub 热门项目里挑一个最值得产品化的，'
            '并自动做一个概念 demo。所有 demo 均为非官方概念演示。</p>'
            + (f"<h2>深度 demo</h2>{deep_html}" if deep_html else "")
            + "<h2>每日精选</h2>" + ("".join(cards) or '<p class="meta">还没有数据</p>'))
    (config.SITE / "index.html").write_text(page("GitHub 雷达", body))
    (config.SITE / ".nojekyll").write_text("")
