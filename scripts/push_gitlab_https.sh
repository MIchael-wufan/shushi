#!/usr/bin/env bash
# 使用 HTTPS + 个人访问令牌 (PAT) 推送到 GitLab（方式 A）
# 用法：
#   1) 在 GitLab：用户设置 -> Access Tokens，创建含 write_repository 的 token
#   2) 在终端（勿把 token 写入仓库或提交到 Git）：
#        export GITLAB_TOKEN='glpat-xxxxxxxx'
#   3) 在仓库根目录执行：
#        bash scripts/push_gitlab_https.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${GITLAB_TOKEN:-}" ]]; then
  echo "未设置环境变量 GITLAB_TOKEN。" >&2
  echo "请先在**本机终端**执行: export GITLAB_TOKEN='你的PAT'（PAT 来自 GitLab -> 用户设置 -> Access Tokens）" >&2
  echo "再运行: bash scripts/push_gitlab_https.sh" >&2
  exit 1
fi

# GitLab 推荐以 oauth2 为用户名、PAT 为密码 走 HTTPS
HOST_PATH="gitlab-ee.zhenguanyu.com/wufanbj05/shushi.git"
PUSH_URL="https://oauth2:${GITLAB_TOKEN}@${HOST_PATH}"

echo "推送到 $HOST_PATH 分支 main ..."
git push "$PUSH_URL" main

# 不把带令牌的 URL 写进 .git/config；上游仍用无口令的 origin
if git rev-parse --abbrev-ref main@{upstream} 2>/dev/null | grep -q .; then
  : # 已有上游
else
  git branch --set-upstream-to=origin/main main 2>/dev/null || true
fi

echo "完成。已推送 main。后续可直接: git push origin main（需已配置凭证助手或再次通过本脚本用 PAT）"
