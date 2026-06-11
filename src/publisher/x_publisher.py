
import os
import json
import logging
import yaml
import tweepy
from typing import Dict, Any, Optional
from datetime import datetime
from openai import OpenAI

logger = logging.getLogger(__name__)

# 投稿文の自動生成に失敗したときに X comment へ書き込むエラーマーカーの接頭辞。
# 以前は無意味な「【翻訳記事】<タイトル>」を投稿していたが、Xに出す価値がないため廃止し、
# 代わりに原因付きのエラーを残して本人が気づけるようにする。publish_social 側もこの接頭辞で
# 「エラーコメントは再投稿対象にしない／空とみなして再生成する」判定を行う。
FALLBACK_ERROR_PREFIX = "【生成エラー】"

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

        # 投稿文生成がエラーに落ちたかを示すフラグ。
        # generate_post_text() の冒頭で False にリセットし、生成失敗時に True にする。
        self.generation_fell_back = False
        self.fallback_reason: Optional[str] = None

    def _notify_failure(self, message: str):
        """
        投稿文生成がフォールバックに落ちたことを通知する。
        必ず grep しやすいマーカー付きで ERROR ログに残し、
        環境変数 DISCORD_WEBHOOK_URL が設定されていれば Discord にも送る
        （未設定ならログのみ。webhook URL はリポジトリにハードコードしない）。
        """
        logger.error(f"X_POST_FALLBACK_USED: {message}")
        webhook = os.getenv("DISCORD_WEBHOOK_URL")
        if not webhook:
            return
        try:
            import requests
            requests.post(
                webhook,
                json={"content": f"⚠️ X投稿文の自動生成に失敗。投稿はスキップし、Notionの X comment にエラーを記録しました。\n原因: {message}"},
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"Failed to send fallback notification: {e}")

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
        self.generation_fell_back = False
        self.fallback_reason = None
        prompt_path = "config/x_prompt.yaml"
        if not os.path.exists(prompt_path):
            logger.warning(f"{prompt_path} not found.")
            self.generation_fell_back = True
            self.fallback_reason = f"{prompt_path} not found (cwd={os.getcwd()})"
            return f"{FALLBACK_ERROR_PREFIX}{self.fallback_reason}"
            
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
            self.generation_fell_back = True
            self.fallback_reason = str(e)
            return f"{FALLBACK_ERROR_PREFIX}{self.fallback_reason}"

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

    def post(self, page_title: str, page_url: str, content_snippet: str = "", override_text: str = None, image_path: str = None, source_url: str = None):
        """
        Generate text and post to X. If image_path is given, attach it
        (インフォグラフィック等。画像付き投稿はテキストのみの30〜40倍のIMP実績).
        source_url を渡すと、本体ツイートへの返信（スレッド2件目）として
        その公開URLを投稿する。Xは本文に外部リンクを含めるとリーチが落ちるため、
        本文にはURLを入れず出典リンクはスレッドに分離する方針（本人指示 2026-06-12）。
        非公開ページの内部URLは渡さない想定（呼び出し側で public_url のみ渡す）。
        """
        if not self.initialize_client():
            return

        logger.info("Generating X post content...")
        if override_text:
            post_text = override_text
        else:
            post_text = self.generate_post_text(page_title, content_snippet)
            # 生成に失敗した場合は、無意味なエラー文字列をXに出さないため投稿自体をスキップする。
            # 主因は x_prompt.yaml の肥大化によるコンテキスト長超過（2026-06-04〜）。
            if self.generation_fell_back:
                self._notify_failure(
                    f"title={page_title!r} reason={self.fallback_reason}"
                )
                logger.error("Skipping X post: text generation failed (see X comment in Notion for cause).")
                return False

        # CTA絵文字「詳細はこちら👇」はXでスパム判定されIMPを大きく下げるため付与しない
        # （_memory/domains/twitter.md 2026-05-12 発見・ルール2/8違反）。
        # 本文にはURLを入れない（リーチ低下回避）。出典の公開URLは source_url として
        # 本体ツイートへの返信（スレッド2件目）に分離して投稿する。
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
            tweet_id = response.data['id']
            logger.info(f"Posted to X successfully! ID: {tweet_id}")
        except Exception as e:
            logger.error(f"Failed to post to X: {e}")
            return False

        # スレッド2件目（本体への返信）に出典の公開URLを置く。
        # 返信の失敗は本体投稿の成否に影響させない（本体は成功扱いのまま）。
        if source_url:
            try:
                reply_text = f"出典・全文: {source_url}"
                self.client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
                logger.info(f"Posted source URL as reply to {tweet_id}")
            except Exception as e:
                logger.warning(f"Main tweet OK but failed to post source-URL reply: {e}")

        return True
