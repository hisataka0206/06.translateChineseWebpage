"""
Notion text utilities.

Notion API は ``rich_text[].text.content`` 1 セグメントあたり最大 2000 文字までしか
受け付けない (over だと ``body failed validation`` で 400 を返す)。
本モジュールは長文を安全な複数セグメントに分割する共通ロジックを提供する。

主な API:
    - ``chunk_text(text, limit)``: 単純な文字数チャンクへ分割
    - ``make_text_rich_text(text, annotations, link)``: 1 つの論理テキストランから
      Notion rich_text 配列を生成 (必要に応じて自動チャンク)
    - ``sanitize_rich_text_array(rich_text)``: 既存 rich_text 配列内の過大セグメント
      を分割しつつ annotations/link 情報を保持
    - ``sanitize_block_rich_text(block)``: 1 ブロック内の rich_text を再帰的に
      sanitize し、長文 paragraph を複数ブロックへ分割する必要があれば
      ブロック列を返す
    - ``sanitize_blocks(blocks)``: ブロック列を一括 sanitize して 1 本のリストに
      平坦化する

すべての関数は副作用なし (入力を mutate しない)。
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# Notion 公開仕様の hard limit。これを超えると 400 が返る。
NOTION_RICH_TEXT_HARD_LIMIT = 2000
# 余裕を持たせた安全側のチャンクサイズ。マルチバイト境界の崩れ等を吸収するための
# 100 文字バッファ。
SAFE_CHUNK_LIMIT = 1900
# 1 ブロックあたりの rich_text 配列の最大長 (Notion 仕様)。
MAX_SEGMENTS_PER_BLOCK = 100

# rich_text を保持する block_type 一覧。Notion 公式ドキュメントの block オブジェクト
# プロパティと完全一致させる必要は無いが、現在パイプラインで生成・コピーされる
# 主要タイプを網羅する。
_RICH_TEXT_BLOCK_TYPES = (
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "toggle",
    "quote",
    "callout",
    "code",
    "template",
)


def chunk_text(text: str, limit: int = SAFE_CHUNK_LIMIT) -> List[str]:
    """文字数で text を分割する。

    Args:
        text: 分割対象。``None`` または空文字列の場合は空リストを返す。
        limit: 1 チャンクあたりの最大文字数。

    Returns:
        分割後の文字列リスト。
    """
    if not text:
        return []
    if limit <= 0:
        # 防御コード: 不正な limit が来てもクラッシュさせない。
        limit = SAFE_CHUNK_LIMIT
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def make_text_rich_text(
    text: str,
    annotations: Optional[Dict[str, Any]] = None,
    link: Optional[str] = None,
    limit: int = SAFE_CHUNK_LIMIT,
) -> List[Dict[str, Any]]:
    """1 つの論理テキストランから Notion rich_text 配列を生成する。

    text が ``limit`` を超える場合は自動で複数セグメントへ分割する。
    annotations と link は全セグメントへ複製される。

    Args:
        text: 表示テキスト。
        annotations: ``{"bold": True}`` 等の Notion annotations オブジェクト。
        link: ハイパーリンク URL。
        limit: 1 セグメントあたりの最大文字数。

    Returns:
        Notion API へそのまま渡せる rich_text オブジェクトのリスト。
        text が空なら空リストを返す。
    """
    chunks = chunk_text(text, limit)
    out: List[Dict[str, Any]] = []
    for chunk in chunks:
        item: Dict[str, Any] = {
            "type": "text",
            "text": {"content": chunk},
        }
        if link:
            item["text"]["link"] = {"url": link}
        if annotations:
            # annotations はセグメント間で共有するため毎回コピー。
            item["annotations"] = dict(annotations)
        out.append(item)
    return out


def sanitize_rich_text_array(
    rich_text: Optional[Iterable[Dict[str, Any]]],
    limit: int = SAFE_CHUNK_LIMIT,
) -> List[Dict[str, Any]]:
    """既存 rich_text 配列内の過大 text セグメントを分割する。

    各セグメントの annotations / link / href / type を保持したまま、
    ``text.content`` が ``limit`` を超えるものだけを複数セグメントへ分割する。
    text 以外の type (equation, mention, …) はそのまま通す。

    Args:
        rich_text: 既存 rich_text 配列。``None`` 可。
        limit: 1 セグメントあたりの最大文字数。

    Returns:
        分割済みの新しい rich_text 配列 (常に list)。
    """
    if not rich_text:
        return []

    out: List[Dict[str, Any]] = []
    for item in rich_text:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            # text 以外はそのまま通過させる。
            out.append(copy.deepcopy(item))
            continue
        content = item.get("text", {}).get("content", "") or ""
        if len(content) <= limit:
            out.append(copy.deepcopy(item))
            continue

        # 過大: 分割しつつメタ情報をコピー。
        annotations = item.get("annotations")
        link_obj = item.get("text", {}).get("link")
        href = item.get("href")
        for chunk in chunk_text(content, limit):
            new_item: Dict[str, Any] = {
                "type": "text",
                "text": {"content": chunk},
            }
            if link_obj:
                # link オブジェクト ({"url": ...}) を丸ごとコピー。
                new_item["text"]["link"] = dict(link_obj)
            if annotations:
                new_item["annotations"] = dict(annotations)
            if href:
                new_item["href"] = href
            out.append(new_item)

    if len(out) > MAX_SEGMENTS_PER_BLOCK:
        # rich_text 配列長の API 上限。極端な巨大段落のみ該当する想定。
        # その場合は ``sanitize_block_rich_text`` 側で複数 paragraph へ分割される。
        logger.warning(
            "rich_text segments (%d) exceed Notion per-block limit (%d); "
            "caller should split into multiple blocks.",
            len(out),
            MAX_SEGMENTS_PER_BLOCK,
        )
    return out


def _split_segments_into_blocks(
    block_type: str,
    base_block: Dict[str, Any],
    segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """rich_text segments が ``MAX_SEGMENTS_PER_BLOCK`` を超える場合に、
    同種ブロックを連結して返す。children などのメタ情報は最初のブロックだけに残す。
    """
    if len(segments) <= MAX_SEGMENTS_PER_BLOCK:
        new_block = copy.deepcopy(base_block)
        new_block[block_type] = dict(new_block.get(block_type, {}))
        new_block[block_type]["rich_text"] = segments
        return [new_block]

    blocks: List[Dict[str, Any]] = []
    for i in range(0, len(segments), MAX_SEGMENTS_PER_BLOCK):
        chunk = segments[i:i + MAX_SEGMENTS_PER_BLOCK]
        new_block = copy.deepcopy(base_block)
        content = dict(new_block.get(block_type, {}))
        content["rich_text"] = chunk
        if i != 0:
            # 2 個目以降の分割では children / icon / color を一旦落とす
            # (重複を避けるため)。
            for k in ("children",):
                content.pop(k, None)
        new_block[block_type] = content
        blocks.append(new_block)
    return blocks


def sanitize_block_rich_text(
    block: Dict[str, Any],
    limit: int = SAFE_CHUNK_LIMIT,
) -> List[Dict[str, Any]]:
    """1 ブロック内の rich_text を安全な長さへ整える。

    text の長さが ``limit`` を超える場合は同一ブロック内の rich_text を分割。
    rich_text 配列が ``MAX_SEGMENTS_PER_BLOCK`` を超える場合は同種ブロック列に
    展開する。table 系など特殊構造は touch しない。

    Args:
        block: Notion ブロック (新規 / コピー双方の形式に対応)。
        limit: 1 セグメントあたりの最大文字数。

    Returns:
        sanitize 済みブロックのリスト。通常は要素 1。
    """
    if not isinstance(block, dict):
        return [block]

    block_type = block.get("type")
    if not block_type or block_type not in _RICH_TEXT_BLOCK_TYPES:
        return [copy.deepcopy(block)]

    content = block.get(block_type, {}) or {}
    rich_text = content.get("rich_text")
    if not rich_text:
        return [copy.deepcopy(block)]

    sanitized = sanitize_rich_text_array(rich_text, limit)
    return _split_segments_into_blocks(block_type, block, sanitized)


def sanitize_blocks(
    blocks: Iterable[Dict[str, Any]],
    limit: int = SAFE_CHUNK_LIMIT,
) -> List[Dict[str, Any]]:
    """ブロック列を一括 sanitize し、平坦化したリストを返す。"""
    out: List[Dict[str, Any]] = []
    for block in blocks or []:
        out.extend(sanitize_block_rich_text(block, limit))
    return out
