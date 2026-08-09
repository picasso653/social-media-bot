# Next Phases — Detailed Implementation Guide

> This document is designed so anyone can pick up and continue the project.
> Each phase lists: **goal**, **inputs needed**, **step-by-step tasks**, **expected output**, and **acceptance criteria**.

---

## Phase 1: Project Scaffolding & Foundation

**Goal:** Create the entire project skeleton — every file exists and the app boots up in Docker with a database. No real logic yet, just plumbing.

**Inputs needed:** None (greenfield).

### Step-by-Step

#### 1.1 Create `requirements.txt`

List ALL Python dependencies. Split into logical groups:

```
# Web Framework
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.9.0
pydantic-settings==2.5.0

# Database
sqlalchemy==2.0.35
asyncpg==0.29.0
alembic==1.13.0
psycopg2-binary==2.9.9

# Cache & Queue
redis==5.1.0
celery==5.4.0

# Telegram
python-telegram-bot==21.5

# Social Media APIs
tweepy==4.14.0
requests==2.32.0
requests-oauthlib==2.0.0

# Security
cryptography==43.0.0
python-jose[cryptography]==3.3.0

# Utilities
python-multipart==0.0.9
Pillow==10.4.0
httpx==0.27.0
aiofiles==24.1.0

# Testing
pytest==8.3.0
pytest-asyncio==0.24.0
pytest-mock==3.14.0
httpx (for TestClient)

# Development
python-dotenv==1.0.1
```

#### 1.2 Create `.env.example`

```
# Application
APP_NAME=SocialMediaBot
APP_ENV=development
APP_DEBUG=true
SECRET_KEY=change-me-to-a-random-string
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/socialmedia
REDIS_URL=redis://redis:6379/0

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_WEBHOOK_URL=https://your-domain.com/api/v1/telegram/webhook

# X (Twitter)
X_API_KEY=your_api_key
X_API_KEY_SECRET=your_api_key_secret
X_CALLBACK_URL=https://your-domain.com/api/v1/auth/x/callback

# TikTok
TIKTOK_CLIENT_KEY=your_client_key
TIKTOK_CLIENT_SECRET=your_client_secret
TIKTOK_CALLBACK_URL=https://your-domain.com/api/v1/auth/tiktok/callback

# Instagram (Facebook)
INSTAGRAM_APP_ID=your_fb_app_id
INSTAGRAM_APP_SECRET=your_fb_app_secret
INSTAGRAM_CALLBACK_URL=https://your-domain.com/api/v1/auth/instagram/callback

# Token Encryption
TOKEN_ENCRYPTION_KEY=generate-with-python-cryptography
```

#### 1.3 Create `.gitignore`

Standard Python + IDE ignores. Include `.env` (CRITICAL — never commit secrets).

#### 1.4 Create `src/config.py`

Use `pydantic-settings` to read from `.env`. Create a `Settings` class that validates all config values at startup:

```python
class Settings(BaseSettings):
    # App
    app_name: str = "SocialMediaBot"
    app_env: str = "development"
    app_debug: bool = True
    secret_key: str
    
    # Database
    database_url: str
    
    # Redis
    redis_url: str
    
    # Telegram
    telegram_bot_token: str
    telegram_webhook_url: str = ""
    
    # Platform API keys (loaded lazily — only needed when platform is used)
    x_api_key: str = ""
    x_api_key_secret: str = ""
    x_callback_url: str = ""
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_callback_url: str = ""
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_callback_url: str = ""
    
    # Security
    token_encryption_key: str
    
    model_config = SettingsConfigDict(env_file=".env")
```

#### 1.5 Create `src/main.py`

The FastAPI application entry point. Should:

- Create FastAPI app with title, description, version
- Add CORS middleware (allow all origins for dev)
- Include routers from `src/api/routes/` (at this stage, just a health endpoint)
- Add startup event: create database tables, verify Redis connection
- Add shutdown event: close connections
- Return a health-check at `GET /health`

```python
app = FastAPI(title="Social Media Bot", version="0.1.0")

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

app.include_router(telegram.router, prefix="/api/v1/telegram")
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(posts.router, prefix="/api/v1/posts")
```

#### 1.6 Create Database Models

All four models as defined in the schema:

**`src/models/__init__.py`** — Export all models so Alembic can discover them.

**`src/models/user.py`:**
```python
class User(Base):
    __tablename__ = "users"
    id = Column(UUID, primary_key=True, default=uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)
    # relationship: social_accounts
```

**`src/models/social_account.py`:**
```python
class SocialAccount(Base):
    __tablename__ = "social_accounts"
    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    platform = Column(String(50), nullable=False)  # 'x', 'tiktok', 'instagram'
    platform_user_id = Column(String(255), nullable=True)
    access_token = Column(Text, nullable=False)  # ENCRYPTED
    refresh_token = Column(Text, nullable=True)  # ENCRYPTED
    token_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    # UniqueConstraint: (user_id, platform)
```

**`src/models/post.py`:**
```python
class Post(Base):
    __tablename__ = "posts"
    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    content_type = Column(String(20), nullable=False)  # 'text', 'image', 'video'
    text_content = Column(Text, nullable=True)
    media_url = Column(Text, nullable=True)  # S3/local path to media file
    status = Column(String(20), default="pending")  # pending, processing, posted, partial, failed
    created_at = Column(DateTime, default=func.now())
    posted_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    # relationship: post_platforms
```

**`src/models/post_platform.py`:**
```python
class PostPlatform(Base):
    __tablename__ = "post_platforms"
    id = Column(UUID, primary_key=True, default=uuid4)
    post_id = Column(UUID, ForeignKey("posts.id"), nullable=False, index=True)
    account_id = Column(UUID, ForeignKey("social_accounts.id"), nullable=False)
    platform = Column(String(50), nullable=False)
    platform_post_id = Column(String(255), nullable=True)
    platform_post_url = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending, posted, failed
    posted_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
```

#### 1.7 Create `src/platforms/base.py` — Abstract Adapter

The adapter interface. Every platform adapter MUST implement these methods:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class PostResult:
    success: bool
    platform_post_id: Optional[str] = None
    platform_post_url: Optional[str] = None
    error_message: Optional[str] = None

@dataclass
class PlatformInfo:
    name: str           # 'x', 'tiktok', 'instagram'
    display_name: str    # 'X (Twitter)', 'TikTok', 'Instagram'
    supports_text: bool
    supports_image: bool
    supports_video: bool
    max_text_length: int
    max_image_count: int

class BasePlatformAdapter(ABC):
    @abstractmethod
    async def authenticate(self, code: str) -> dict: ...
    
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> dict: ...
    
    @abstractmethod
    async def post_text(self, access_token: str, content: str) -> PostResult: ...
    
    @abstractmethod
    async def post_image(self, access_token: str, image_data: bytes, caption: str) -> PostResult: ...
    
    @abstractmethod
    async def post_video(self, access_token: str, video_data: bytes, caption: str) -> PostResult: ...
    
    @abstractmethod
    def get_platform_info(self) -> PlatformInfo: ...
    
    @abstractmethod
    def get_auth_url(self, state: str) -> str: ...
```

#### 1.8 Create `src/platforms/registry.py`

A registry that maps platform names → adapter instances. The PostService uses this to route posts.

```python
from src.platforms.base import BasePlatformAdapter

class PlatformRegistry:
    _adapters: dict[str, BasePlatformAdapter] = {}
    
    @classmethod
    def register(cls, name: str, adapter: BasePlatformAdapter):
        cls._adapters[name] = adapter
    
    @classmethod
    def get(cls, name: str) -> BasePlatformAdapter:
        if name not in cls._adapters:
            raise ValueError(f"Unknown platform: {name}")
        return cls._adapters[name]
    
    @classmethod
    def get_all(cls) -> dict[str, BasePlatformAdapter]:
        return cls._adapters.copy()
    
    @classmethod
    def get_names(cls) -> list[str]:
        return list(cls._adapters.keys())
```

Adapters register themselves at import time (in their own `__init__`):

```python
# At bottom of x_adapter.py
PlatformRegistry.register("x", XAdapter())
```

#### 1.9 Create Platform Adapter Scaffolds

Each adapter file (`x_adapter.py`, `tiktok_adapter.py`, `instagram_adapter.py`) should:

1. Inherit from `BasePlatformAdapter`
2. Implement all abstract methods
3. **NOT contain real API calls yet** — raise `NotImplementedError` or return fake `PostResult(success=True)` for now
4. Register itself in the `PlatformRegistry`

This lets us test the routing logic without needing real API keys.

#### 1.10 Create API Routes

**`src/api/routes/telegram.py`:**
- `POST /webhook` — receives Telegram update, validates secret token, returns 200 OK immediately (actual processing delegated to background task)

**`src/api/routes/auth.py`:**
- `GET /{platform}/login` — returns OAuth authorization URL (call adapter's `get_auth_url()`)
- `GET /{platform}/callback` — handles OAuth callback, saves tokens to DB

**`src/api/routes/posts.py`:**
- `POST /` — create a post (receives user_id, content, media, target platforms)
- `GET /history` — get user's post history with pagination
- `GET /{post_id}/status` — get status of a specific post across platforms

All routes are empty shells at this stage — they just validate input and return mock data.

#### 1.11 Create `Dockerfile`

Multi-stage build for Python:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

#### 1.12 Create `docker-compose.yml`

Three services: `app`, `db` (PostgreSQL), `redis`:

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - .:/app  # Hot reload in dev
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
  
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: socialmedia
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

#### 1.13 Initialize Alembic

```bash
alembic init migrations
# Then edit migrations/env.py to use our SQLAlchemy models
```

#### 1.14 Create Repository Layer

**`src/repositories/base.py`:**
```python
class BaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add(self, instance):
        self.session.add(instance)
        await self.session.flush()
        return instance
    
    async def delete(self, instance):
        await self.session.delete(instance)
        await self.session.flush()
```

Specific repositories (`user_repository.py`, `account_repository.py`, `post_repository.py`) extend this with domain-specific queries.

#### 1.15 Create Service Layer Scaffolds

**`src/services/post_service.py`:**
- `create_post()` — takes user_id, content, media, platforms list → creates Post record → iterates platforms → calls each adapter → creates PostPlatform records → returns results
- `get_post_status()` — queries PostPlatform records

**`src/services/auth_service.py`:**
- `start_oauth()` — generates state, returns auth URL
- `complete_oauth()` — exchanges code for tokens, saves to DB
- `disconnect_platform()` — deletes SocialAccount record
- `get_connected_platforms()` — queries active SocialAccounts for user

**`src/services/telegram_service.py`:**
- `handle_message()` — parses Telegram message, routes to PostService
- `handle_command()` — parses Telegram commands (/start, /connect, /status, etc.)

#### 1.16 Create Utility Files

**`src/utils/security.py`:**
- `encrypt_token(token: str) -> str` — AES-GCM encrypt a token using `TOKEN_ENCRYPTION_KEY`
- `decrypt_token(encrypted: str) -> str` — decrypt
- `generate_state() -> str` — random state for OAuth CSRF protection

**`src/utils/text_formatter.py`:**
- `truncate_text(text: str, max_length: int) -> str` — truncate with ellipsis
- `format_for_platform(text: str, platform: str) -> str` — platform-specific formatting

**`src/utils/image_processor.py`:**
- `resize_image(image_data: bytes, width: int, height: int) -> bytes` — resize using Pillow
- `get_platform_image_requirements(platform: str) -> dict` — return required dimensions

#### 1.17 Create Test Infrastructure

**`tests/conftest.py`:**
- In-memory SQLite or test PostgreSQL fixtures
- Async client fixture for FastAPI TestClient
- Mock settings/environment

**`tests/test_health.py`:**
- Verify `GET /health` returns 200 with `{"status": "ok"}`

#### 1.18 Create `scripts/setup.sh`

One-click setup for development:
```bash
#!/bin/bash
cp .env.example .env
echo "Edit .env with your API keys, then run: docker-compose up"
```

---

### Phase 1 Completion Checklist

- [ ] `docker-compose up` starts without errors
- [ ] `GET /health` returns 200 OK
- [ ] Database tables created automatically (or via migration)
- [ ] All four models exist and have correct relationships
- [ ] All three platform adapters exist (empty shells) and are registered
- [ ] All API routes exist (return mock responses)
- [ ] `pytest` runs and passes the health-check test
- [ ] `.env.example` contains all required variables

---

## Phase 2: Telegram Bot Integration

**Goal:** Users can interact with the bot via Telegram. They can type messages, send photos, and use commands. The bot processes content and routes it to the PostService.

**Inputs needed:**
- Telegram Bot Token (from @BotFather)
- A public URL for webhook (use ngrok in development)
- Phase 1 completed (app running, DB connected)

### Step-by-Step

#### 2.1 Implement Command Handlers

Create a proper command dispatcher using `python-telegram-bot`:

**Commands to implement:**
- `/start` — Welcome message explaining what the bot does
  - Show inline keyboard with quick actions: [New Post] [My Accounts] [Help]
- `/help` — Show all available commands with examples
- `/connect <platform>` — Start OAuth flow for a platform
  - Valid platforms: `x`, `tiktok`, `instagram`
  - Returns an authorization link
- `/disconnect <platform>` — Remove a platform connection
  - Confirmation prompt before disconnecting
- `/status` — Show which platforms are connected
  - Format: "✅ X (Twitter) — Connected as @username"
- `/history` — Show recent posts with their status across platforms

**Implementation pattern:**
```python
from telegram.ext import Application, CommandHandler, MessageHandler, filters

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
    Welcome to Social Media Bot!
    
    Send me text or a photo to post to your connected accounts.
    Use /help to see all commands.
    """
    keyboard = [
        [InlineKeyboardButton("📝 New Post", callback_data="new_post")],
        [InlineKeyboardButton("🔗 My Accounts", callback_data="status")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
```

#### 2.2 Implement Message Handler (Text)

When a user sends plain text:
1. Check if text looks like a command (starts with `/`) → delegate to command handler
2. Otherwise, treat it as a post:
   - Parse for platform hashtags: `#x #tiktok #instagram`
   - If hashtags found → post only to those platforms
   - If no hashtags → post to ALL connected platforms
   - If no platforms connected → tell user to connect first
3. Call `PostService.create_post()` with the content
4. Send confirmation: "Posted to X ✅, TikTok ✅"

#### 2.3 Implement Photo + Caption Handler

When a user sends a photo with a caption:
1. Download the photo from Telegram's servers (Telegram provides a `file_id`)
2. Extract caption text (same hashtag logic as text handler)
3. Call `PostService.create_post()` with image + caption
4. Send confirmation with preview thumbnail

```python
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get the largest photo version
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_data = await file.download_as_bytearray()
    
    caption = update.message.caption or ""
    # Extract platform targets from caption
    platforms = extract_platforms_from_text(caption)
    clean_caption = remove_platform_tags(caption)
    
    # Submit to PostService
    result = await post_service.create_post(
        user_id=user.id,
        content=clean_caption,
        media=bytes(image_data),
        platforms=platforms
    )
    
    await update.message.reply_text(format_post_result(result))
```

#### 2.4 Implement Callback Query Handler (Inline Buttons)

Handle button presses from inline keyboards:
- "Connect X" → start OAuth for X
- "Disconnect X" → confirm then disconnect
- "New Post" → prompt user to send content
- Platform selection toggles

#### 2.5 Implement Webhook Setup

In `src/main.py`, add startup logic:
```python
@app.on_event("startup")
async def set_telegram_webhook():
    if settings.telegram_webhook_url:
        await bot.set_webhook(settings.telegram_webhook_url)
```

The webhook endpoint:
```python
@router.post("/webhook")
async def telegram_webhook(update: dict):
    # Validate the update came from Telegram
    # Queue the update for processing (don't process inline)
    # Return 200 OK within 2 seconds
    await process_update.delay(update)  # Celery task or background_tasks
    return {"ok": True}
```

#### 2.7 Platform Detection from Message Text

```python
PLATFORM_TAGS = {
    "#x": "x",
    "#twitter": "x", 
    "#tiktok": "tiktok",
    "#tt": "tiktok",
    "#instagram": "instagram",
    "#ig": "instagram",
}

def extract_platforms_from_text(text: str) -> list[str]:
    """Extract platform targets from text. Returns [] if no tags found (post to all)."""
    found = set()
    for tag, platform in PLATFORM_TAGS.items():
        if tag.lower() in text.lower():
            found.add(platform)
    return list(found)

def remove_platform_tags(text: str) -> str:
    """Strip platform hashtags from caption before posting."""
    for tag in PLATFORM_TAGS:
        text = text.replace(tag, "").replace(tag.upper(), "")
    return text.strip()
```

### Phase 2 Completion Checklist

- [ ] `/start` shows welcome message with inline keyboard
- [ ] `/help` shows all commands
- [ ] Sending plain text posts to connected platforms
- [ ] Sending photo + caption posts to connected platforms  
- [ ] Platform-specific targeting via `#x`, `#tiktok`, `#ig` tags
- [ ] Confirmation message after successful post
- [ ] Error message if posting fails
- [ ] `/status` shows connected accounts
- [ ] Webhook is registered and receiving updates
- [ ] Bot works both via polling and webhook modes

---

## Phase 3: X (Twitter) Integration

**Goal:** Full X (Twitter) adapter — OAuth connect, text posting, image posting, token refresh.

**Inputs needed:**
- X Developer account with Read+Write permissions
- API Key, API Key Secret, Access Token, Access Token Secret

### Step-by-Step

#### 3.1 OAuth 1.0a Setup

X uses OAuth 1.0a for user authentication (different from most platforms that use OAuth 2.0).

```python
class XAdapter(BasePlatformAdapter):
    def __init__(self):
        self.auth = tweepy.OAuth1UserHandler(
            settings.x_api_key,
            settings.x_api_key_secret,
            callback=settings.x_callback_url
        )
    
    def get_auth_url(self, state: str) -> str:
        return self.auth.get_authorization_url()
    
    async def authenticate(self, oauth_verifier: str, oauth_token: str) -> dict:
        """Exchange request token + verifier for access tokens."""
        self.auth.request_token = {"oauth_token": oauth_token, "oauth_token_secret": ""}
        access_token, access_token_secret = self.auth.get_access_token(oauth_verifier)
        return {
            "access_token": access_token,
            "access_token_secret": access_token_secret,
        }
```

#### 3.2 API v2 Client

Use Tweepy with API v2 endpoints for posting:

```python
def _get_client(self, access_token: str, access_token_secret: str) -> tweepy.Client:
    return tweepy.Client(
        consumer_key=settings.x_api_key,
        consumer_secret=settings.x_api_key_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
```

#### 3.3 Text Posting

```python
async def post_text(self, access_token: str, content: str, **kwargs) -> PostResult:
    try:
        # Decrypt stored token_secret as well
        tokens = json.loads(decrypt_token(access_token))
        client = self._get_client(tokens["access_token"], tokens["access_token_secret"])
        
        # Truncate to 280 chars
        content = truncate_text(content, self.get_platform_info().max_text_length)
        
        response = client.create_tweet(text=content)
        return PostResult(
            success=True,
            platform_post_id=str(response.data["id"]),
            platform_post_url=f"https://x.com/user/status/{response.data['id']}"
        )
    except tweepy.TweepyException as e:
        return PostResult(success=False, error_message=str(e))
```

#### 3.4 Image Posting

X requires:
1. Upload media via v1.1 endpoint (`media/upload`)
2. Create tweet with `media_ids`

```python
async def post_image(self, access_token: str, image_data: bytes, caption: str) -> PostResult:
    try:
        tokens = json.loads(decrypt_token(access_token))
        
        # Upload media using API v1.1
        api = tweepy.API(self._get_auth(tokens))
        media = api.media_upload(filename="image.jpg", file=io.BytesIO(image_data))
        
        # Create tweet with media
        client = self._get_client(tokens["access_token"], tokens["access_token_secret"])
        response = client.create_tweet(
            text=truncate_text(caption, 280),
            media_ids=[media.media_id]
        )
        
        return PostResult(
            success=True,
            platform_post_id=str(response.data["id"]),
            platform_post_url=f"https://x.com/user/status/{response.data['id']}"
        )
    except tweepy.TweepyException as e:
        return PostResult(success=False, error_message=str(e))
```

#### 3.5 Platform Info

```python
def get_platform_info(self) -> PlatformInfo:
    return PlatformInfo(
        name="x",
        display_name="X (Twitter)",
        supports_text=True,
        supports_image=True,
        supports_video=False,  # Not supported in free tier
        max_text_length=280,
        max_image_count=4,
    )
```

### Phase 3 Completion Checklist

- [ ] User can connect X account via `/connect x`
- [ ] OAuth callback correctly saves encrypted tokens
- [ ] Sending text → appears as tweet on X
- [ ] Sending photo + caption → appears as tweet with image on X
- [ ] Text > 280 chars is truncated with warning
- [ ] Token refresh works on 401 responses
- [ ] Disconnect removes tokens and shows confirmation
- [ ] Tests pass with mocked Tweepy calls

---

## Phase 4: TikTok Integration

**Goal:** Full TikTok adapter using Content Posting API.

**Inputs needed:**
- TikTok developer account (approved for Content Posting API)
- Client Key, Client Secret
- TikTok business/linked account

### Step-by-Step

#### 4.1 OAuth 2.0 Setup

TikTok uses OAuth 2.0 with PKCE:

```python
class TikTokAdapter(BasePlatformAdapter):
    def __init__(self):
        self.client_key = settings.tiktok_client_key
        self.client_secret = settings.tiktok_client_secret
        self.redirect_uri = settings.tiktok_callback_url
        self.base_url = "https://open.tiktokapis.com/v2"
    
    def get_auth_url(self, state: str) -> str:
        params = {
            "client_key": self.client_key,
            "response_type": "code",
            "scope": "user.info.basic,video.publish",
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"
    
    async def authenticate(self, code: str) -> dict:
        url = f"{self.base_url}/oauth/token/"
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            return resp.json()
```

#### 4.2 TikTok Posting (Direct Post)

TikTok's Content Posting API supports direct posting of videos and photos:

```python
async def post_video(self, access_token: str, video_data: bytes, caption: str) -> PostResult:
    url = f"{self.base_url}/post/publish/video/init/"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Step 1: Initialize upload
    body = {
        "post_info": {
            "title": caption[:2200],  # TikTok caption limit
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_comment": False,
            "disable_duet": False,
            "disable_stitch": False,
        },
        "source_info": {"source": "FILE_UPLOAD", "video_size": len(video_data)},
    }
    
    async with httpx.AsyncClient() as client:
        init_resp = await client.post(url, headers=headers, json=body)
        init_data = init_resp.json()
        
        # Step 2: Upload video bytes to the upload URL
        upload_url = init_data["data"]["upload_url"]
        await client.put(upload_url, content=video_data)
        
        # Step 3: Wait for processing (TikTok processes the video)
        # TikTok sends a webhook when done, or we poll
        
        return PostResult(success=True, platform_post_id=init_data["data"]["publish_id"])
```

#### 4.3 Image Posting (Photo Mode)

TikTok supports photo mode posts (slideshow):

```python
async def post_image(self, access_token: str, image_data: bytes, caption: str) -> PostResult:
    # Similar to video but with "photo" source type
    # Uses /post/publish/photo/init/ endpoint
```

### Phase 4 Completion Checklist

- [ ] User can connect TikTok account via `/connect tiktok`
- [ ] OAuth flow works end-to-end
- [ ] Sending text → posted to TikTok (if platform supports text-only)
- [ ] Sending photo → posted to TikTok as photo mode
- [ ] Sending video → posted to TikTok
- [ ] Token refresh works
- [ ] Tests pass with mocked API calls

---

## Phase 5: Instagram Integration

**Goal:** Full Instagram adapter using Instagram Graph API (via Facebook).

**Inputs needed:**
- Facebook Developer account
- Facebook App with Instagram Graph API product
- Instagram Business or Creator account linked to a Facebook Page

### Step-by-Step

#### 5.1 OAuth Setup

Instagram uses Facebook Login + Instagram Graph API:

```python
class InstagramAdapter(BasePlatformAdapter):
    def __init__(self):
        self.app_id = settings.instagram_app_id
        self.app_secret = settings.instagram_app_secret
        self.redirect_uri = settings.instagram_callback_url
    
    def get_auth_url(self, state: str) -> str:
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
            "response_type": "code",
            "state": state,
        }
        return f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"
    
    async def authenticate(self, code: str) -> dict:
        # Step 1: Exchange code for short-lived access token
        # Step 2: Exchange short-lived token for long-lived token (60 days)
        # Step 3: Get Instagram Business Account ID from Facebook Pages
```

#### 5.2 Instagram Posting

Instagram Graph API supports two types:
- **Single media** (image or video) to the feed
- **Reels** (video only)
- **Carousel** (multiple images) — requires multiple steps

```python
async def post_image(self, access_token: str, image_data: bytes, caption: str) -> PostResult:
    ig_user_id = self._get_instagram_user_id(access_token)
    
    # Step 1: Create media container
    container_url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media"
    container_params = {
        "image_url": self._upload_to_cdn(image_data),  # Instagram requires URL, not binary
        "caption": caption[:2200],
        "access_token": access_token,
    }
    
    # Step 2: Publish the container
    publish_url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish"
    # ... POST with creation_id
```

### Phase 5 Completion Checklist

- [ ] User can connect Instagram via `/connect instagram`
- [ ] OAuth + Facebook Page + IG account resolution works
- [ ] Image posting works (feed posts)
- [ ] Caption properly formatted
- [ ] Token refresh works (long-lived 60-day tokens)
- [ ] Tests pass with mocked API calls

---

## Phase 6: Polish & Production-Ready

### Step-by-Step

#### 6.1 Post History
- Telegram `/history` command returns last 10 posts with status per platform

#### 6.2 Post Scheduling
- New model field `scheduled_at`
- Celery beat task checks every minute for due posts
- Telegram command: `/schedule 2026-12-25 10:00 Merry Christmas!`

#### 6.3 Image Processing
- Auto-resize images to each platform's optimal dimensions:
  - X: 1600x900 (16:9)
  - Instagram: 1080x1080 (1:1) or 1080x1350 (4:5)
  - TikTok: 1080x1920 (9:16)

#### 6.4 Rate Limiting with Redis
- Per-user rate limits: max 5 posts per hour across all platforms
- Per-platform rate limits from API docs

#### 6.5 Error Handling
- Categorize errors: auth (token expired), rate limit, content policy, network
- Retry with exponential backoff (3 attempts)
- Detailed error messages: "❌ TikTok: Video processing failed (try again in 5 min)"

#### 6.6 End-to-End Tests
- Full flow test: Telegram message → DB record → adapter call → DB update → Telegram response
- Mock all external APIs

#### 6.7 Production Deployment
- Environment-specific configs (dev/staging/prod)
- GitHub Actions CI/CD pipeline
- Logging to file + console (structured JSON logs)
- Sentry for error tracking

---

## Phase 7: Web Application (Future)

### Step-by-Step

#### 7.1 Frontend Framework
- React with TypeScript (Vite for build)
- Tailwind CSS for styling

#### 7.2 Features
- Login/registration (JWT-based)
- Dashboard showing connected platforms
- Post composer with image upload + preview
- Platform toggle switches (visual selection)
- Post history table with filters
- Analytics: views, likes, comments per platform

#### 7.3 API Changes
- Add authentication (JWT) endpoints
- Extend existing API with web-specific endpoints
- WebSocket for real-time post status updates

---

## Phase 8: Advanced Features (Future)

- **AI Caption Generation:** OpenAI GPT-4 API integration. `Generate a caption about my new coffee shop opening`
- **Hashtag Suggestions:** Analyze image content + text, suggest relevant trending hashtags
- **Best Time to Post:** Analyze engagement history, suggest optimal posting times per platform
- **Additional Platforms:** YouTube Shorts, LinkedIn, Facebook (each is one new adapter file)
- **Analytics Reports:** Weekly/monthly PDF reports with post performance

---

*This document is kept in sync with PROGRESS.md. After completing each sub-task in a phase, mark it as `[x]` in PROGRESS.md.*
