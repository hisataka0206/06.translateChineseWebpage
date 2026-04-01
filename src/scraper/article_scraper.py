import logging
import httpx
from bs4 import BeautifulSoup, NavigableString, Tag
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ArticleScraper:
    """Scraper to extract text and images from a web article in order"""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def scrape_url(self, url: str) -> List[Dict[str, Any]]:
        """
        Scrape a URL and return a list of parsed elements (text, image, headings).
        
        Returns:
            List of dicts like:
            [{"type": "paragraph", "content": "hello"}, {"type": "image", "url": "..."}]
        """
        logger.info(f"[Scraper] Scraping URL: {url}")
        try:
            with httpx.Client(follow_redirects=True, verify=False) as client:
                response = client.get(url, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                html = response.text
        except httpx.HTTPError as e:
            logger.error(f"[Scraper] Failed to fetch URL {url}: {e}")
            return []
        except Exception as e:
            logger.error(f"[Scraper] Unexpected error fetching {url}: {e}")
            return []

        soup = BeautifulSoup(html, "html.parser")
        
        # 1. Try WeChat main article area
        main_content = soup.find(id="js_content")
        
        # 2. General fallback
        if not main_content:
            main_content = soup.find("article")
            
        # 3. Last fallback
        if not main_content:
            main_content = soup.find("body")

        if not main_content:
            logger.warning(f"[Scraper] Could not find main content area for {url}")
            return []

        raw_elements = self._extract_elements_in_order(main_content)
        return self._consolidate_elements(raw_elements)

    def _extract_elements_in_order(self, element: Any) -> List[Dict[str, Any]]:
        """Recursively extract elements keeping the sequential order."""
        elements = []
        
        if isinstance(element, NavigableString):
            text = element.text.strip()
            if text:
                elements.append({"type": "text", "content": text})
            return elements

        if isinstance(element, Tag):
            # Skip non-content tags
            if element.name in ["script", "style", "nav", "aside", "footer", "iframe", "video", "audio", "button", "input"]:
                return elements
            
            # Extract Image
            if element.name == "img":
                img_url = self._extract_image_url(element)
                if img_url:
                    elements.append({"type": "image", "url": img_url})
                return elements

            # Basic recursion for children
            for child in element.children:
                child_elements = self._extract_elements_in_order(child)
                
                # Apply block formatting based on the parent tag
                if element.name in ["h1", "h2", "h3"]:
                    # Group all text children under this heading type
                    level = element.name[-1]
                    for ce in child_elements:
                        if ce["type"] == "text":
                            ce["type"] = f"heading_{level}"
                        elements.append(ce)
                elif element.name == "li":
                    for ce in child_elements:
                        if ce["type"] == "text":
                            ce["type"] = "bulleted_list_item"
                        elements.append(ce)
                else:
                    elements.extend(child_elements)
                    
        return elements

    def _extract_image_url(self, img_tag: Tag) -> str:
        """Extract image URL giving priority to lazy-loaded data attributes."""
        # WeChat uses data-src, lots of sites use data-original, etc.
        url = img_tag.get("data-src") or img_tag.get("data-original") or img_tag.get("src")
        
        if not url:
            return None
            
        if url.startswith("//"):
            url = "https:" + url
            
        # Allow only absolute URLs for Notion API
        if url.startswith("http"):
            return url
            
        return None

    def _consolidate_elements(self, raw_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Consolidate adjacent text nodes to form paragraphs and remove empties."""
        consolidated = []
        for el in raw_elements:
            # Map bare text to paragraph
            if el["type"] == "text":
                el["type"] = "paragraph"
                
            if not consolidated:
                if el.get("content") or el["type"] == "image":
                    consolidated.append(el)
                continue
                
            last = consolidated[-1]
            # If current and last are both paragraphs, join them
            if last["type"] == "paragraph" and el["type"] == "paragraph":
                if el.get("content"):
                    last["content"] += "\n" + el["content"]
            else:
                if el.get("content") or el["type"] == "image":
                    consolidated.append(el)
                    
        # Trim whitespace from texts
        for el in consolidated:
            if "content" in el and isinstance(el["content"], str):
                el["content"] = el["content"].strip()
                
        return consolidated
