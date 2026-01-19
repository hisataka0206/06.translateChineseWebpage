"""
Main entry point for Chinese to Japanese Translation Service
Translates Chinese Notion pages to Japanese with image text support
"""

import os
import sys
import yaml
import logging
from pathlib import Path
from dotenv import load_dotenv
from colorlog import ColoredFormatter

from src.notion.client import NotionClient
from src.translation.translator import TextTranslator
from src.translation.image_translator import ImageTextTranslator
from src.publisher.notion_publisher import NotionPublisher


def setup_logging(config: dict) -> logging.Logger:
    """
    Setup logging with color formatting

    Args:
        config: Configuration dictionary

    Returns:
        Configured logger
    """
    log_config = config.get("logging", {})
    log_level = log_config.get("level", "INFO")
    log_file = log_config.get("log_file", "logs/translation.log")
    console_output = log_config.get("console_output", True)

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # Console handler with colors
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level))

        formatter = ColoredFormatter(
            "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
            datefmt=None,
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level))
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def load_config(config_path: str = "config/config.yaml") -> dict:
    """
    Load configuration from YAML file

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_prompt_template(prompt_file: str) -> str:
    """
    Load custom prompt template from file

    Args:
        prompt_file: Path to prompt template file

    Returns:
        Prompt template string
    """
    if not os.path.exists(prompt_file):
        return None

    with open(prompt_file, 'r', encoding='utf-8') as f:
        return f.read()


def main():
    """Main execution function"""
    try:
        # Load environment variables
        load_dotenv()

        # Load configuration
        config = load_config()

        # Setup logging
        logger = setup_logging(config)
        logger.info("=" * 60)
        logger.info("Starting Chinese to Japanese Translation Service")
        logger.info("=" * 60)

        # Get API keys
        # Notion API key is directly in config
        notion_api_key = config["notion"].get("token")

        # OpenAI API key: prioritize config, then env var
        openai_api_key = config["openai"].get("api_key") or os.getenv(config["openai"]["api_key_env"])

        if not notion_api_key:
            logger.error("Missing Notion API token in config.yaml")
            sys.exit(1)

        if not openai_api_key:
            logger.error("Missing OpenAI API key in config.yaml or environment variable")
            sys.exit(1)

        # Initialize clients
        logger.info("Initializing Notion client...")
        notion_client = NotionClient(api_key=notion_api_key)

        # Load custom prompt if available
        prompt_file = config.get("translation", {}).get("prompt_file")
        custom_prompt = None
        if prompt_file:
            logger.info(f"Loading custom prompt from: {prompt_file}")
            # Ensure path is relative to repo root if possible or absolute
            prompt_path = prompt_file
            if not os.path.exists(prompt_path):
                 # Try relative to main.py dir? Or assumes cwd is root.
                 pass 
            custom_prompt = load_prompt_template(prompt_path)

        logger.info("Initializing translation services...")
        # Pass API key explicitly
        text_translator = TextTranslator(api_key=openai_api_key, prompt_template=custom_prompt)
        image_translator = ImageTextTranslator(api_key=openai_api_key)

        # Initialize publisher
        publisher = NotionPublisher(
            notion_client=notion_client,
            text_translator=text_translator,
            image_translator=image_translator
        )

        # Get source and destination from config
        source_page_ids = config["notion"]["source_page_ids"]
        destination_parent_id = config["notion"]["destination_parent_id"]
        processed_source_parent_id = config["notion"].get("processed_source_parent_id")
        
        # Get skip_translation flag
        skip_translation = config["openai"].get("skip_translation", False)

        if not processed_source_parent_id or processed_source_parent_id == "replace-with-actual-page-id":
             logger.warning("Warning: 'processed_source_parent_id' is not configured correctly.")
        
        logger.info(f"Found {len(source_page_ids)} parent pages to process")
        logger.info(f"Destination parent ID: {destination_parent_id}")
        logger.info(f"Processed pages destination: {processed_source_parent_id}")
        logger.info(f"Skip Translation Mode: {skip_translation}")

        # Discover all child pages from parent pages
        all_pages_to_translate = []
        for parent_id in source_page_ids:
            # Clean parent_id if it has query params
            if "?" in parent_id:
                 parent_id = parent_id.split("?")[0]
            
            logger.info(f"\nDiscovering child pages from parent: {parent_id}")
            try:
                child_ids = notion_client.get_child_page_ids(parent_id)
                all_pages_to_translate.extend(child_ids)
            except Exception as e:
                logger.error(f"Failed to get child pages for {parent_id}: {e}")

        logger.info(f"\n{'='*60}")
        logger.info(f"Total child pages to process: {len(all_pages_to_translate)}")
        logger.info(f"{'='*60}\n")

        # Process each child page
        results = []
        for i, source_page_id in enumerate(all_pages_to_translate, 1):
            logger.info(f"\n[{i}/{len(all_pages_to_translate)}] Processing page: {source_page_id}")

            try:
                result = publisher.translate_and_publish_page(
                    source_page_id=source_page_id,
                    destination_parent_id=destination_parent_id,
                    processed_parent_id=processed_source_parent_id,
                    skip_translation=skip_translation
                )
                results.append(result)

                if result["status"] == "success":
                    if result.get("action") == "move_only":
                         logger.info(f"✓ Successfully moved: {source_page_id} to {result.get('destination_parent_id')}")
                    else:
                         logger.info(f"✓ Successfully translated: {result['original_title']}")
                         logger.info(f"  New page ID: {result['new_page_id']}")
                elif result["status"] == "skipped":
                    logger.info(f"⊘ Skipped (already done): {source_page_id}")

            except Exception as e:
                logger.error(f"✗ Error processing page {source_page_id}: {e}")
                results.append({
                    "status": "error",
                    "source_page_id": source_page_id,
                    "error": str(e)
                })

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Translation Summary")
        logger.info("=" * 60)

        success_count = sum(1 for r in results if r["status"] == "success")
        skipped_count = sum(1 for r in results if r["status"] == "skipped")
        error_count = sum(1 for r in results if r["status"] == "error")

        logger.info(f"Total pages: {len(results)}")
        logger.info(f"✓ Successfully translated: {success_count}")
        logger.info(f"⊘ Skipped (already done): {skipped_count}")
        logger.info(f"✗ Errors: {error_count}")

        if error_count > 0:
            logger.warning("\nPages with errors:")
            for result in results:
                if result["status"] == "error":
                    logger.warning(f"  - {result['source_page_id']}: {result.get('error', 'Unknown error')}")

        logger.info("\nTranslation service completed!")

    except KeyboardInterrupt:
        logger.warning("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\nFatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
