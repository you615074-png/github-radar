"""采集：GitHub Trending + Search API，记录 star 快照，计算热度。"""
import base64
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from . import config

UA = "Mozilla/5.0 (github-radar; +https://github.com/you615074-png/github-radar)"
API = requests.Session()
API.headers.update({"Accept": "application/vnd.github+json", "User-Agent": UA,
                    "X-GitHub-Api-Version": "2022-11-28"})
if config.GITHUB_TOKEN:
    API.headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"


def gh(path, **params):
    for attempt in range(4):
        r = API.get(f"https://api.github.com{path}", params=params, timeout=30)
        if r.ok:
            return r.json()
        if r.status_code == 404:
            return None
        if r.status_code in (403, 429):
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 30))
            time.sleep(min(max(reset - time.time(), 5), 120))
        else:
            time.sleep(3 * (attempt + 1))
    r.raise_for_status()


def slim(item: dict) -> dict:
    lic = (item.get("license") or {}).get("spdx_id")
    return {
        "full_name": item["full_name"],
        "url": item["html_url"],
        "description": (item.get("description") or "").strip(),
        "language": item.get("language"),
        "stars": item.get("stargazers_count", 0),
        "forks": item.get("forks_count", 0),
        "license": lic,
        "fork": item.get("fork", False),
        "archived": item.get("archived", False),
        "topics": item.get("topics") or [],
        "created_at": item.get("created_at"),
        "pushed_at": item.get("pushed_at"),
        "homepage": item.get("homepage") or "",
        "open_issues": item.get("open_issues_count", 0),
    }


def trending(since: str) -> list[dict]:
    r = requests.get(f"https://github.com/trending?since={since}", headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for art in soup.select("article.Box-row"):
        a = art.select_one("h2 a[href]")
        if not a:
            continue
        full = a["href"].strip("/")
        gained = art.find(string=re.compile(r"stars? (today|this week|this month)"))
        n = int(re.sub(r"\D", "", gained)) if gained else 0
        out.append({"full_name": full, "gained": n})
    return out


def search_new(days: int, min_stars: int) -> list[dict]:
    since = (date.today() - timedelta(days=days)).isoformat()
    q = f"created:>={since} stars:>={min_stars} fork:false archived:false"
    res = gh("/search/repositories", q=q, sort="stars", order="desc", per_page=100) or {}
    return [slim(i) for i in res.get("items", [])]


def load_snapshot(day: date) -> dict:
    p = config.DATA / "stars" / f"{day.isoformat()}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def nearest_snapshot(today: date, days_back: int, window: int = 2) -> tuple[dict, int]:
    """找 days_back 天前（±window）的快照，返回 (快照, 实际相隔天数)。"""
    for d in [days_back] + [x for k in range(1, window + 1) for x in (days_back + k, days_back - k)]:
        if d <= 0:
            continue
        snap = load_snapshot(today - timedelta(days=d))
        if snap:
            return snap, d
    return {}, 0


def collect(today: date) -> list[dict]:
    t0 = time.time()
    daily, weekly = trending("daily"), trending("weekly")
    searched = search_new(7, 50) + search_new(30, 300)
    repos = {r["full_name"]: r for r in searched}
    trend_day = {t["full_name"]: t["gained"] for t in daily}
    trend_week = {t["full_name"]: t["gained"] for t in weekly}

    missing = [n for n in {*trend_day, *trend_week} if n not in repos]
    with ThreadPoolExecutor(8) as ex:
        for item in ex.map(lambda n: gh(f"/repos/{n}"), missing):
            if item:
                repos[item["full_name"]] = slim(item)

    snap_1, gap_1 = nearest_snapshot(today, 1, 0)
    snap_7, gap_7 = nearest_snapshot(today, 7)
    now = datetime.now(timezone.utc)
    for name, r in repos.items():
        age = max((now - datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))).days, 1)
        rates = {"lifetime": r["stars"] / age if age <= 60 else 0}
        if name in trend_day:
            rates["trending_today"] = trend_day[name]
        if name in trend_week:
            rates["trending_week"] = trend_week[name] / 7
        if name in snap_1:
            rates["snapshot_1d"] = (r["stars"] - snap_1[name]) / gap_1
        if name in snap_7:
            rates["snapshot_7d"] = (r["stars"] - snap_7[name]) / gap_7
        r["daily_rate"] = round(max(rates.values()), 1)
        r["rate_source"] = max(rates, key=rates.get)
        r["age_days"] = age
        r["on_trending"] = name in trend_day or name in trend_week
        # 热度 0-10：日增约 3000 star 为满分
        r["heat"] = round(min(10, 10 * math.log10(1 + max(r["daily_rate"], 0)) / 3.5), 2)

    snap_dir = config.DATA / "stars"
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / f"{today.isoformat()}.json").write_text(
        json.dumps({n: r["stars"] for n, r in sorted(repos.items())}, ensure_ascii=False, indent=0))
    print(f"[采集] trending 日榜 {len(daily)} / 周榜 {len(weekly)}，搜索 {len(searched)}，"
          f"去重后 {len(repos)} 个，用时 {time.time() - t0:.0f}s")
    return sorted(repos.values(), key=lambda r: r["daily_rate"], reverse=True)


def fetch_readme(full_name: str, limit: int = 6000) -> str:
    res = gh(f"/repos/{full_name}/readme")
    if not res or "content" not in res:
        return ""
    text = base64.b64decode(res["content"]).decode("utf-8", errors="ignore")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)", "", text)  # 徽章
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)          # 图片
    text = re.sub(r"<img[^>]*>|<picture.*?</picture>", "", text, flags=re.S | re.I)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit]
