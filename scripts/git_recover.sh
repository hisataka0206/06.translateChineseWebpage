#!/bin/bash
# git_recover.sh
# ローカル .git が壊れた状態（HEAD bad object / master.bak 残存 / index.lock 残存）を
# origin/master に合わせて安全に復旧する。
#
# 検出された壊れ方（2026-06-03 時点）:
#   - .git/index.lock        : 2026-04-30 の空ロックが残存し git 操作をブロック
#   - .git/refs/heads/master.bak : 不正な sha (d6525a...b1b1b1b1) を指す壊れた backup ref
#   - refs/heads/master      : ローカルに存在しない sha (da7b9aa) を指す → "fatal: bad object HEAD"
#   - origin/master          : 429d5c8（ローカルにオブジェクトあり・正常）
#
# 使い方:  cd <repo> && bash scripts/git_recover.sh
set -e

REPO="/Users/hisatakamac/work/humanoidAsAService/Tools/translateChineseWebpage"
cd "$REPO"

echo "=== 1) 念のためバックアップ ==="
cp -f .git/refs/heads/master "/tmp/master_ref_$(date +%s).bak" 2>/dev/null || true

echo "=== 2) 残存ロック / 壊れた backup ref を削除 ==="
rm -f .git/index.lock
rm -f .git/refs/heads/master.bak

echo "=== 3) master を正常な commit に向け直す ==="
git update-ref refs/heads/master 429d5c8

echo "=== 4) リモート最新を取得 ==="
git fetch origin

echo "=== 5) origin/master に揃える（作業ツリーはコード修正済みのものを保持したい場合は手順A、完全同期は手順B） ==="
echo "--- 現在の status ---"
git status

cat <<'NOTE'

----------------------------------------------------------------------
ここで一旦停止します。次のどちらかを選んでください:

[A] 直近に当環境で適用した publisher 修正(CTA削除)を残してコミットする場合:
      git add src/publisher/x_publisher.py src/publisher/linkedin_publisher.py
      git commit -m "fix(publisher): remove spammy CTA 詳細はこちら👇 from X/LinkedIn output"
      git push origin master

[B] リモートを正として作業ツリーを完全に巻き戻す場合（ローカル変更は破棄）:
      git reset --hard origin/master
   ※ この場合 publisher 修正は消えるので、再度適用が必要。
----------------------------------------------------------------------
NOTE
