# 使い方 (Usage Guide)

## プロジェクトの目的

このプロジェクトは、**Notionに保存されている中国語のWebページ記事を日本語に翻訳**し、新しいNotionページとして作成するサービスです。

**主な機能:**
- 中国語テキストを日本語に自動翻訳
- 画像内の中国語テキストを抽出・翻訳し、対訳表を作成
- 対訳表をToggleブロック（折りたたみ可能）で表示
- 親ページ配下の子ページを自動検出して一括翻訳

---

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

**インストールされるパッケージ:**
- notion-client: Notion API連携
- openai: GPT-4による翻訳・画像解析
- Pillow: 画像フォーマット変換（WebP → JPEG）
- その他: yaml, dotenv, requests, colorlog

### 2. OpenAI APIキーの設定

`.env`ファイルにOpenAI APIキーを設定します:

```bash
# .envファイルを作成
cp .env.example .env
```

`.env`ファイルを編集:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxx
```

**OpenAI API Keyの取得方法:**
1. https://platform.openai.com/api-keys にアクセス
2. 「Create new secret key」をクリック
3. キーをコピーして`.env`に貼り付け

### 3. Notion設定の編集

`config/config.yaml`を編集して、NotionページIDを設定:

```yaml
notion:
  # Notion API統合トークン
  token: "ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

  # 翻訳元: 中国語ページの親ページID
  source_page_ids:
    - "your-parent-page-id-here"

  # 翻訳先: 日本語ページを作成する親ページID
  destination_parent_id: "your-destination-parent-id-here"
```

**Notion API統合トークンの取得方法:**
1. https://www.notion.so/my-integrations にアクセス
2. 「新しいインテグレーション」を作成
3. トークンをコピーして`config.yaml`の`token`に貼り付け
4. **重要:** 翻訳元ページと翻訳先ページの両方でインテグレーションを共有

**Notion Page IDの取得方法:**
- NotionページのURLから取得:
  - URL: `https://www.notion.so/My-Page-2adcd55722618022834fc77653064573`
  - Page ID: `2adcd55722618022834fc77653064573`
- ハイフン付きの場合: `2adcd557-2261-8022-834f-c77653064573`
- ハイフンなしの場合: `2adcd55722618022834fc77653064573`
- **どちらの形式でも使用可能です**

### 4. 翻訳プロンプトのカスタマイズ（オプション）

翻訳品質を調整したい場合、`config/translation_prompt.txt`を編集:

```
あなたは中国語から日本語への翻訳専門家です。

以下の中国語テキストを、自然で読みやすい日本語に翻訳してください。

翻訳の際の注意点:
1. 専門用語は正確に翻訳してください
2. 文脈を考慮し、意味が通じるように翻訳してください
...
```

---

## 実行方法

### 基本的な実行

```bash
python3 -m src.main
```

### 実行プロセス

実行すると以下の処理が自動的に行われます:

1. **親ページから子ページを検出**
   - `source_page_ids`に指定した親ページ配下の全子ページを自動検出

2. **各子ページを順次処理**
   - １ページずつ翻訳処理を実行

3. **翻訳処理の詳細**
   - ✓ ページタイトルを翻訳
   - ✓ 本文テキストを段落ごとに翻訳
   - ✓ 画像を処理:
     - WebP/PNG形式 → JPEG形式に変換
     - GPT-4oで画像内の中国語テキストを抽出
     - GPT-4で中国語→日本語に翻訳
     - 対訳表（中国語｜日本語）を作成
     - Toggleブロックで折りたたみ表示

4. **新しいページを作成**
   - タイトル: `翻訳後のタイトル`
   - 翻訳先の親ページ配下に作成

5. **元ページを更新**
   - 翻訳が完了したページはprocessed source parentに移動すること
   - 翻訳が完了したページは元のsource pageからは削除すること

### 実行例

```bash
$ python3 -m src.main

============================================================
Starting Chinese to Japanese Translation Service
============================================================
Found 1 parent pages to process
Destination parent ID: 2adcd5572261800b9b65f99cdecd7b2e

Discovering child pages from parent: 2adcd55722618022834fc77653064573
Found 14 child pages

============================================================
Total child pages discovered: 14
============================================================

[1/14] Processing page: 294cd557-2261-812b-ad98-ce7eed670105
✓ Successfully translated: 人形机器人解析
  New page ID: 2adcd557-2261-819b-9316-cc45f61d1ec4

[2/14] Processing page: 294cd557-2261-8128-ae13-fd739a8b3d76
⊘ Skipped (already translated): 294cd557-2261-8128-ae13-fd739a8b3d76

...

============================================================
Translation Summary
============================================================
Total pages: 14
✓ Successfully translated: 13
✗ Errors: 0

Translation service completed!
```

### ログの確認

実行ログは`logs/translation.log`に保存されます:

```bash
# リアルタイムでログを確認
tail -f logs/translation.log

# エラーのみ確認
grep ERROR logs/translation.log
```

---

## プロジェクト構造

```
06.translateChineseWebpage/
├── README.md                    # プロジェクト説明（日本語）
├── USAGE.md                     # 使い方ガイド（このファイル）
├── requirements.txt             # Python依存パッケージ一覧
├── .env                         # 環境変数（OpenAI APIキー）
├── .env.example                 # 環境変数テンプレート
├── .gitignore                   # Git管理除外ファイル
│
├── config/                      # 設定ファイル
│   ├── config.yaml             # メイン設定（Notion, OpenAI設定）
│   ├── notionAPI.yaml          # Notion API認証情報
│   └── translation_prompt.txt  # カスタム翻訳プロンプト
│
├── src/                         # ソースコード
│   ├── main.py                 # メインエントリーポイント
│   │
│   ├── notion/                 # Notion API連携
│   │   ├── client.py           # APIクライアント（ページ取得・作成）
│   │   └── parser.py           # ページ・ブロック解析
│   │
│   ├── translation/            # 翻訳サービス
│   │   ├── translator.py       # テキスト翻訳（GPT-4）
│   │   └── image_translator.py # 画像テキスト抽出・翻訳（GPT-4o + GPT-4）
│   │
│   ├── formatting/             # コンテンツ整形
│   │   └── toggle_formatter.py # Toggleブロック・テーブル生成
│   │
│   └── publisher/              # ページ公開
│       └── notion_publisher.py  # 翻訳ページ作成・公開
│
├── tests/                       # テストコード
├── data/                        # データ保存（入力・出力）
└── logs/                        # 実行ログ
    └── translation.log         # 翻訳処理ログ
```

---

## 重要な仕様・動作

### 1.翻訳管理システム

 1. Source pageに置かれているページは全て翻訳すること
 2. 翻訳が完了したページはdestination translating pagesに移動すること

### 2.画像処理の仕組み

1. **WebP → JPEG変換**: OpenAIはWebP形式を拒否することがあるため、自動的にJPEGに変換
2. **2段階処理**:
   - Step 1: GPT-4oで画像内の中国語テキストを抽出
   - Step 2: GPT-4で中国語テキストを日本語に翻訳
3. **Toggleブロック**: 対訳表は折りたたみ可能な形式で表示

### 3.親ページ・子ページの関係

```
親ページ（source_page_id）
├── 子ページ1 → 翻訳 → 翻訳先に移動
├── 子ページ2 → 翻訳 → 翻訳先に移動
├── 子ページ3 → 翻訳 → 翻訳先に移動
...
```

---


### 4.編集機能

１．ページによって、以下のような記事の価値とは関係ない文言が一部出ている事があります。削除してください。

**点击蓝字 关注我们**

关注公众号，点击公众号主页右上角“ · · · ”，设置星标，实时关注人形机器人新鲜的行业动态与知识！

２．ページによって、タイトルが設定されていないことがあります。中身を踏まえてタイトルを設定してください。

### 5.翻訳されたページに関する編集
・DB化して保存すること


### 6.Xへの投稿
・DBのX post列がGoであれば、投稿する
・URLと広告文を投稿する
・広告文はx_prompt.yamlに従って生成し、DBのX comment欄に記載する
・config.yamlにXの投稿設定を追加する
・投稿したらDBのX post列をDoneに変更する


## トラブルシューティング

### エラー: "Missing OPENAI_API_KEY environment variable"

**原因**: `.env`ファイルにOpenAI APIキーが設定されていない

**解決方法**:
```bash
# .envファイルを確認
cat .env

# OPENAI_API_KEYが設定されているか確認
# 設定されていない場合は追加
echo 'OPENAI_API_KEY=sk-proj-xxxxx' >> .env
```

### エラー: "Missing Notion API token in config.yaml"

**原因**: `config/config.yaml`のNotionトークンが未設定

**解決方法**:
```yaml
# config/config.yamlを編集
notion:
  token: "ntn_xxxxxxxxxxxxxxxx"  # ← ここに実際のトークンを設定
```

### ページが翻訳されない


**原因2**: 親ページIDが間違っている
- **確認**: `config.yaml`の`source_page_ids`を確認
- **解決**: 正しい親ページIDに修正

### 画像翻訳が機能しない

**症状**: 画像が表示されるが、対訳表が作成されない

**原因**: OpenAI APIがWebP形式を拒否（現在は修正済み）

**確認方法**:
```bash
# ログでエラーを確認
grep "Image processing error" logs/translation.log
```

**解決状況**: WebP → JPEG変換を実装済み（自動的に変換されます）

### API Error: 500 Internal Server Error

**原因**: OpenAI APIの一時的な障害または画像サイズ過大

**解決方法**:
1. 数分待ってから再実行
2. ログで詳細を確認: `grep "500\|ERROR" logs/translation.log`
3. 画像は自動的に2048px以下にリサイズされます

---

## API料金について

### OpenAI API料金の目安

**テキスト翻訳（GPT-4）**:
- 1ページあたり約500-2000トークン
- 料金: 約$0.01-0.06 / ページ

**画像解析（GPT-4o）**:
- 1画像あたり: 約$0.002-0.01
- 高解像度: やや高額

**推定コスト（14ページ、各5画像の場合）**:
- テキスト翻訳: $0.14-0.84
- 画像解析: $0.14-0.70
- **合計: 約$0.28-1.54**

### Notion API

- 無料（レート制限: 3リクエスト/秒）

---

## よくある質問（FAQ）

### Q1: 複数の親ページを一度に処理できますか？

はい、可能です:

```yaml
notion:
  source_page_ids:
    - "parent-page-1"
    - "parent-page-2"
    - "parent-page-3"
```


### Q3: 画像内のテキストが正しく抽出されない場合は？

- GPT-4oの画像認識精度に依存します
- 低解像度や複雑なレイアウトは認識困難な場合があります
- ログで `Extracted X text pairs from image` を確認してください



---

## サポート・問い合わせ

問題が発生した場合:

1. **ログを確認**: `logs/translation.log`
2. **エラーメッセージをコピー**
3. **設定ファイルを確認**: `config/config.yaml`, `.env`

開発者: Claude Code
バージョン: 1.0.0
最終更新: 2025-11-16
