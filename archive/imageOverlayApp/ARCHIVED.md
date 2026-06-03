# ARCHIVED — imageOverlayApp（2026-06-03 アーカイブ）

[[アーカイブ化]] / [[imageOverlayApp]] / [[image-translate-overlay スキルへ移行]]

## 状態
このローカルアプリ（中国語インフォグラフィックのOCR＋翻訳→日本語オーバーレイ→PPTX/PNG/HTML出力）は
**現時点で使用を停止しアーカイブ**した。

## 理由
同等の機能を **`image-translate-overlay` スキル** で実現する方針に切り替えたため。
個別アプリの起動・依存管理（tesseract / venv / FastAPI サーバ常駐）が不要になり、運用が軽くなる。

## 再開時のメモ
- コード・編集UI・PPTX出力ロジックは本ディレクトリにそのまま保持（削除はしていない）。
- 復活させる場合は `run_app.command` をダブルクリックで従来どおり起動可能。
- 中国記事の図の日本語化は当面 image-translate-overlay スキルで行う。
