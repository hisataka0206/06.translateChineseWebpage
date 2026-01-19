# 開発仕様書：Notion記事ベース中国語ロボット用語抽出ツール

本プロジェクトは、Notion上の中国語ロボット工学記事から専門用語を自動抽出し、学習用単語帳（Excel/CSV）を作成するツールの開発仕様書兼READMEです。

## 1. プロジェクト概要

Notionの指定されたデータベース（または親ページ）配下にある中国語のロボット工学記事（子ページ）を読み込み、テキストおよび画像内の文字から専門用語を抽出します。
最終的に、単語の出現頻度や出典元記事を紐付けた単語帳を生成することを目的としています。

---

## 2. 技術スタック & 前提条件

| カテゴリ | 技術要素 | 選定理由・補足 |
| --- | --- | --- |
| **言語** | Python 3.10+ | |
| **LLM API** | **Google Gemini 1.5 Pro** | GPT-4oと比較して画像内文字認識（OCR）性能が高く、大量トークンを安価に処理可能。 |
| **データソース** | Notion API | `notion-client` ライブラリ使用。 |
| **データ処理** | Pandas | 集計・Excel出力に使用。 |
| **環境変数** | `.env` | `python-dotenv` で管理。 |

### 必要な環境変数 (`.env`)
- `NOTION_TOKEN`: Notion Internal Integration Token
- `NOTION_PAGE_ID`: 抽出対象の親ページID
- `GOOGLE_API_KEY`: Gemini APIキー（Google AI Studio）

---

## 3. 機能要件

### Phase 1: Notionデータ取得 (Fetcher)
- **ページ取得**: 指定された `NOTION_PAGE_ID` 配下の子ページ（Database Item含む）を全件再帰的に取得する。
- **ブロック解析**:
    - **テキスト**: Paragraph, Heading, Bulleted List等のテキストコンテンツを結合。
    - **画像**: ImageブロックのURLから画像を一時ダウンロードまたはメモリ上に保持。（NotionのURL有効期限に注意）

### Phase 2: マルチモーダル解析 (Extractor)
Gemini 1.5 Proを用いて、記事ごとのテキストと画像を**同時に**解析します。

- **プロンプト設定**:
    - **役割**: ロボット工学専門の翻訳家
    - **タスク**: テキスト・画像から中国語専門用語（ヒューマノイド、ハードウェア、AI制御等）を抽出
    - **除外**: 一般的な動詞・代名詞
    - **出力**: JSON形式

- **出力データ構造 (JSON Schema)**:
  ```json
  [
    {
      "word": "伺服电机",
      "pinyin": "sì fú diàn jī",
      "meaning_ja": "サーボモータ",
      "context_cn": "伺服电机控制精度高..."
    }
  ]
  ```

### Phase 3: 集計とデータベース化 (Aggregator)
各記事の解析結果を統合・集計します。

- **登場回数 (Frequency)**: 同一単語の出現回数をカウント。
- **出典 (Source)**: その単語が出現した記事タイトルとURLをリスト化。
- **マージ処理**: `word` をキーとしてデータを統合。

### Phase 4: 出力 (Exporter)
集計結果を `robot_vocab.xlsx` として出力します。

**出力カラム構成**:
1. **単語 (Word)**
2. **ピンイン (Pinyin)**
3. **日本語訳 (Meaning)**
4. **登場回数 (Frequency)**
5. **出典記事リスト (Sources)**
6. **代表的な例文 (Context)**

---

## 4. プロジェクト構造

```
06.translateChineseWebpage/
├── README.md                    # 本ファイル（仕様書）
├── USAGE.md                     # 既存の翻訳機能に関する利用ガイド
├── requirements.txt             # 依存パッケージ
├── .env                         # 環境変数
├── config/                      # 設定ファイル
│   └── config.yaml             # Notion設定等
├── src/                         # ソースコード
│   ├── vocab_extractor.py      # [NEW] 単語抽出メインスクリプト（予定）
│   ├── notion/                 # Notion API関連
│   ├── translation/            # 翻訳・LLM関連
│   └── ...
└── logs/                        # 実行ログ
```

---

## 5. 開発・実行フロー (予定)

### 依存パッケージのインストール
```bash
pip install -r requirements.txt
```
※ `google-generativeai` ライブラリの追加が必要になる可能性があります。

### 実行コマンド
```bash
python -m src.vocab_extractor
```

### 既存の翻訳機能について
本プロジェクトには、Notionページを全文翻訳して「done」プレフィックスを付与する機能も含まれています。
詳細は [USAGE.md](./USAGE.md) を参照してください。
