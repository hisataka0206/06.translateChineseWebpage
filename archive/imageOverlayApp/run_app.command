#!/bin/bash
# Image Translate Overlay App launcher (double-click on macOS)
cd "$(dirname "$0")"

echo "=== Image Translate Overlay App ==="

# 1) tesseract binary check
if ! command -v tesseract >/dev/null 2>&1; then
  echo "[!] tesseract が見つかりません。インストールしてください:"
  echo "    brew install tesseract"
  echo "   （中国語データは本アプリに同梱済みです）"
  read -p "Enterで終了" _; exit 1
fi

# 2) python venv + deps
if [ ! -d ".venv" ]; then
  echo "[*] 仮想環境を作成しています..."
  python3 -m venv .venv
fi
source .venv/bin/activate
echo "[*] 依存パッケージを確認しています..."
pip install -q --upgrade pip >/dev/null 2>&1
pip install -q -r requirements.txt

# 3) launch server and open browser
PORT=8765
echo "[*] サーバを起動します → http://127.0.0.1:${PORT}"
( sleep 2; open "http://127.0.0.1:${PORT}" ) &
python -m uvicorn app:app --host 127.0.0.1 --port ${PORT}
