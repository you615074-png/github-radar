"""规则过滤（不调用大模型）和历史记录。"""
import json
import re
from datetime import date, timedelta

from . import config

NAME_BAD = re.compile(
    r"(^|[-_.])(awesome|tutorials?|course|interviews?|roadmap|cheat-?sheets?|leetcode|"
    r"system-design-primer|free-programming|public-apis|books?|resources?)([-_.]|$)", re.I)
DESC_BAD = re.compile(
    r"awesome list|curated list|a list of|collection of (resources|links|prompts)|tutorial|"
    r"interview (questions|prep)|learning (path|roadmap)|cheat ?sheet|study notes|course materials|"
    r"面试|教程|学习路线|学习笔记|资源合集|资料汇总|题库", re.I)

HISTORY = config.DATA / "history.json"


def load_history() -> dict:
    if HISTORY.exists():
        return json.loads(HISTORY.read_text())
    return {"picks": [], "top": {}, "scores": {}}


def save_history(h: dict):
    HISTORY.write_text(json.dumps(h, ensure_ascii=False, indent=1))


def picked_names(h: dict) -> set:
    return {p["full_name"] for p in h["picks"]}


def recent_top(h: dict, today: date) -> set:
    cutoff = (today - timedelta(days=config.TOP_REPEAT_DAYS)).isoformat()
    return {n for n, d in h["top"].items() if d >= cutoff and d != today.isoformat()}


def rule_filter(repos: list[dict], h: dict, today: date) -> tuple[list[dict], dict]:
    picked, top = picked_names(h), recent_top(h, today)
    kept, dropped = [], {}

    def drop(reason):
        dropped[reason] = dropped.get(reason, 0) + 1

    for r in repos:
        name = r["full_name"].split("/")[1]
        if r["fork"] or r["archived"]:
            drop("fork 或已归档")
        elif r["full_name"] in picked:
            drop("以前已精选")
        elif r["full_name"] in top:
            drop("近 7 天已上榜")
        elif not r["license"]:
            drop("无 License")
        elif NAME_BAD.search(name) or DESC_BAD.search(r["description"]):
            drop("列表 / 教程类")
        else:
            kept.append(r)
    return kept, dropped


def readme_filter(r: dict) -> str | None:
    """返回淘汰原因，None 表示通过。"""
    text = r.get("readme", "")
    if len(text) < 400:
        return "README 太短"
    links = len(re.findall(r"\]\(http", text))
    if links > 60 and links * 120 > len(text):
        return "README 像资源列表"
    return None
