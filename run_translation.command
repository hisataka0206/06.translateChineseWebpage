#!/bin/bash
# [[Notion中国語→日本語翻訳]] runner
# Claude scheduled task から Spotlight 経由でダブルクリック起動される想定。
# ログは logs/runs/ に個別ファイルで保存され、latest_status.txt で完了検知できる。

set -u

PROJECT_DIR="/Users/hisatakamac/work/humanoidAsAService/Tools/translateChineseWebpage"
cd "$PROJECT_DIR" || {
  echo "FATAL: cannot cd to $PROJECT_DIR" >&2
  exit 1
}

mkdir -p logs/runs

TS=$(date '+%Y%m%d_%H%M%S')
LOG="logs/runs/run_${TS}.log"
STATUS="logs/runs/latest_status.txt"

echo "=== RUN START $(date '+%Y-%m-%d %H:%M:%S %Z') ===" | tee "$LOG"
echo "PROJECT_DIR=$PROJECT_DIR" | tee -a "$LOG"
echo "PYTHON=$(which python3)" | tee -a "$LOG"
echo "" | tee -a "$LOG"

# 実行（stderr も tee）
python3 -m src.main 2>&1 | tee -a "$LOG"
EC=${PIPESTATUS[0]}

echo "" | tee -a "$LOG"
echo "=== RUN END $(date '+%Y-%m-%d %H:%M:%S %Z') EXIT=$EC ===" | tee -a "$LOG"

# 完了検知用ステータスファイル（Claude 側はこの mtime を watch）
printf '%s EXIT=%s LOG=%s\n' \
  "$(date '+%Y-%m-%d %H:%M:%S %Z')" \
  "$EC" \
  "$LOG" \
  > "$STATUS"

# 結果が見やすいよう少し待機してからウィンドウを閉じる
sleep 3

# Terminal を自動で閉じる（設定で "シェルが終了したらウィンドウを閉じる" が ON のときは不要だが保険）
osascript <<'OSA' >/dev/null 2>&1
tell application "Terminal"
  set _wins to windows
  repeat with _w in _wins
    try
      if (busy of _w) is false then close _w saving no
    end try
  end repeat
end tell
OSA

exit $EC
