"""demo 自动检查：静态规则 + 无头浏览器实测。返回问题列表，空列表表示通过。"""
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_HOSTS = {"cdn.tailwindcss.com", "cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"}
FORBIDDEN = {
    r"\bfetch\s*\(": "使用了 fetch 网络请求",
    r"XMLHttpRequest": "使用了 XMLHttpRequest",
    r"new\s+WebSocket": "使用了 WebSocket",
    r"EventSource": "使用了 EventSource",
    r"sendBeacon": "使用了 sendBeacon",
    r"\beval\s*\(": "使用了 eval",
    r"new\s+Function\s*\(": "使用了 new Function",
    r"document\.cookie": "读写了 cookie",
}


def static_check(html: str, repo: str) -> list[str]:
    issues = []
    low = html.lower()
    if not low.startswith("<!doctype html") or not low.rstrip().endswith("</html>"):
        issues.append("不是完整的 HTML 文件（应以 <!DOCTYPE html> 开头、</html> 结尾）")
    if len(html) < 1500:
        issues.append("页面内容过少")
    for pat, msg in FORBIDDEN.items():
        if re.search(pat, html):
            issues.append(msg)
    for src in re.findall(r"""<(?:script|link|img|iframe)[^>]+(?:src|href)=["'](https?:[^"']+)""", html, re.I):
        host = urlparse(src).hostname or ""
        if host not in ALLOWED_HOSTS:
            issues.append(f"引用了不允许的外部资源：{host}")
    if repo.lower() not in low:
        issues.append(f"页面底部缺少对原项目 {repo} 的署名和链接")
    return issues


def browser_check(path: Path, screenshot: Path) -> list[str]:
    from playwright.sync_api import sync_playwright

    issues, errors, blocked = [], [], set()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 860})

        def route(r):
            u = urlparse(r.request.url)
            if u.scheme in ("file", "data", "blob", "about") or u.hostname in ALLOWED_HOSTS:
                r.continue_()
            else:
                blocked.add(u.hostname)
                r.abort()

        page.route("**/*", route)
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text[:200]))
        page.goto(path.resolve().as_uri(), wait_until="load", timeout=30000)
        page.wait_for_timeout(1500)

        text_len = len(page.inner_text("body").strip())
        if text_len < 200:
            issues.append(f"页面渲染后几乎没有文字（{text_len} 字）")
        buttons = page.locator("button:visible")
        inputs = page.locator("input:visible, textarea:visible, select:visible")
        if buttons.count() + inputs.count() == 0:
            issues.append("页面上没有任何可交互的按钮或输入框")
        page.screenshot(path=str(screenshot))

        # 依次点几个按钮，看会不会报错
        for i in range(min(buttons.count(), 6)):
            try:
                buttons.nth(i).click(timeout=2000)
                page.wait_for_timeout(400)
            except Exception:
                pass
        browser.close()

    if errors:
        issues.append("运行时报错：" + " | ".join(dict.fromkeys(errors))[:600])
    if blocked:
        issues.append("尝试访问不允许的地址：" + ", ".join(sorted(h or "?" for h in blocked)))
    return issues


def check(path: Path, screenshot: Path, repo: str) -> list[str]:
    issues = static_check(path.read_text(errors="ignore"), repo)
    try:
        issues += browser_check(path, screenshot)
    except Exception as e:
        issues.append(f"浏览器检查失败：{str(e)[:200]}")
    return issues


if __name__ == "__main__":  # 深挖脚本调用：python -m radar.check_demo <index.html> <owner/repo>
    target = Path(sys.argv[1])
    found = check(target, target.parent / "screenshot.png", sys.argv[2])
    print("\n".join(found) or "通过")
    sys.exit(1 if found else 0)
