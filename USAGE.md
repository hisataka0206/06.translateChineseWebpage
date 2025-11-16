# 使い方 (Usage Guide)

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example`を`.env`にコピーして、APIキーを設定してください。

```bash
cp .env.example .env
```

`.env`ファイルを編集:

```env
NOTION_API_KEY=your_actual_notion_api_key
OPENAI_API_KEY=your_actual_openai_api_key
```

#### Notion API Keyの取得方法:
1. https://www.notion.so/my-integrations にアクセス
2. 「新しいインテグレーション」を作成
3. トークンをコピーして`.env`に貼り付け
4. 翻訳したいページと翻訳先の親ページにインテグレーションを共有

#### OpenAI API Keyの取得方法:
1. https://platform.openai.com/api-keys にアクセス
2. 新しいAPIキーを作成
3. キーをコピーして`.env`に貼り付け

### 3. 設定ファイルの編集

`config/config.yaml`を編集して、NotionページIDを設定してください。

```yaml
notion:
  # 翻訳元の中国語ページID(複数指定可能)
  source_page_ids:
    - "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    - "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"

  # 翻訳先の親ページID
  destination_parent_id: "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
```

#### Page IDの取得方法:
NotionページのURLから取得できます:
- URL: `https://www.notion.so/My-Page-abc123def456`
- Page ID: `abc123def456`

### 4. カスタムプロンプトの調整(オプション)

翻訳の品質を向上させたい場合、`config/translation_prompt.txt`を編集してください。

## 実行方法

### 基本的な実行

```bash
python -m src.main
```

### 実行結果

実行すると以下の処理が行われます:

1. ✓ 設定ファイルから中国語ページIDを読み込み
2. ✓ 各ページがすでに翻訳済み(titleに"done"がある)かチェック
3. ✓ 未翻訳のページのみ処理:
   - テキストを中国語→日本語に翻訳
   - 画像内の中国語テキストを抽出・翻訳
   - 翻訳テーブルをtoggleブロックで作成
4. ✓ 新しい日本語ページを作成(タイトルは"done 翻訳後のタイトル")
5. ✓ 元の中国語ページのタイトルに"done"を追加(再翻訳防止)

### ログ確認

実行ログは`logs/translation.log`に保存されます。

```bash
# リアルタイムでログを確認
tail -f logs/translation.log
```

## プロジェクト構造

```
06.translateChineseWebpage/
├── README.md                    # プロジェクト説明
├── USAGE.md                     # 使い方ガイド(このファイル)
├── requirements.txt             # Python依存関係
├── .env.example                 # 環境変数テンプレート
├── .env                         # 環境変数(作成必要・gitignore対象)
├── .gitignore                   # Git除外設定
├── config/
│   ├── config.yaml             # メイン設定ファイル
│   └── translation_prompt.txt  # 翻訳プロンプト
├── src/
│   ├── main.py                 # メインエントリーポイント
│   ├── notion/
│   │   ├── client.py           # Notion APIクライアント
│   │   └── parser.py           # ページ・ブロック解析
│   ├── translation/
│   │   ├── translator.py       # テキスト翻訳
│   │   └── image_translator.py # 画像テキスト翻訳
│   ├── formatting/
│   │   └── toggle_formatter.py # Toggleブロック生成
│   └── publisher/
│       └── notion_publisher.py  # 翻訳ページ作成
├── tests/                       # テストコード
├── data/
│   ├── input/                  # テスト用入力データ
│   └── output/                 # 出力キャッシュ
└── logs/
    └── translation.log         # 実行ログ
```

## トラブルシューティング

### エラー: "Missing NOTION_API_KEY environment variable"

→ `.env`ファイルが存在し、`NOTION_API_KEY`が設定されているか確認してください。

### エラー: "Missing OPENAI_API_KEY environment variable"

→ `.env`ファイルに`OPENAI_API_KEY`が設定されているか確認してください。

### ページが翻訳されない

→ ページのタイトルに"done"が含まれていないか確認してください。含まれている場合、すでに翻訳済みとしてスキップされます。

### 画像翻訳が機能しない

→ GPT-4 Visionモデルへのアクセス権があるか確認してください。OpenAIのダッシュボードで確認できます。

## 注意事項

- 翻訳にはOpenAI APIの料金が発生します
- 大量のページを一度に翻訳する場合、API制限に注意してください
- Notion APIのレート制限: 3リクエスト/秒
- 画像解析はGPT-4 Visionを使用するため、通常のGPT-4より料金が高くなります
