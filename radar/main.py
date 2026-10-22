"""每日流程入口：python -m radar.main [--dry-run] [--limit N] [--no-demo]"""
import argparse
import json
import re
import shutil
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from . import collect, config, filters, generate, llm, mailer, score, site


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def public_pick(r: dict) -> dict:
    ev = r["eval"]
    return {
        "full_name": r["full_name"], "url": r["url"], "description": r["description"],
        "license": r["license"], "stars": r["stars"], "daily_rate": r["daily_rate"],
        "category": ev.get("category", ""), "one_liner": ev.get("one_liner", ""),
        "reason": ev.get("reason", ""), **r["score"],
    }


def forget_today(history: dict, today: str):
    """同一天重复运行时，先撤销当天的记录和 demo，避免重复和残留。"""
    history["picks"] = [p for p in history["picks"] if p["date"] != today]
    history["top"] = {n: d for n, d in history["top"].items() if d != today}
    for old in (config.SITE / "demos").glob(f"{today}-*"):
        shutil.rmtree(old, ignore_errors=True)


def run(args) -> None:
    today = datetime.now(config.BJ).date()
    ts = today.isoformat()
    peak_note = ("⚠️ 本次运行处于 DeepSeek 峰时（全价）" if llm.is_peak()
                 else "✅ 本次运行处于 DeepSeek 谷时（半价）")
    print(f"[开始] {ts}，{peak_note}，后端 {config.LLM_BACKEND}")
    if args.skip_if_done and (config.DATA / "daily" / f"{ts}.json").exists():
        print(f"[跳过] {ts} 的日报已经生成过了")
        return

    history = filters.load_history()
    forget_today(history, ts)

    repos = collect.collect(today)
    kept, dropped = filters.rule_filter(repos, history, today)
    filtered = len(kept)
    kept = kept[:config.MAX_FOR_README]
    with ThreadPoolExecutor(8) as ex:
        readmes = list(ex.map(lambda r: collect.fetch_readme(r["full_name"]), kept))
    cands = []
    for r, text in zip(kept, readmes):
        r["readme"] = text
        reason = filters.readme_filter(r)
        if reason:
            dropped[reason] = dropped.get(reason, 0) + 1
        else:
            cands.append(r)
    cands = cands[:args.limit or config.MAX_FOR_SCORING]
    print(f"[过滤] 规则过滤后 {filtered} 个，送去打分 {len(cands)} 个；淘汰：{dropped}")

    ranked = score.score_all(cands, history, today)
    if not ranked:
        raise RuntimeError("没有任何候选完成打分")
    top = ranked[:config.TOP_N]
    for i, t in enumerate(top, 1):
        print(f"  #{i} {t['full_name']} 综合 {t['score']['final']} "
              f"(传播 {t['score']['content']} / 创业 {t['score']['startup']}) {t['eval'].get('one_liner')}")

    # demo：第 1 名做不出来就换第 2 名；都失败则精选第 1 名、不附 demo
    pick, demo_path, attempts, issues = None, None, 0, []
    for cand in ([] if args.no_demo else top[:config.DEMO_CANDIDATES]):
        slug = f"{ts}-{slugify(cand['full_name'])}"
        out_dir = config.SITE / "demos" / slug
        res = generate.build_demo(cand, out_dir)
        attempts += res["attempts"]
        if res["ok"]:
            pick, demo_path = cand, f"demos/{slug}"
            break
        issues = res["issues"]
        shutil.rmtree(out_dir, ignore_errors=True)
    pick = pick or top[0]

    content = generate.write_content(pick, [t for t in top if t is not pick])
    daily = {
        "date": ts, "headline": content["headline"], "summary_md": content["summary_md"],
        "pick": public_pick(pick), "demo_path": demo_path,
        "top": [{"full_name": t["full_name"], "url": t["url"],
                 "one_liner": t["eval"].get("one_liner", ""), "reason": t["eval"].get("reason", ""),
                 **t["score"]} for t in top],
    }
    (config.DATA / "daily").mkdir(parents=True, exist_ok=True)
    (config.DATA / "daily" / f"{ts}.json").write_text(json.dumps(daily, ensure_ascii=False, indent=1))

    history["picks"].append({"date": ts, "full_name": pick["full_name"],
                             "category": pick["eval"].get("category", ""), "final": pick["score"]["final"]})
    cutoff = (today - timedelta(days=30)).isoformat()
    history["top"] = {n: d for n, d in history["top"].items() if d >= cutoff}
    history["top"].update({t["full_name"]: ts for t in top})
    filters.save_history(history)
    site.build()

    private = {"post": content["post"], "notes_md": content["notes_md"],
               "product_idea": pick["eval"].get("product_idea", ""),
               "red_flags": pick["eval"].get("red_flags") or []}
    stats = {"collected": len(repos), "filtered": filtered, "scored": len(ranked),
             "dropped": "，".join(f"{k} {v}" for k, v in dropped.items()) or "无",
             "demo_attempts": attempts, "demo_issues": issues,
             "llm": llm.usage.summary(), "peak": peak_note}
    subject, body = mailer.build_email(daily, private, stats)
    if args.dry_run:
        config.OUT.mkdir(exist_ok=True)
        (config.OUT / f"email-{ts}.html").write_text(body)
        print(f"[邮件] dry-run，未发送，已保存到 out/email-{ts}.html")
    else:
        mailer.send(subject, body)
    print(f"[完成] 精选 {pick['full_name']}，demo：{demo_path or '无'}；{llm.usage.summary()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="不发邮件，邮件内容保存到 out/")
    ap.add_argument("--limit", type=int, default=0, help="最多打分多少个（测试用）")
    ap.add_argument("--no-demo", action="store_true", help="跳过 demo 生成")
    ap.add_argument("--skip-if-done", action="store_true", help="当天已生成过日报就直接退出")
    args = ap.parse_args()
    try:
        run(args)
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        if not args.dry_run and config.GMAIL_APP_PASSWORD:
            try:
                mailer.send("[GitHub 雷达] ❌ 今日运行失败",
                            f"<p>今天的流程出错了，详细日志见 GitHub Actions。</p><pre>{mailer.e(tb[-3000:])}</pre>")
            except Exception as mail_err:
                print(f"[邮件] 错误通知也发送失败：{mail_err}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
