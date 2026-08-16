#!/usr/bin/env bash
set -euo pipefail

# 指定ディレクトリ（省略時はカレントディレクトリ）に対応する Claude Code のセッションログ
# (~/.claude/projects/<encoded-path>/*.jsonl) を突き合わせて、ccusage が集計した
# セッションごとのコストのうちこのプロジェクト分だけを合計する。
#
# Usage: cc_dir_usage.sh [dir]
#
# 背景: `ccusage session --json` の各エントリは projectPath を持たず、
# セッションを識別できるのは period フィールド（= セッションUUID）だけ。
# 一方 ~/.claude/projects/<encoded-cwd>/ 配下の *.jsonl のファイル名がそのままセッションUUIDなので、
# そこからこのプロジェクトのセッションID一覧を作り、ccusage の出力とID一致でフィルタする。

PROJECT_DIR="$(cd "${1:-.}" && pwd)"
ENCODED_PATH="$(echo "$PROJECT_DIR" | sed -e 's/[\/._]/-/g')"
CLAUDE_PROJECT_DIR="$HOME/.claude/projects/$ENCODED_PATH"

if [ ! -d "$CLAUDE_PROJECT_DIR" ]; then
  echo "Claude project directory not found: $CLAUDE_PROJECT_DIR" >&2
  exit 1
fi

SESSION_IDS_JSON=$(find "$CLAUDE_PROJECT_DIR" -maxdepth 1 -name '*.jsonl' -exec basename {} \; \
  | sed 's/\.jsonl$//' \
  | jq -R . \
  | jq -s .)

npx ccusage@latest session --json 2>/dev/null | jq --argjson ids "$SESSION_IDS_JSON" '
  [.session[]? | select(.period as $p | $ids | index($p)) | .totalCost // 0] | add // 0
'
