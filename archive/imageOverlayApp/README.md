# Image Translate Overlay App

中国語の[[インフォグラフィック]]画像を読み込み、[[OCR]]＋[[翻訳]]して **日本語の編集可能オーバーレイ** を生成。ブラウザ上で[[PowerPoint風ショートカット]]で微調整し、**[[PPTX]] / [[PNG]] / [[HTML]]** で出力するローカルアプリ。

## できること

1. ユーザーが画像を選ぶ
2. アプリが解析して、元の位置に白背景で日本語を配置した編集用[[HTML]]を生成し、ブラウザで開く
   - **クラウド画像理解（推奨）**: [[tesseract]]で座標を取得しつつ、[[GPT-4o]]が画像を理解して **意味単位でまとめ・ノイズ除去・文脈翻訳**（Cowork品質）。OCR座標で精密に配置。
   - **Ollama簡易**: OCR行単位＋ローカル翻訳（キー不要・オフライン・精度は簡易）。
3. ドラッグ／整列／書式などPowerPoint風の操作で編集
4. **PPTX**（PowerPointで再編集可）・**PNG**・**HTML** で書き出し

## セットアップ（初回のみ）

```bash
# tesseract 本体（中国語データはアプリに同梱済み）
brew install tesseract
```

`.env`（親フォルダ `translateChineseWebpage/.env`）に翻訳用キー:

```
OPENAI_API_KEY=sk-...        # クラウドLLM翻訳に使用
# OPENAI_MODEL=gpt-4o-mini   # 任意（既定 gpt-4o-mini）
# OLLAMA_MODEL=qwen3:8b      # Ollama利用時の任意
```

Ollama（ローカル・キー不要）を使う場合は `ollama serve` と `ollama pull qwen3:8b` を済ませておく。

## 起動

`run_app.command` を**ダブルクリック**（または `bash run_app.command`）。
自動で仮想環境作成→依存導入→`http://127.0.0.1:8765` をブラウザで開く。

## 使い方

1. 画像を選び、翻訳エンジン（クラウド/Ollama）を選択して「解析」
2. 編集画面で **編集モード ON** → ドラッグ／矢印キー／整列／書式／Undo
3. 上部「出力」から **PPTX / PNG / HTML** を保存

ショートカット一覧は編集画面の「⌨ ショートカット」ボタン。

## 構成

| ファイル | 役割 |
|---|---|
| `app.py` | FastAPIサーバ（アップロード・編集配信・出力API） |
| `pipeline.py` | OCR（tesseract）＋行クラスタリング＋配置items生成 |
| `vlm.py` | GPT-4oで画像理解→意味単位グルーピング・ノイズ除去・文脈翻訳（座標はOCRトークンから精密化） |
| `translate.py` | 中→日 バッチ翻訳（Ollama簡易パス用, OpenAI互換API） |
| `pptx_export.py` | items＋背景画像 → 編集可能 .pptx |
| `editor_template.html` | 編集UI（PowerPoint風）＋出力ボタン |
| `static/html2canvas.min.js` | PNG書き出し（同梱・オフライン可） |
| `tessdata/chi_sim.traineddata` | 中国語OCRデータ（同梱） |

## 注意

- PPTX/HTML出力は**アプリ起動中**のみ（サーバ経由）。PNGはブラウザ内で完結。
- OCRの座標は概ね合いますが、密集部は編集画面でドラッグ調整してください。
- フォント名は PPTX 側で "Hiragino Sans" を指定（Windows等では適宜変更）。
