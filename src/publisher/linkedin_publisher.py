
import os
import logging
import requests
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class LinkedInPublisher:
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LinkedIn Publisher
        """
        self.config = config
        self.linkedin_conf = config.get("linkedin", {})
        
        # Credentials
        self.access_token = os.getenv("LINKEDIN_ACCESS_TOKEN") or self.linkedin_conf.get("access_token")
        self.author_urn = os.getenv("LINKEDIN_AUTHOR_URN") or self.linkedin_conf.get("author_urn") # e.g. urn:li:person:12345
        
        # OpenAI for text generation (reuses X prompt or new one)
        api_key = os.getenv("OPENAI_API_KEY") or config.get("openai", {}).get("api_key")
        self.openai_client = OpenAI(api_key=api_key)
        self.model = config.get("models", {}).get("x_post", "gpt-4") # Reusing x_post model for now

    def generate_post_text(self, title: str, content_summary: str) -> str:
        """
        Generate post text using LLM.
        For now, reusing X prompt structure but maybe allow longer text?
        LinkedIn allows 3000 chars, so we can be more verbose if needed.
        """
        # TODO: Separate prompt for LinkedIn if needed. For now reusing the logic but maybe different max tokens.
        prompt_path = "config/linkedin_prompt.yaml"
        if not os.path.exists(prompt_path):
            prompt_path = "config/x_prompt.yaml" # Fallback to X prompt

        if not os.path.exists(prompt_path):
             return f"【翻訳記事】{title}"

        try:
            with open(prompt_path, "r") as f:
                prompt_content = f.read()
            
            messages = [
                {"role": "system", "content": prompt_content},
                {"role": "user", "content": f"Title: {title}\n\nSummary/Content: {content_summary}"}
            ]
            
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500 # Allow more for LinkedIn
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate LinkedIn post text: {e}")
            return f"【翻訳記事】{title}"

    def post(self, page_title: str, page_url: str, content_snippet: str = "", override_text: str = None) -> bool:
        """
        Post to LinkedIn
        """
        if not self.access_token or not self.author_urn:
            logger.error("LinkedIn credentials (ACCESS_TOKEN or AUTHOR_URN) not set.")
            return False

        logger.info("Generating LinkedIn post content...")
        if override_text:
            post_text = override_text
        else:
            post_text = self.generate_post_text(page_title, content_snippet)
            
        full_text = f"{post_text}\n\n詳細はこちら👇\n{page_url}"

        # API Endpoint
        api_url = "https://api.linkedin.com/v2/ugcPosts"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        # UGC Post Body
        payload = {
            "author": self.author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": full_text
                    },
                    "shareMediaCategory": "ARTICLE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {
                                "text": page_title
                            },
                            "originalUrl": page_url,
                             "title": {
                                "text": page_title
                            }
                        }
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        try:
            logger.info(f"Posting to LinkedIn:\n{full_text}")
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"Posted to LinkedIn successfully! ID: {response.json().get('id')}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to post to LinkedIn: {e}")
            if response is not None:
                logger.error(f"Response: {response.text}")
            return False
