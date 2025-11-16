import requests
import copy
import os
import yaml


def load_notion_config(path="../config/notionAPI.yaml"):
    """YAML から Notion API 設定を読み込む"""
    # 絶対パスに変換
    abs_path = os.path.abspath(path)

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"YAML file not found: {abs_path}")

    with open(abs_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if "notion" not in data:
        raise KeyError("YAML 内に 'notion:' セクションがありません。")

    notion = data["notion"]

    # 必須項目チェック
    required_keys = ["token", "src_page_id", "dst_page_id"]
    for key in required_keys:
        if key not in notion:
            raise KeyError(f"YAML の 'notion' セクションに '{key}' がありません。")

    return notion


# NOTION_TOKEN = "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"
# ID1 = "2adcd55722618022834fc77653064573"  # コピー元ページID
# ID2 = "2adcd5572261800b9b65f99cdecd7b2e"  # コピー先ページID


# ログを最小化、正常時は print しない
def info(msg):
    print(msg)


def get_blocks(block_or_page_id: str):
    url = f"https://api.notion.com/v1/blocks/{block_or_page_id}/children?page_size=100"
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        raise RuntimeError(f"Failed to get blocks: {res.status_code} {res.text}")
    return res.json().get("results", [])


def to_creatable_block(block: dict) -> dict:
    """
    Notion API の新規作成が受け入れる形へ変換。
    未対応タイプは ValueError でスキップ対象。
    """
    block_type = block["type"]

    SIMPLE_TYPES = {
        "paragraph",
        "heading_1",
        "heading_2",
        "heading_3",
        "bulleted_list_item",
        "numbered_list_item",
        "quote",
        "to_do",
        "toggle",
        "callout",
        "code",
        "equation",
        "divider",
        "table_of_contents",
    }

    if block_type == "child_page":
        raise ValueError("child_page is handled separately")

    # 特別処理：table
    if block_type == "table":
        table_meta = block["table"]
        table_block_id = block["id"]

        row_blocks = get_blocks(table_block_id)
        creatable_rows = []
        for r in row_blocks:
            if r["type"] != "table_row":
                continue
            row_inner = copy.deepcopy(r["table_row"])
            creatable_rows.append(
                {
                    "object": "block",
                    "type": "table_row",
                    "table_row": row_inner,
                }
            )

        return {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": table_meta["table_width"],
                "has_column_header": table_meta.get("has_column_header", False),
                "has_row_header": table_meta.get("has_row_header", False),
                "children": creatable_rows,
            },
        }

    # 特別処理：image
    if block_type == "image":
        img = block["image"]
        caption = copy.deepcopy(img.get("caption", []))

        url = None
        if img.get("type") == "external":
            url = img["external"]["url"]
        elif img.get("type") == "file":
            url = img["file"]["url"]

        if not url:
            raise ValueError("image URL not found")

        return {
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": url},
                "caption": caption,
            },
        }

    # シンプル系
    if block_type in SIMPLE_TYPES:
        inner = copy.deepcopy(block[block_type])
        return {"object": "block", "type": block_type, block_type: inner}

    # その他はスキップ
    raise ValueError(f"unsupported type: {block_type}")


def append_blocks(parent_page_id: str, blocks: list[dict]):
    """
    通常ブロックをまとめて貼り付ける。
    未対応タイプは静かにスキップ。
    """
    if not blocks:
        return

    blocks_to_append = []
    for b in blocks:
        try:
            new_b = to_creatable_block(b)
            blocks_to_append.append(new_b)
        except ValueError:
            continue

    if not blocks_to_append:
        return

    url = f"https://api.notion.com/v1/blocks/{parent_page_id}/children"
    body = {"children": blocks_to_append}

    res = requests.patch(url, headers=headers, json=body)
    if res.status_code != 200:
        raise RuntimeError(f"Failed to append blocks: {res.status_code} {res.text}")


def create_child_page(parent_page_id: str, title: str) -> str:
    """親ページの下にタイトルを持つ新しい子ページを作る。"""
    url = "https://api.notion.com/v1/pages"
    body = {
        "parent": {"page_id": parent_page_id},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": title}}]}
        },
    }
    res = requests.post(url, headers=headers, json=body)
    if res.status_code != 200:
        raise RuntimeError(f"Failed to create page: {res.status_code} {res.text}")
    return res.json()["id"]


def copy_page_content(src_page_id: str, dst_page_id: str):
    """ページ内部のブロックを全コピー。再帰で child_page も対応。"""
    blocks = get_blocks(src_page_id)

    normal_blocks = []

    for b in blocks:
        if b["type"] == "child_page":
            title = b["child_page"]["title"]
            src_child = b["id"]

            dst_child = create_child_page(dst_page_id, title)
            copy_page_content(src_child, dst_child)
        else:
            normal_blocks.append(b)

    append_blocks(dst_page_id, normal_blocks)


def copy_child_pages(src_parent_id: str, dst_parent_id: str):
    """src_parent の child_page をすべて dst_parent の下にコピー"""
    blocks = get_blocks(src_parent_id)
    child_pages = [b for b in blocks if b["type"] == "child_page"]

    for b in child_pages:
        title = b["child_page"]["title"]
        src_child_id = b["id"]

        dst_child_id = create_child_page(dst_parent_id, title)
        copy_page_content(src_child_id, dst_child_id)

        # ←正常完了ログはこれだけ
        print(f"copy child page {title} done")


if __name__ == "__main__":
    cfg = load_notion_config()

    NOTION_TOKEN = cfg["token"]
    SRC_PARENT_ID = cfg["src_page_id"]
    DST_PARENT_ID = cfg["dst_page_id"]
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    copy_child_pages(SRC_PARENT_ID, DST_PARENT_ID)
