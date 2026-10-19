#!/usr/bin/env bash
# 深挖：用 codex（ChatGPT 订阅额度）把一个项目做成完整的 demo 并发布到网站。
# 用法：./deep_dive.sh https://github.com/owner/repo
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "请先按 README 的「本机准备」创建 .venv"; exit 1; }
[ $# -ge 1 ] || { echo "用法：./deep_dive.sh https://github.com/owner/repo"; exit 1; }

REPO="$(echo "$1" | sed -E 's#^(https?://)?github\.com/##; s#\.git$##; s#/+$##' | cut -d/ -f1-2)"
[[ "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "无法识别仓库：$1"; exit 1; }
SLUG="$(echo "$REPO" | tr 'A-Z' 'a-z' | sed -E 's#[^a-z0-9]+#-#g; s#^-|-$##g')"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/out"
echo "▶ 下载 $REPO 源码（只读取，不执行）"
git clone --depth 1 --quiet "https://github.com/$REPO" "$WORK/src"
rm -rf "$WORK/src/.git"

echo "▶ codex 开始构建（通常 10-30 分钟）"
PROMPT="$(sed "s#{{REPO}}#$REPO#g" "$ROOT/prompts/deep_dive.md")"
# workspace-write：只能写工作目录，默认不能联网
codex exec --skip-git-repo-check --sandbox workspace-write -C "$WORK" "$PROMPT"

[ -f "$WORK/out/index.html" ] || { echo "✗ codex 没有产出 out/index.html"; exit 1; }

echo "▶ 自动检查"
if ! (cd "$ROOT" && "$PY" -m radar.check_demo "$WORK/out/index.html" "$REPO"); then
  read -r -p "检查未通过，仍然发布吗？[y/N] " ans
  [ "$ans" = "y" ] || { echo "已取消"; exit 1; }
fi

echo "▶ 发布"
cd "$ROOT"
git pull --rebase --quiet   # 先同步每日任务的最新提交，避免首页冲突
DEST="$ROOT/site/deep/$SLUG"
rm -rf "$DEST" && mkdir -p "$DEST"
cp -R "$WORK/out/." "$DEST/"
"$PY" -m radar.deep "$REPO" "$SLUG"
git add site data
git commit -m "deep dive: $REPO" --quiet
git push --quiet
echo "✓ 完成：$("$PY" -c 'from radar import config; print(config.SITE_URL)')/deep/$SLUG/ （部署约需 1-2 分钟）"
