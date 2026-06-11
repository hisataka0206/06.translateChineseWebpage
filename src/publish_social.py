
import os
import sys
import yaml
import logging
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.notion.client import NotionClient
from src.publisher.x_publisher import XPublisher, FALLBACK_ERROR_PREFIX
from src.publisher.linkedin_publisher import LinkedInPublisher
from src.notion.parser import NotionBlockParser
from src.utils.notion_text import make_text_rich_text

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)

def run_social_publish():
    logger.info("Starting Social Auto-Publisher (DB Driven)...")
    load_dotenv()
    config = load_config()
    
    # Setup Notion Client
    notion_api_key = os.getenv("NOTION_TOKEN") or config["notion"]["token"]
    notion = NotionClient(api_key=notion_api_key)
    
    # Initialize Publishers
    x_publisher = XPublisher(config)
    linkedin_publisher = LinkedInPublisher(config)
    
    # Destination DB ID
    dest_id = config["notion"]["destination_parent_id"]
    if "?" in dest_id: dest_id = dest_id.split("?")[0]
    
    logger.info(f"Scanning DB: {dest_id}...")
    
    # Filter: (X post starts with 'Go') OR (LinkedIn post starts with 'Go')
    # Notion API strict filter logic is a bit complex for OR with selects.
    # We can fetch pages where X post is Go OR LinkedIn post is Go.
    # Or just fetch all active pages? No, that's too many.
    # Simple approach: Fetch separately or use compound filter (OR).
    
    filter_criteria = {
        "or": [
            {
                "property": "X post",
                "select": {
                    "equals": "Go"
                }
            },
            {
                "property": "LinkedIn post",
                "select": {
                    "equals": "Go"
                }
            }
        ]
    }
    
    try:
        pages = notion.query_database(dest_id, filter_criteria)
    except Exception as e:
        logger.error(f"Failed to query database: {e}")
        pages = []

    parser = NotionBlockParser()

    if not pages:
        # 記事DBにGoが無くても、インフォグラフィックDBは別途処理する（早期returnしない）
        logger.info("No pages found with 'Go' status for X or LinkedIn (article DB).")
    else:
        # Limit to max 2 pages as requested
        if len(pages) > 2:
            logger.info(f"Found {len(pages)} pages. Limiting to 2.")
            pages = pages[:2]
        else:
            logger.info(f"Found {len(pages)} pages to process.")
    
    for page in pages:
        page_id = page["id"]
        title = parser.get_page_title(page)
        logger.info(f"Processing: {title} ({page_id})")
        
        # 0. Common Data Preparation
        page_url = page.get("public_url")
        if not page_url:
            page_url = page.get("url") or f"https://notion.so/{page_id.replace('-', '')}"
            logger.info(f"Page not published (public_url is null). Using internal URL: {page_url}")
        else:
            logger.info(f"Using Public URL: {page_url}")
        
        props_to_update = {}
        
        # --- X Publishing ---
        x_status = page.get("properties", {}).get("X post", {}).get("select")
        if x_status and x_status.get("name") == "Go":
            logger.info(">>> Processing X Post...")
            try:
                # Get/Gen Comment
                existing_comment = ""
                x_comment_prop = page.get("properties", {}).get("X comment", {})
                if x_comment_prop.get("rich_text"):
                    existing_comment = x_comment_prop["rich_text"][0]["plain_text"]

                # 既存コメントは再利用するが、過去のエラー記録（【生成エラー】…）は
                # 「未生成」とみなして再生成を試みる（エラー文をXに投稿しないため）。
                post_text = existing_comment
                gen_failed = False
                if (not post_text) or post_text.startswith(FALLBACK_ERROR_PREFIX):
                    post_text = x_publisher.generate_post_text(title, title)
                    if x_publisher.generation_fell_back:
                        # 生成失敗。無意味な定型文をXに出さず、原因付きエラーを
                        # X comment に記録して本人が気づけるようにし、投稿はスキップする。
                        gen_failed = True
                        err_txt = (f"{FALLBACK_ERROR_PREFIX}{datetime.now():%Y-%m-%d %H:%M} "
                                   f"投稿文の自動生成に失敗。原因: {x_publisher.fallback_reason}")
                        props_to_update["X comment"] = {"rich_text": make_text_rich_text(err_txt)}
                        logger.error(f"X post generation FAILED for '{title}': {x_publisher.fallback_reason}. "
                                     f"Wrote error to Notion X comment, skipping post.")
                        x_publisher._notify_failure(f"title={title!r} reason={x_publisher.fallback_reason}")
                    else:
                        # Queue update to save generated text
                        # rich_text プロパティ 1 セグメント 2000 文字制限への防御。
                        props_to_update["X comment"] = {"rich_text": make_text_rich_text(post_text or "")}

                if gen_failed:
                    # 生成失敗時は X post=Go のまま残し（Doneにしない）、本人が気づいて
                    # 対処できるようにする。x_prompt.yaml修正後の次回実行で再生成・投稿される。
                    logger.info("Skipping X post for this page due to generation failure.")
                else:
                    # インフォグラフィック画像キュー: queue/<page_id>.png があれば画像付きで投稿する
                    # （2レーン運用: 通常投稿=テキスト / 特集インフォグラフィック=画像付き・週1）
                    image_path = None
                    pid_plain = page_id.replace("-", "")
                    for cand in (f"queue/{page_id}.png", f"queue/{pid_plain}.png"):
                        if os.path.exists(cand):
                            image_path = cand
                            break

                    if x_publisher.post(title, page_url, override_text=post_text, image_path=image_path):
                        if image_path:
                            # 投稿済み画像は queue/posted/ へ退避（再添付防止・履歴保全）
                            try:
                                os.makedirs("queue/posted", exist_ok=True)
                                os.rename(image_path, os.path.join("queue/posted", os.path.basename(image_path)))
                            except OSError as e:
                                logger.warning(f"Could not archive queue image: {e}")
                        props_to_update["X post"] = {"select": {"name": "Done"}}
                        logger.info("X Post Successful.")
                    else:
                        logger.error("X Post Failed.")
            except Exception as e:
                logger.error(f"Error processing X post: {e}")

        # --- LinkedIn Publishing ---
        li_status = page.get("properties", {}).get("LinkedIn post", {}).get("select")
        if li_status and li_status.get("name") == "Go":
            logger.info(">>> Processing LinkedIn Post...")
            try:
                # Get/Gen Comment
                existing_comment = ""
                li_comment_prop = page.get("properties", {}).get("LinkedIn comment", {})
                if li_comment_prop.get("rich_text"):
                    existing_comment = li_comment_prop["rich_text"][0]["plain_text"]
                
                post_text = existing_comment
                li_gen_failed = False
                if (not post_text) or post_text.startswith(FALLBACK_ERROR_PREFIX):
                    post_text = linkedin_publisher.generate_post_text(title, title)
                    if linkedin_publisher.generation_fell_back:
                        li_gen_failed = True
                        err_txt = (f"{FALLBACK_ERROR_PREFIX}{datetime.now():%Y-%m-%d %H:%M} "
                                   f"投稿文の自動生成に失敗。原因: {linkedin_publisher.fallback_reason}")
                        props_to_update["LinkedIn comment"] = {"rich_text": make_text_rich_text(err_txt)}
                        logger.error(f"LinkedIn post generation FAILED for '{title}': {linkedin_publisher.fallback_reason}. "
                                     f"Wrote error to Notion LinkedIn comment, skipping post.")
                    else:
                        # Queue update to save generated text
                        # rich_text プロパティ 1 セグメント 2000 文字制限への防御。
                        props_to_update["LinkedIn comment"] = {"rich_text": make_text_rich_text(post_text or "")}

                if li_gen_failed:
                    logger.info("Skipping LinkedIn post for this page due to generation failure.")
                elif linkedin_publisher.post(title, page_url, override_text=post_text):
                    props_to_update["LinkedIn post"] = {"select": {"name": "Done"}}
                    logger.info("LinkedIn Post Successful.")
                else:
                    logger.error("LinkedIn Post Failed.")
            except Exception as e:
                logger.error(f"Error processing LinkedIn post: {e}")

        # --- Update Notion ---
        if props_to_update:
            try:
                notion.update_page_properties(page_id, props_to_update)
                logger.info("Updated Notion properties.")
            except Exception as e:
                logger.error(f"Failed to update Notion: {e}")

    # --- 特集インフォグラフィックレーン（週1） ---
    publish_infographics(notion, x_publisher, parser)

    logger.info("Social publishing cycle completed.")


# 「インフォグラフィック制作」DB（2026-06-05新設・2レーン運用）
# databases.query は data source ID ではなく database ID を要する点に注意
INFOGRAPHIC_DB_ID = "38339f5c65bb4b7093b993d4a72293b5"


def publish_infographics(notion, x_publisher, parser):
    """特集インフォグラフィックレーン: 「インフォグラフィック制作」DBの X post=Go を投稿する。

    通常レーンとの違い:
    - 画像必須（queue/<page_id>.png が無ければ投稿しない）
    - 投稿文必須（X comment が空なら投稿しない。タイトルからの自動生成はしない）
    - 1回の実行で最大1件（週1レーンのため）
    - 最小投稿間隔ガード: 直近の特集インフォグラフィック投稿から MIN_INFOGRAPHIC_GAP_DAYS 未満なら、
      Goが複数あってもこの実行では投稿しない（毎日連投を防ぎ最低3日空ける。本人指示 2026-06-10）
    - 成功時は X post=Done / Status=Posted / Posted date=当日 を記録
    """
    logger.info("Scanning Infographic DB...")
    filter_criteria = {"property": "X post", "select": {"equals": "Go"}}
    try:
        pages = notion.query_database(INFOGRAPHIC_DB_ID, filter_criteria)
    except Exception as e:
        logger.error(f"Failed to query infographic DB: {e}")
        return
    if not pages:
        logger.info("No infographic pages with 'Go'.")
        return

    # --- 最小投稿間隔ガード（本人指示 2026-06-10: 最低3日空ける） ---
    # 直近の特集インフォグラフィック投稿日（Posted date の最大値）を見て、
    # MIN_INFOGRAPHIC_GAP_DAYS 未満しか経っていなければ、この実行はスキップする。
    # cron は毎日回るが、これにより実投稿は最短でも MIN_INFOGRAPHIC_GAP_DAYS 間隔になる。
    # 失敗・スキップした日も翌日以降に自動で再評価されるため取りこぼさない。
    from datetime import date
    MIN_INFOGRAPHIC_GAP_DAYS = 3
    try:
        posted = notion.query_database(
            INFOGRAPHIC_DB_ID,
            {"property": "Posted date", "date": {"is_not_empty": True}})
        last_posted = None
        for pp in posted:
            d = pp.get("properties", {}).get("Posted date", {}).get("date")
            if d and d.get("start"):
                try:
                    dd = date.fromisoformat(d["start"][:10])
                except ValueError:
                    continue
                if last_posted is None or dd > last_posted:
                    last_posted = dd
        if last_posted is not None:
            gap = (date.today() - last_posted).days
            if gap < MIN_INFOGRAPHIC_GAP_DAYS:
                logger.info(
                    f"Infographic spacing guard: last post {last_posted} "
                    f"({gap}d ago) < {MIN_INFOGRAPHIC_GAP_DAYS}d gap. Skip this run.")
                return
    except Exception as e:
        # ガードの判定に失敗しても投稿自体は止めない（フェイルオープン）。
        logger.warning(f"Spacing guard check failed ({e}); proceeding without it.")

    pages = pages[:1]

    for page in pages:
        page_id = page["id"]
        title = parser.get_page_title(page)
        props = page.get("properties", {})

        comment = ""
        if props.get("X comment", {}).get("rich_text"):
            comment = props["X comment"]["rich_text"][0]["plain_text"]
        if not comment:
            logger.error(f"Infographic '{title}': X comment is empty. Skip (投稿文必須).")
            continue

        image_path = None
        pid_plain = page_id.replace("-", "")
        for cand in (f"queue/{page_id}.png", f"queue/{pid_plain}.png"):
            if os.path.exists(cand):
                image_path = cand
                break
        if not image_path:
            logger.error(f"Infographic '{title}': queue image not found. Skip (画像必須).")
            continue

        if x_publisher.post(title, "", override_text=comment, image_path=image_path):
            try:
                os.makedirs("queue/posted", exist_ok=True)
                os.rename(image_path, os.path.join("queue/posted", os.path.basename(image_path)))
            except OSError as e:
                logger.warning(f"Could not archive queue image: {e}")
            from datetime import date
            try:
                notion.update_page_properties(page_id, {
                    "X post": {"select": {"name": "Done"}},
                    "Status": {"select": {"name": "Posted"}},
                    "Posted date": {"date": {"start": date.today().isoformat()}},
                })
            except Exception as e:
                logger.error(f"Posted but failed to update Notion: {e}")
            logger.info(f"Infographic '{title}' posted successfully.")
        else:
            logger.error(f"Infographic '{title}' post failed.")


if __name__ == "__main__":
    run_social_publish()
