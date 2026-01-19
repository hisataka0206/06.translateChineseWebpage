
import pytest
from unittest.mock import Mock, MagicMock
from src.publisher.notion_publisher import NotionPublisher
from src.translation.translator import TextTranslator

class TestEditingFeatures:
    @pytest.fixture
    def mock_dependencies(self):
        notion_client = Mock()
        text_translator = Mock(spec=TextTranslator)
        image_translator = Mock()
        return notion_client, text_translator, image_translator

    @pytest.fixture
    def publisher(self, mock_dependencies):
        notion_client, text_translator, image_translator = mock_dependencies
        return NotionPublisher(notion_client, text_translator, image_translator)

    def test_clean_text_basic(self, publisher):
        """Test basic text cleaning"""
        original = "Important content"
        cleaned = publisher._clean_text(original)
        assert cleaned == "Important content"

    def test_clean_text_removes_unwanted(self, publisher):
        """Test removal of unwanted phrases"""
        original = "点击蓝字 关注我们 Content"
        cleaned = publisher._clean_text(original)
        assert cleaned == "Content"

        original = "Prefix 关注公众号，点击公众号主页右上角“ · · · ”，设置星标，实时关注人形机器人新鲜的行业动态与知识！ Suffix"
        cleaned = publisher._clean_text(original)
        assert cleaned == "Prefix  Suffix"

    def test_clean_text_returns_none_if_empty(self, publisher):
        """Test that None is returned if text becomes empty"""
        original = "点击蓝字 关注我们"
        cleaned = publisher._clean_text(original)
        assert cleaned is None

    def test_auto_title_generation(self, publisher, mock_dependencies):
        """Test title generation when original title is Untitled"""
        notion_client, text_translator, _ = mock_dependencies

        # Setup mock responses
        notion_client.get_page.return_value = {"id": "page_id"}
        notion_client.get_page_blocks.return_value = [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "Content for title generation"}]
                }
            }
        ]
        # Simulate clean checkout (not translated yet)
        notion_client.is_already_translated.return_value = False
        
        # Simulate creating page response
        notion_client.create_page.return_value = {"id": "new_page_id"}

        # Mock parser behavior (easier than mocking the parser object itself as it's instantiated inside)
        # However, parser is a real object inside publisher.
        # We need to manually set the parser mock or rely on its real behavior if it's simple.
        # NotionBlockParser is simple, let's rely on real one but feed it correct structure?
        # Actually it might be safer to patch the parser method "get_page_title"
        
        publisher.parser = Mock()
        publisher.parser.get_page_title.return_value = "Untitled"
        publisher.parser.extract_text_from_block.return_value = "Content for title generation"

        # Mock text translator
        text_translator.generate_title.return_value = "Generated Title"
        text_translator.translate.return_value = "Translated Content"

        # Run method
        result = publisher.translate_and_publish_page("source_id", "dest_id", "processed_id")

        # Verify
        text_translator.generate_title.assert_called_once()
        assert result["original_title"] == "(Auto-Generated) Generated Title"
        assert result["translated_title"] == "Generated Title"
        notion_client.move_page.assert_called_once_with(page_id="source_id", target_parent_id="processed_id")
        
        # Verify create_page calls
        _, kwargs = notion_client.create_page.call_args
        assert kwargs["title"] == "Generated Title"

    def test_no_auto_title_if_exists(self, publisher, mock_dependencies):
        """Test that title generation is skipped if title exists"""
        notion_client, text_translator, _ = mock_dependencies

        notion_client.get_page.return_value = {"id": "page_id"}
        notion_client.create_page.return_value = {"id": "new_page_id"}
        notion_client.get_page_blocks.return_value = []

        publisher.parser = Mock()
        publisher.parser.get_page_title.return_value = "Existing Title"

        text_translator.translate.return_value = "Translated Title"

        # Run method
        result = publisher.translate_and_publish_page("source_id", "dest_id", "processed_id")

        # Verify
        text_translator.generate_title.assert_not_called()
        assert result["original_title"] == "Existing Title"
        notion_client.move_page.assert_called_once_with(page_id="source_id", target_parent_id="processed_id")
