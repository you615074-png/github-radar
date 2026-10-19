"""组装日报邮件并通过 Gmail SMTP 发送。"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from . import config
from .site import e, md

STYLE = ("font-family:-apple-system,'PingFang SC',sans-serif;line-height:1.7;color:#1c1917;"
         "max-width:720px;margin:0 auto")
BOX = "border:1px solid #e7e5e4;border-radius:10px;padding:14px 18px;margin:14px 0"


def build_email(d: dict, private: dict, stats: dict) -> tuple[str, str]:
    p = d["pick"]
    subject = f"[GitHub 雷达] {d['date'][5:]} 今日精选：{d['headline'] or p['full_name']}"
    if d.get("demo_path"):
        demo_url = f"{config.SITE_URL}/{d['demo_path']}/"
        demo = f'<p>🌐 <b>在线 demo：</b><a href="{demo_url}">{demo_url}</a>（网站部署约需 1-2 分钟）</p>'
    elif stats.get("demo_issues"):
        demo = f'<p>⚠️ 今天的 demo 没有通过自动检查：{e("；".join(stats["demo_issues"]))}</p>'
    else:
        demo = "<p>今天没有生成 demo。</p>"
    top = "".join(
        f'<li><a href="{e(t["url"])}">{e(t["full_name"])}</a> — {e(t["one_liner"])}'
        f'<br><small>传播 {t["content"]} · 创业 {t["startup"]} · 综合 {t["final"]} · {e(t["reason"])}</small></li>'
        for t in d["top"])
    flags = "；".join(private["red_flags"]) or "无"
    body = f"""<div style="{STYLE}">
<h2 style="margin-bottom:4px">📡 {e(d['headline'] or p['full_name'])}</h2>
<p style="color:#78716c;margin-top:0"><a href="{e(p['url'])}">{e(p['full_name'])}</a> · {e(p['category'])} ·
{e(p['license'])} · ⭐ {p['stars']:,}（每天约 +{p['daily_rate']}）</p>
<p><b>{e(p['one_liner'])}</b></p>
{demo}
<div style="{BOX}">{md(d['summary_md'])}</div>
<h3>今日 Top {len(d['top'])}</h3><ol>{top}</ol>
<h3>✍️ 社交媒体文案草稿</h3>
<div style="{BOX};white-space:pre-wrap">{e(private['post'])}</div>
<h3>🔒 创业笔记（只在邮件里，不公开）</h3>
<div style="{BOX};background:#fafaf9">
<p><b>产品设想：</b>{e(private['product_idea'])}<br><b>风险点：</b>{e(flags)}</p>
{md(private['notes_md'])}</div>
<h3>运行情况</h3>
<p style="color:#78716c;font-size:13px">候选 {stats['collected']} 个 → 规则过滤后 {stats['filtered']} 个 →
打分 {stats['scored']} 个。淘汰原因：{e(stats['dropped'])}<br>
demo 尝试 {stats.get('demo_attempts', 0)} 次 · 大模型：{e(stats['llm'])} · {e(stats['peak'])}<br>
<a href="{config.SITE_URL}/">归档网站</a></p></div>"""
    return subject, body


def send(subject: str, html_body: str):
    if not (config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD):
        raise RuntimeError("缺少 GMAIL_ADDRESS 或 GMAIL_APP_PASSWORD")
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, f"GitHub 雷达 <{config.GMAIL_ADDRESS}>", config.MAIL_TO
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=60) as s:
        s.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        s.sendmail(config.GMAIL_ADDRESS, [config.MAIL_TO], msg.as_string())
    print(f"[邮件] 已发送：{subject}")
