
import os
import json
import logging
import yaml
import tweepy
from typing import Dict, Any, Optional
from datetime import datetime
from openai import OpenAI

logger = logging.getLogger(__name__)

class XPublisher:
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize X Publisher
        Support both OAuth 2.0 (via setup_x_auth) and OAuth 1.0a (via config)
        """
        self.config = config
        self.tokens_path = "config/x_tokens.json"
        
        # Load X credentials
        x_conf = config.get("openai", {})
        
        # OAuth 2.0 (Old way)
        self.client_id = x_conf.get("client_secret_id") 
        self.client_secret = x_conf.get("client_secret")
        
        # OAuth 1.0a (New recommended way)
        self.consumer_key = x_conf.get("consumer_key")
        self.consumer_secret = x_conf.get("consumer_secret")
        self.access_token = x_conf.get("access_token")
        self.access_token_secret = x_conf.get("access_token_secret")
        
        # Load OpenAI for generation
        api_key = x_conf.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=api_key)
        self.model = x_conf.get("model", "gpt-4") # Use same model as translation or gpt-4
        
        self.client: Optional[tweepy.Client] = None
        
    def _load_tokens(self) -> Dict[str, Any]:
        if not os.path.exists(self.tokens_path):
            return None
        try:
            with open(self.tokens_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load X tokens: {e}")
            return None

    def _save_tokens(self, tokens: Dict[str, Any]):
        try:
            with open(self.tokens_path, "w") as f:
                json.dump(tokens, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save refreshed X tokens: {e}")

    def _refresh_tokens(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            oauth2 = tweepy.OAuth2UserHandler(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri="https://twitter.com",
                scope=["tweet.write", "users.read", "offline.access"]
            )
            
            new_token = oauth2.refresh_token(
                "https://api.twitter.com/2/oauth2/token",
                refresh_token=token_data.get("refresh_token")
            )
            self._save_tokens(new_token)
            return new_token
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return None

    def initialize_client(self) -> bool:
        """Initialize Tweepy Client"""
        # Method 1: OAuth 1.0a (Recommended for Bots)
        if self.consumer_key and self.consumer_secret and self.access_token and self.access_token_secret:
            try:
                self.client = tweepy.Client(
                    consumer_key=self.consumer_key,
                    consumer_secret=self.consumer_secret,
                    access_token=self.access_token,
                    access_token_secret=self.access_token_secret
                )
                logger.info("Initialized X Client with OAuth 1.0a")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize X Client (OAuth 1.0a): {e}")
                return False

        # Method 2: OAuth 2.0 User Context (Legacy flow for this app)
        if self.client_id and self.client_secret:
            token_data = self._load_tokens()
            if not token_data:
                 logger.warning(f"X Tokens not found at {self.tokens_path}. Please use OAuth 1.0a keys in config or run setup_x_auth.py")
                 return False
                
            if "expires_at" in token_data:
                expires_at = token_data["expires_at"]
                if datetime.now().timestamp() > (expires_at - 60):
                    logger.info("X Access Token expired, refreshing...")
                    token_data = self._refresh_tokens(token_data)
                    if not token_data:
                        return False
            
            try:
                # Use Bearer Token for OAuth 2.0 User Context
                self.client = tweepy.Client(bearer_token=token_data["access_token"])
                return True
            except Exception as e:
                 logger.error(f"Failed to initialize X Client (OAuth 2.0): {e}")
                 return False

        logger.error("No valid X credentials found in config.")
        return False

    def generate_post_text(self, title: str, content_summary: str) -> str:
        """Generate post text using LLM and prompt file"""
        prompt_path = "config/x_prompt.yaml"
        if not os.path.exists(prompt_path):
            logger.warning(f"{prompt_path} not found.")
            return f"【翻訳記事】{title}" # Fallback
            
        try:
        try:
            with open(prompt_path, "r") as f:
                prompt_content = f.read()
            
            # Initial messages
            messages = [
                {"role": "system", "content": prompt_content},
                {"role": "user", "content": f"Title: {title}\n\nSummary/Content: {content_summary}"}
            ]
            
            max_retries = 3
            for attempt in range(max_retries):
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=200 
                )
                generated_text = response.choices[0].message.content.strip()
                
                # Check length (120 chars)
                if len(generated_text) <= 120:
                    return generated_text
                
                logger.warning(f"Generated text too long ({len(generated_text)} chars). Retrying ({attempt + 1}/{max_retries})...")
                
                # Add history for context and ask to shorten
                messages.append({"role": "assistant", "content": generated_text})
                messages.append({"role": "user", "content": "The text is too long. It must be strictly under 120 characters. Please rewrite it shorter."})
            
            logger.error("Failed to generate text under 120 characters after retries.")
            return generated_text # Return best effort
            
        except Exception as e:
            logger.error(f"Failed to generate X post text: {e}")
            return f"【翻訳記事】{title}"

    def post(self, page_title: str, page_url: str, content_snippet: str = "", override_text: str = None):
        """
        Generate text and post to X
        """
        if not self.initialize_client():
            return
            
        logger.info("Generating X post content...")
        if override_text:
            post_text = override_text
        else:
            post_text = self.generate_post_text(page_title, content_snippet)
        
        final_text = f"{post_text}\n\n詳細はこちら👇\n{page_url}"
        
        try:
            logger.info(f"Posting to X:\n{final_text}")
            response = self.client.create_tweet(text=final_text)
            logger.info(f"Posted to X successfully! ID: {response.data['id']}")
            return True
        except Exception as e:
            logger.error(f"Failed to post to X: {e}")
            return False
