
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
        x_conf = config.get("x", {})
        
        
        # OAuth 2.0 (Old way)
        self.client_id = os.getenv("X_CLIENT_SECRET_ID") or x_conf.get("client_secret_id")
        self.client_secret = os.getenv("X_CLIENT_SECRET") or x_conf.get("client_secret")
        
        # OAuth 1.0a (New recommended way)
        self.consumer_key = os.getenv("X_CONSUMER_KEY") or x_conf.get("consumer_key")
        self.consumer_secret = os.getenv("X_CONSUMER_SECRET") or x_conf.get("consumer_secret")
        self.access_token = os.getenv("X_ACCESS_TOKEN") or x_conf.get("access_token")
        self.access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET") or x_conf.get("access_token_secret")
        
        # Load OpenAI for generation
        api_key = os.getenv("OPENAI_API_KEY") or config.get("openai", {}).get("api_key")
        self.openai_client = OpenAI(api_key=api_key)
        self.model = config.get("models", {}).get("x_post", "gpt-4")
        
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

    def _upload_media(self, image_path: str):
        """Upload an image via API v1.1 (required for media). Needs OAuth 1.0a keys."""
        if not (self.consumer_key and self.consumer_secret and self.access_token and self.access_token_secret):
            raise RuntimeError("Media upload requires OAuth 1.0a credentials")
        auth = tweepy.OAuth1UserHandler(
            self.consumer_key, self.consumer_secret,
            self.access_token, self.access_token_secret)
        api = tweepy.API(auth)
        media = api.media_upload(image_path)
        return media.media_id

    def post(self, page_title: str, page_url: str, content_snippet: str = "", override_text: str = None, image_path: str = None):
        """
        Generate text and post to X. If image_path is given, attach it
        (インフォグラフィック等。画像付き投稿はテキストのみの30〜40倍のIMP実績).
        """
        if not self.initialize_client():
            return

        logger.info("Generating X post content...")
        if override_text:
            post_text = override_text
        else:
            post_text = self.generate_post_text(page_title, content_snippet)

        # CTA絵文字「詳細はこちら👇」はXでスパム判定されIMPを大きく下げるため付与しない
        # （_memory/domains/twitter.md 2026-05-12 発見・ルール2/8違反）。
        # 本文のみを投稿し、リンク誘導は行わない方針。URLを残したい場合は
        # final_text = f"{post_text}\n\n{page_url}" に変更する。
        final_text = post_text

        media_ids = None
        if image_path:
            if os.path.exists(image_path):
                try:
                    media_ids = [self._upload_media(image_path)]
                    logger.info(f"Media uploaded: {image_path}")
                except Exception as e:
                    # 画像アップロード失敗時はテキストのみで投稿せず中断する
                    # （インフォグラフィック投稿で画像が落ちると意味がないため）
                    logger.error(f"Media upload failed, aborting post: {e}")
                    return False
            else:
                logger.error(f"image_path not found, aborting post: {image_path}")
                return False

        try:
            logger.info(f"Posting to X (media={'yes' if media_ids else 'no'}):\n{final_text}")
            response = self.client.create_tweet(text=final_text, media_ids=media_ids)
            logger.info(f"Posted to X successfully! ID: {response.data['id']}")
            return True
        except Exception as e:
            logger.error(f"Failed to post to X: {e}")
            return False
