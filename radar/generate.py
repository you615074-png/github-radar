"""生成日报内容、创业笔记和单文件 demo。"""
import re
from pathlib import Path
from string import Template

from . import check_demo, config, llm
from .score import prompt


def _fields(r: dict) -> dict:
    e = r["eval"]
    return dict(
        full_name=r["full_name"], url=r["url"], description=r["description"] or "（无）",
        license=r["license"], stars=r["stars"], daily_rate=r["daily_rate"],
        category=e.get("category", ""), one_liner=e.get("one_liner", ""),
        target_user=e.get("target_user", ""), product_idea=e.get("product_idea", ""),
        demo_idea=e.get("demo_idea", ""), reason=e.get("reason", ""),
        red_flags="；".join(e.get("red_flags") or []) or "无",
        content_score=r["score"]["content"], startup_score=r["score"]["startup"],
        readme=r.get("readme", "")[:5000],
    )


def write_content(pick: dict, others: list[dict]) -> dict:
    lines = [f"- {o['full_name']}：{o['eval'].get('one_liner', '')}" for o in others]
    user = Template(prompt("content.user.md")).safe_substitute(
        **_fields(pick), others="\n".join(lines) or "（无）")
    text = llm.chat([{"role": "system", "content": prompt("content.system.md")},
                     {"role": "user", "content": user}],
                    config.MODEL_WRITE, json_mode=True, max_tokens=4000)
    data = llm.parse_json(text)
    for k in ("headline", "summary_md", "post", "notes_md"):
        data.setdefault(k, "")
    return data


def extract_html(text: str) -> str:
    m = re.search(r"```html\s*(.*?)```", text, re.S | re.I)
    html = m.group(1) if m else text
    start = html.lower().find("<!doctype")
    end = html.lower().rfind("</html>")
    if start >= 0 and end > start:
        html = html[start:end + len("</html>")]
    return html.strip()


def build_demo(pick: dict, out_dir: Path) -> dict:
    """生成 demo 并自动检查，最多尝试 DEMO_ATTEMPTS 次。返回 {ok, attempts, issues}。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path, shot = out_dir / "index.html", out_dir / "screenshot.png"
    messages = [{"role": "system", "content": prompt("demo.system.md")},
                {"role": "user", "content": Template(prompt("demo.user.md")).safe_substitute(**_fields(pick))}]
    issues = []
    for attempt in range(1, config.DEMO_ATTEMPTS + 1):
        reply = llm.chat(messages, config.MODEL_DEMO, thinking=True, max_tokens=32000)
        html = extract_html(reply)
        html_path.write_text(html)
        issues = check_demo.check(html_path, shot, pick["full_name"])
        print(f"[demo] {pick['full_name']} 第 {attempt} 次：{'通过' if not issues else '；'.join(issues)}")
        if not issues:
            return {"ok": True, "attempts": attempt, "issues": []}
        messages += [{"role": "assistant", "content": f"```html\n{html}\n```"},
                     {"role": "user", "content": Template(prompt("demo.fix.md")).safe_substitute(
                         issues="\n".join(f"- {i}" for i in issues))}]
    return {"ok": False, "attempts": config.DEMO_ATTEMPTS, "issues": issues}
