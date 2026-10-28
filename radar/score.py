"""DeepSeek 打分 + 综合排序。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from string import Template

from . import config, llm

KEYS = ["topicality", "accessibility", "wow", "pain", "packaging_room",
        "monetization", "license_safety", "demoability"]
# 评分标准有改动时 +1，旧缓存会自动重新打分
RUBRIC_VERSION = 3
ATTACK_TOOL_CAP = 2.0  # 漏洞利用、攻击工具类项目的综合分上限


def prompt(name: str) -> str:
    return (config.PROMPTS / name).read_text()


def score_one(r: dict) -> dict:
    user = Template(prompt("score.user.md")).safe_substitute(
        full_name=r["full_name"], description=r["description"] or "（无）",
        language=r["language"] or "未知", license=r["license"], stars=r["stars"],
        daily_rate=r["daily_rate"], created_at=(r["created_at"] or "")[:10],
        age_days=r["age_days"], topics=", ".join(r["topics"]) or "（无）",
        homepage=r["homepage"] or "（无）", readme=r.get("readme", ""))
    messages = [{"role": "system", "content": prompt("score.system.md")},
                {"role": "user", "content": user}]
    try:
        data = llm.parse_json(llm.chat(messages, config.MODEL_SCORE, json_mode=True, max_tokens=1500))
    except ValueError:  # JSON 偶尔不合法，重试一次
        data = llm.parse_json(llm.chat(messages, config.MODEL_SCORE, json_mode=True, max_tokens=1500))
    s = data.get("scores") or {}
    data["scores"] = {k: max(1, min(10, int(s.get(k, 5) or 5))) for k in KEYS}
    data.setdefault("red_flags", [])
    data["attack_tool"] = data.get("attack_tool") is True
    return data


def aggregate(r: dict, recent_categories: set) -> dict:
    s = r["eval"]["scores"]
    content = (s["topicality"] + s["accessibility"] + s["wow"]) / 3
    startup = (0.30 * s["pain"] + 0.25 * s["packaging_room"]
               + 0.25 * s["monetization"] + 0.20 * s["license_safety"])
    final = 0.30 * content + 0.40 * startup + 0.15 * s["demoability"] + 0.15 * r["heat"]
    penalty = 0.8 if r["eval"].get("category") in recent_categories else 0
    final -= penalty
    if r["eval"].get("attack_tool"):
        final = min(final, ATTACK_TOOL_CAP)
    return {"content": round(content, 2), "startup": round(startup, 2),
            "final": round(final, 2), "category_penalty": penalty}


def pick_top(ranked: list[dict], n: int, per_category: int) -> list[dict]:
    """按综合分取前 n 个，同一类别最多 per_category 个。"""
    top, count = [], {}
    for r in ranked:
        cat = r["eval"].get("category") or "其他"
        if count.get(cat, 0) >= per_category:
            continue
        top.append(r)
        count[cat] = count.get(cat, 0) + 1
        if len(top) == n:
            break
    return top


def score_all(repos: list[dict], history: dict, today: date) -> list[dict]:
    """对候选打分，7 天内打过分的复用缓存。返回按综合分排序的列表。"""
    cache = history["scores"]
    cutoff = (today - timedelta(days=config.SCORE_CACHE_DAYS)).isoformat()
    def fresh(name):
        c = cache.get(name, {})
        return c.get("date", "") >= cutoff and c.get("v") == RUBRIC_VERSION

    todo = [r for r in repos if not fresh(r["full_name"])]
    for r in repos:
        if r not in todo:
            r["eval"] = cache[r["full_name"]]["eval"]

    def run(r):
        try:
            r["eval"] = score_one(r)
            cache[r["full_name"]] = {"date": today.isoformat(), "v": RUBRIC_VERSION, "eval": r["eval"]}
        except Exception as e:
            print(f"[打分] {r['full_name']} 失败：{e}")

    with ThreadPoolExecutor(config.LLM_CONCURRENCY) as ex:
        list(ex.map(run, todo))
    print(f"[打分] 新打分 {len(todo)} 个，复用缓存 {len(repos) - len(todo)} 个")

    # 清掉过期缓存，避免 history.json 无限增长
    for name in [n for n, v in cache.items() if v["date"] < cutoff]:
        del cache[name]

    recent = {p["category"] for p in history["picks"]
              if p["date"] >= (today - timedelta(days=config.RECENT_CATEGORY_DAYS)).isoformat()}
    scored = [r for r in repos if "eval" in r]
    for r in scored:
        r["score"] = aggregate(r, recent)
    return sorted(scored, key=lambda r: r["score"]["final"], reverse=True)
