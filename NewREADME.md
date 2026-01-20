## 開発仕様書：Notion記事ベース中国語ロボット用語抽出ツール

### 1\. プロジェクト概要

Notionの指定されたデータベース（または親ページ）配下にある中国語のロボット工学記事（子ページ）を読み込み、テキストおよび画像内の文字から専門用語を抽出する。最終的に、単語の出現頻度や出典元記事を紐付けた単語帳（Excel/CSV）を生成する。

### 2\. 技術スタック & 前提条件

  * **言語:** Python 3.10+
  * **LLM API:** Google Gemini 1.5 Pro
      * *理由:* GPT-4oよりも画像内の文字認識（OCR）性能が高く、大量のトークンを安価に処理できるため。
  * **データソース:** Notion API (`notion-client`)
  * **データ処理:** Pandas
  * **環境変数:** `.env` ファイルで管理
      * `NOTION_TOKEN`: NotionのInternal Integration Token
      * `NOTION_PAGE_ID`: 親ページのID
      * `GOOGLE_API_KEY`: Gemini APIキー

### 3\. 機能要件

#### Phase 1: Notionデータ取得 (Fetcher)

1.  **ページ取得:** 指定された `NOTION_PAGE_ID` の子ページ（Databaseの場合はその中の各Item）を全件取得する。
2.  **ブロック解析:** 各ページ内のブロックを走査する。
      * **テキスト:** Paragraph, Heading, Bulleted Listなどのテキストコンテンツを結合する。

#### Phase 2: マルチモーダル解析 (Extractor)

1.  **Gemini 1.5 Proへのリクエスト:**
      * 1記事ごとに、「全テキスト」をまとめて1回のAPIリクエストとして送信する。
      * **プロンプトの指示内容:**
          * 役割: ロボット工学専門の翻訳家。
          * タスク: テキストから、中国語の専門用語（ヒューマノイド、ハードウェア、AI制御関連）を抽出する。
          * 除外: 一般的な動詞や代名詞。
          * 出力形式: JSONリストのみ。
2.  **構造化データ定義 (JSON Schema):**
    ```json
    [
      {
        "word": "原文単語 (例: 伺服电机)",
        "pinyin": "ピンイン (例: sì fú diàn jī)",
        "meaning_ja": "日本語訳 (例: サーボモータ)",
        "context_cn": "記事内での使用文脈（短い抜粋）"
      },
      ...
    ]
    ```

#### Phase 3: 集計とデータベース化 (Aggregator)

1.  **データ結合:** 全記事の解析結果（JSON）を統合する。
2.  **集計ロジック:**
      * **登場回数 (Frequency):** 同じ単語（`word`）が出現するたびにカウントアップする。
      * **出典 (Source):** その単語がどの記事（タイトル + Notion URL）で使われていたかのリストを保持する。
3.  **重複処理:** 同じ単語でも意味やピンインが異なるケースは稀だが、基本は `word` をキーにしてマージする。

#### Phase 4: 出力 (Exporter)

  * 以下のカラムを持つExcelファイル (`robot_vocab.xlsx`) を出力する。
    1.  **単語 (Word)**
    2.  **ピンイン (Pinyin)**
    3.  **日本語訳 (Meaning)**
    4.  **登場回数 (Frequency)**
    5.  **出典記事リスト (Sources)**: 記事タイトルをカンマ区切りなどで記載
    6.  **代表的な例文 (Context)**: 最初に抽出された使用例

### 4\. 処理フロー（疑似コード）

```python
results = []

pages = notion.get_child_pages(PARENT_ID)

for page in pages:
    print(f"Processing: {page.title}")
    
    # コンテンツ収集
    text_content = notion.get_text_blocks(page.id)
    
    # LLM解析 (Gemini 1.5 Pro)
    # テキストと画像を同時に投げる
    extracted_data = gemini.extract_terms(
        text=text_content, 
        prompt="ロボット工学用語を抽出してJSONで返して..."
    )
    
    # 出典情報を付与してリストに追加
    for item in extracted_data:
        item['source_title'] = page.title
        item['source_url'] = page.url
        results.append(item)

# 集計処理
df = pandas.DataFrame(results)
final_df = aggregate_by_word(df) # 登場回数計算や出典のマージ
final_df.to_excel("output.xlsx")
```

-----

### AIコーディングツール（Cursor/Windsurfなど）への指示プロンプト

この仕様書を使って実際にコードを書かせる際は、以下のプロンプトをAIに入力してください。

> **指示:**
> あなたはPythonのエキスパートです。
> 以下の「開発仕様書」に基づいて、Notionの記事から中国語のロボット関連用語を抽出し、単語帳を作成するPythonスクリプトを作成してください。
>
> **ポイント:**
>
> 1.  過去にNotion APIを使ったことがあるので、`notion-client`の基本的な使い方は理解しています。
> 3.  出力結果には、単語ごとの「登場回数」と「どの記事に出てきたか」を含めるロジックを実装してください。
> 4.  コードは `.env` ファイルから環境変数を読み込むように設計し、エラーハンドリング（特にAPI制限や画像ダウンロード失敗時）を考慮してください。

# 依存パッケージインストール
pip install -r requirements.txt

# テスト実行
python -m pytest tests/test_vocab_extraction.py -v

# 単語抽出実行
python -m src.vocab_extractor