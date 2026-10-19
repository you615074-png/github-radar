"""全局配置。敏感信息只从环境变量读取（GitHub Actions 里来自 Secrets）。"""
import os
from datetime import timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
PROMPTS = ROOT / "prompts"
OUT = ROOT / "out"  # 本地调试输出，不进仓库

BJ = timezone(timedelta(hours=8))

# ---- 大模型 ----
# api：直接调用 OpenAI 兼容接口（默认 DeepSeek）；dsh：本地调试时借用 dsh headless
LLM_BACKEND = os.getenv("LLM_BACKEND", "api")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
MODEL_SCORE = os.getenv("MODEL_SCORE", "deepseek-flash")
MODEL_WRITE = os.getenv("MODEL_WRITE", "deepseek-flash")
MODEL_DEMO = os.getenv("MODEL_DEMO", "deepseek-flash")
LLM_CONCURRENCY = int(os.getenv("LLM_CONCURRENCY", "8"))

# DeepSeek 谷时价（美元 / 百万 token），只用于邮件里的成本估算；峰时 ×2
# 来源：https://api-docs.deepseek.com/quick_start/pricing（2026-10 核对）
PRICE = {"hit": 0.003, "miss": 0.15, "out": 0.6}
# 峰时：周一到周五 UTC 01:00-04:00、06:00-10:00（北京 09-12 点、14-18 点）
PEAK_HOURS_UTC = [(1, 4), (6, 10)]

# ---- GitHub / 网站 / 邮件 ----
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
SITE_URL = os.getenv("SITE_URL", "https://you615074-png.github.io/github-radar").rstrip("/")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")
MAIL_TO = os.getenv("MAIL_TO") or GMAIL_ADDRESS

# ---- 漏斗参数 ----
MAX_FOR_README = 80      # 规则过滤后按热度取前 N 个去读 README
MAX_FOR_SCORING = 40     # 最多送去打分的数量
SCORE_CACHE_DAYS = 7     # 7 天内打过分的直接复用，省钱
TOP_N = 5
TOP_REPEAT_DAYS = 7      # 7 天内上过 Top 5 的不再进 Top 5
RECENT_CATEGORY_DAYS = 3 # 与最近 3 天精选同类别会被扣分
DEMO_ATTEMPTS = 3        # demo 生成 + 修复的总次数
DEMO_CANDIDATES = 2      # 第 1 名做不出来就换第 2 名
