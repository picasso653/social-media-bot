# Multi-Social Media Posting Bot (Via Telegram)
## Requirements & Architecture Document

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [What You Will Be Able To Do](#2-what-you-will-be-able-to-do)
3. [System Architecture](#3-system-architecture)
4. [Tech Stack](#4-tech-stack)
5. [Functional Requirements](#5-functional-requirements)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [SOLID Principles In Practice](#7-solid-principles-in-practice)
8. [Database Schema](#8-database-schema)
9. [API Design](#9-api-design)
10. [Step-by-Step Setup Guide](#10-step-by-step-setup-guide)
11. [Future Roadmap](#11-future-roadmap)
12. [FAQ](#12-faq)

---

## 1. Project Overview

**What is it?**
A Telegram bot that acts as your personal social media assistant. You send it a photo and some text via Telegram, and it automatically posts that content to your connected social media accounts (X/Twitter, TikTok, Instagram, and more in the future).

**Why Telegram?**
- You already use messaging apps daily — Telegram is free, fast, and has a built-in Bot API.
- No need to build a separate mobile app right away (saves months of work).
- Works from any device where Telegram works (phone, tablet, desktop).

**Core Idea:**
```
You (on Telegram)  ──>  Telegram Bot  ──>  Backend Server  ──>  X/TikTok/Instagram
   "Post this"            receives msg        processes &       publishes your
   + photo                + image             routes it          post
```

---

## 2. What You Will Be Able To Do

### Version 1 (MVP — what we build first)

| Action | How | Example |
|--------|-----|---------|
| Send a text post to all connected accounts | Telegram message | Type "Hello World" → posted to X, TikTok, Instagram |
| Send an image + caption to all accounts | Telegram message with photo | Attach a photo + caption "My new product" |
| Choose which platforms to post to | Command with hashtags or buttons | `/post #x #tiktok Hello World` → posts only to X and TikTok |
| Connect/disconnect a social account | Telegram command | `/connect x` starts linking your X account |
| See connection status | Telegram command | `/status` shows which accounts are linked |

### Version 2 (Future)

| Feature | Description |
|---------|-------------|
| Schedule posts | `/schedule 2026-12-25 10:00 Merry Christmas!` |
| Web dashboard | A website where you manage everything with a GUI |
| Analytics | See views, likes, comments per post |
| AI caption generator | "Write a caption about my new coffee shop" → generates one |

---

## 3. System Architecture

We follow a **clean, layered architecture** so each piece is independent and replaceable.

```
┌─────────────────────────────────────────────────────────┐
│                     TELEGRAM LAYER                        │
│  (Receives your messages, sends back confirmations)       │
└─────────────────────┬───────────────────────────────────┘
                      │  Webhook / Polling
┌─────────────────────▼───────────────────────────────────┐
│                   API GATEWAY LAYER                       │
│  (Validates requests, routes to correct handler)          │
│  - FastAPI / Express endpoints                            │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                   SERVICE LAYER                           │
│  (Business logic — what happens when you post)            │
│  - PostService: receives content, decides platforms       │
│  - PlatformRouter: routes to correct social media API     │
│  - AuthService: manages OAuth tokens                      │
└───────┬─────────────┬─────────────┬─────────────────────┘
        │             │             │
┌───────▼───┐  ┌──────▼──────┐  ┌──▼──────────┐
│ X Adapter │  │TikTok Adapter│  │Instagram Adap│
│(API calls)│  │(API calls)  │  │(API calls)  │
└───────────┘  └─────────────┘  └─────────────┘
        │             │             │
┌───────▼─────────────▼─────────────▼─────────────────────┐
│                   DATABASE LAYER                          │
│  (Stores users, tokens, post history)                     │
│  - PostgreSQL (users, accounts, posts)                    │
│  - Redis (cache, rate limiting)                           │
└─────────────────────────────────────────────────────────┘
```

### Why This Architecture?

- **Layered**: Each layer does one job. If we change the database, the Telegram layer doesn't care.
- **Adapter Pattern**: Each social media platform has its own "adapter". Adding a new platform (YouTube, LinkedIn, Facebook) means writing ONE new adapter file — nothing else changes.
- **Independence**: The Telegram bot can be replaced with a web app later without touching the social media posting logic.

---

## 4. Tech Stack

### Backend (The Engine)

| Technology | Purpose | Why |
|------------|---------|-----|
| **Python 3.11+** | Main language | Excellent library support, easy to learn, great for APIs |
| **FastAPI** | Web framework | Fast, modern, auto-generates documentation |
| **SQLAlchemy** | Database ORM | Write Python instead of SQL, works with any database |
| **PostgreSQL** | Main database | Robust, free, great for relational data |
| **Redis** | Cache + queue | Stores temporary data, handles rate limiting |
| **Alembic** | Database migrations | Tracks database changes like Git tracks code |
| **Celery** | Background tasks | Handles posting asynchronously (don't make user wait) |

### Social Media APIs

| Platform | Library / API | Notes |
|----------|--------------|-------|
| **X (Twitter)** | `tweepy` or X API v2 | Requires developer account + OAuth 1.0a |
| **TikTok** | TikTok Content Posting API | Requires business account verification |
| **Instagram** | Instagram Graph API | Requires Facebook developer account + page |

### Infrastructure (How It Runs)

| Component | Purpose | Cost Estimate |
|-----------|---------|---------------|
| **VPS/Droplet** (DigitalOcean, Hetzner, Railway) | Runs the backend 24/7 | $5–15/month |
| **Docker** | Packages the app so it runs the same everywhere | Free |
| **NGINX** | Reverse proxy (handles HTTPS) | Free |
| **GitHub** | Code hosting + CI/CD | Free |

### Telegram

| Tool | Purpose |
|------|---------|
| **python-telegram-bot** | Handles Telegram bot interactions |
| **BotFather** (Telegram's bot) | Creates your bot and gives you an API token |

---

## 5. Functional Requirements

### FR-1: Telegram Bot Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message + instructions | `/start` |
| `/connect <platform>` | Start linking a social account | `/connect x` |
| `/disconnect <platform>` | Remove a linked account | `/disconnect tiktok` |
| `/status` | Show which platforms are connected | `/status` |
| `/help` | Show all available commands | `/help` |

### FR-2: Posting

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| FR-2.1 | User sends text → posted as text to connected platforms | Must Have |
| FR-2.2 | User sends photo + caption → posted as image+text | Must Have |
| FR-2.3 | User can specify which platforms to post to | Must Have |
| FR-2.4 | Posts are stored in history (date, platform, status) | Should Have |
| FR-2.5 | Confirmation message sent back to user after posting | Must Have |
| FR-2.6 | Error message sent back if posting fails on a platform | Must Have |
| FR-2.7 | Support posting video (TikTok primarily) | Could Have |

### FR-3: Account Management

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| FR-3.1 | OAuth flow for connecting social accounts | Must Have |
| FR-3.2 | Automatic token refresh (so you don't have to re-login) | Must Have |
| FR-3.3 | Revoke/disconnect accounts | Must Have |
| FR-3.4 | View which accounts are active | Must Have |

### FR-4: Platform-Specific Formatting

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| FR-4.1 | Text auto-truncated to platform limits (X: 280 chars) | Must Have |
| FR-4.2 | Image resized to platform requirements | Should Have |
| FR-4.3 | Platform-specific hashtag formatting | Could Have |

---

## 6. Non-Functional Requirements

### NFR-1: Reliability
- System should be available 99% of the time
- Failed posts should be retried 3 times before marking as failed

### NFR-2: Security
- All OAuth tokens encrypted at rest in the database
- Telegram webhook endpoint validates requests (only accepts from Telegram servers)
- No user passwords stored (OAuth-only authentication)

### NFR-3: Extensibility
- Adding a new social media platform should require **one new file** (the adapter)
- No changes to existing code (Open/Closed Principle)
- Platform-agnostic core code

### NFR-4: Maintainability
- Code follows SOLID principles
- All functions are type-hinted
- Code coverage > 80% for core business logic

### NFR-5: Performance
- Post submission response < 3 seconds
- Actual posting happens in background (async)
- Image processing happens before sending to APIs

---

## 7. SOLID Principles In Practice

Here's how each SOLID principle maps to our code:

### S — Single Responsibility Principle
**One class, one job.**

```
❌ BAD: SocialMediaBot class that handles Telegram + posts to X + posts to TikTok + database
✅ GOOD:
   - TelegramHandler: only handles incoming Telegram messages
   - PostService: only orchestrates where to post
   - XAdapter: only talks to X's API
   - PostRepository: only talks to the database
```

### O — Open/Closed Principle
**Open for extension, closed for modification.**

Adding a new platform (e.g., LinkedIn) means:
1. Create `LinkedInAdapter` class that implements `BasePlatformAdapter`
2. Register it in the platform registry
3. **Done.** No existing code is touched.

```python
# Base class (closed — we never change this)
class BasePlatformAdapter(ABC):
    @abstractmethod
    async def post_text(self, content: str) -> PostResult: ...
    
    @abstractmethod  
    async def post_image(self, image: bytes, caption: str) -> PostResult: ...
    
    @abstractmethod
    async def get_platform_name(self) -> str: ...

# New adapter (open — we extend here)
class LinkedInAdapter(BasePlatformAdapter):
    async def post_text(self, content: str) -> PostResult:
        # LinkedIn-specific code here
        pass
```

### L — Liskov Substitution Principle
**Any subclass should work where its parent class is expected.**

Every adapter can be used interchangeably. The `PostService` doesn't know or care which platforms it's posting to — it just calls `adapter.post_text()`.

### I — Interface Segregation Principle
**Don't force a class to implement methods it doesn't need.**

```python
# Instead of one giant interface:
class TextPoster(ABC):
    @abstractmethod
    def post_text(self, content): ...

class ImagePoster(ABC):
    @abstractmethod
    def post_image(self, image, caption): ...

class VideoPoster(ABC):
    @abstractmethod
    def post_video(self, video, caption): ...

# TikTok implements all three, X implements TextPoster + ImagePoster only
```

### D — Dependency Inversion Principle
**Depend on abstractions, not concrete classes.**

```python
# PostService depends on the ABSTRACT platform, not on X specifically
class PostService:
    def __init__(self, platforms: list[BasePlatformAdapter]):
        self.platforms = platforms  # List of abstractions
    
    async def post_to_all(self, content):
        for platform in self.platforms:
            await platform.post_text(content)  # Works for any platform
```

---

## 8. Database Schema

### Entity-Relationship Diagram (text representation)

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│    users     │       │ social_accounts  │       │      posts       │
├──────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)      │──┐    │ id (PK)          │       │ id (PK)          │
│ telegram_id  │  │    │ user_id (FK)     │──┐    │ user_id (FK)     │
│ username     │  │    │ platform         │  │    │ social_account_id│
│ created_at   │  │    │ platform_user_id │  │    │ platform         │
│ is_active    │  │    │ access_token     │  │    │ content_type     │
└──────────────┘  │    │ refresh_token    │  │    │ text_content     │
                  │    │ token_expires_at │  │    │ media_url        │
                  └───<│ is_active        │  │    │ status           │
                       │ created_at       │  │    │ posted_at        │
                       │ updated_at       │  │    │ error_message    │
                       └──────────────────┘  │    └──────────────────┘
                                             │
                       ┌──────────────────┐  │
                       │  post_platforms  │  │
                       ├──────────────────┤  │
                       │ id (PK)          │  │
                       │ post_id (FK)     │──┘
                       │ account_id (FK)  │
                       │ platform_post_id │
                       │ platform_post_url│
                       │ status           │
                       │ posted_at        │
                       └──────────────────┘
```

### Table Explanations

**users** — One row per Telegram user who uses the bot.
**social_accounts** — Stores OAuth tokens for each connected platform. One user can have one account per platform (e.g., one X, one TikTok).
**posts** — Every post you make through the bot is stored here.
**post_platforms** — Links a post to each platform it was posted on (since one post can go to multiple platforms). Stores the platform's post ID and URL so you can find it later.

---

## 9. API Design

### Internal API Endpoints (for the Telegram bot to call)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/telegram/webhook` | Receives Telegram messages |
| `GET` | `/api/v1/auth/{platform}/login` | Start OAuth flow for a platform |
| `GET` | `/api/v1/auth/{platform}/callback` | OAuth callback URL |
| `GET` | `/api/v1/accounts/status` | Get connected accounts status |
| `POST` | `/api/v1/posts` | Create a new post |
| `GET` | `/api/v1/posts/history` | Get post history |

### Future API Endpoints (for web/mobile app)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/login` | App login |
| `GET` | `/api/v1/analytics` | Post performance analytics |
| `POST` | `/api/v1/posts/schedule` | Schedule a future post |

---

## 10. Step-by-Step Setup Guide

### Prerequisites Checklist

Before writing a single line of code, you need these accounts:

```
☐ Telegram account (you have this already)
☐ GitHub account (for code storage)
☐ A server to run the bot (see step 5)
☐ X (Twitter) Developer Account
☐ TikTok Developer Account  
☐ Facebook Developer Account (for Instagram)
```

### Step 1: Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Give it a name (e.g., "My Social Poster")
4. Give it a username (must end in `bot`, e.g., `mysocialposter_bot`)
5. BotFather gives you a **Token** — save this. It looks like:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

### Step 2: Get X (Twitter) API Access

1. Go to [developer.twitter.com](https://developer.twitter.com)
2. Sign up for a **Free Tier** developer account
3. Create a **Project** and an **App**
4. In your App settings, go to **Keys and Tokens**
5. Note down:
   - API Key (Consumer Key)
   - API Key Secret (Consumer Secret)
   - Access Token
   - Access Token Secret
6. Set the App permissions to **Read and Write**

### Step 3: Get TikTok API Access

1. Go to [developers.tiktok.com](https://developers.tiktok.com)
2. Create a developer account
3. Create an app — choose **Content Posting API**
4. You'll need a TikTok business account linked
5. Note down:
   - Client Key
   - Client Secret

### Step 4: Get Instagram API Access

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Create a developer account
3. Create an app — choose **Business** type
4. Add **Instagram Graph API** product
5. You'll need:
   - A Facebook Page linked to your Instagram Business/Creator account
   - App ID and App Secret
6. Note down:
   - Facebook App ID
   - Facebook App Secret
   - Instagram Business Account ID

### Step 5: Set Up a Server

**Option A: Railway (Easiest — recommended for beginners)**
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Create a new project → Deploy from GitHub repo
4. Add PostgreSQL and Redis plugins
5. Railway auto-detects your app and runs it
6. Cost: ~$5/month

**Option B: DigitalOcean Droplet (More control)**
1. Go to [digitalocean.com](https://digitalocean.com)
2. Create a Droplet (Ubuntu 22.04, basic $6/month plan)
3. Follow their setup guide to install Docker

### Step 6: Project Setup (Once Server is Ready)

```bash
# Clone the project
git clone <your-repo-url>
cd social-media-bot

# Copy environment file and fill in your tokens
cp .env.example .env
# Now edit .env with Notepad/VS Code — fill in ALL your tokens

# Start everything with Docker
docker-compose up -d
```

### Step 7: Connect Your Accounts

1. Open your Telegram bot
2. Send `/connect x` — the bot gives you a link
3. Open the link, authorize the app
4. Send `/connect tiktok` — same process
5. Send `/connect instagram` — same process
6. Send `/status` to verify all are connected

### Step 8: Test It

1. Send your bot a text message: "Hello from my new bot!"
2. Send a photo with a caption
3. Check your social media accounts — the posts should be there

---

## 11. Future Roadmap

### Phase 1: Core MVP (Now)
- [x] Requirements documentation
- [ ] Project scaffolding (Docker, FastAPI, database)
- [ ] Telegram bot integration (webhook)
- [ ] X (Twitter) adapter
- [ ] TikTok adapter
- [ ] Instagram adapter
- [ ] Basic posting (text + image)
- [ ] Account connection/disconnection

### Phase 2: Polish (2-4 weeks after MVP)
- [ ] Post scheduling
- [ ] Post history with status
- [ ] Image auto-resizing per platform
- [ ] Better error handling & retry logic
- [ ] Admin dashboard (basic web UI)

### Phase 3: Web App (1-2 months after Phase 2)
- [ ] Full web dashboard with login
- [ ] Drag-and-drop post composer
- [ ] Visual platform selector
- [ ] Analytics dashboard
- [ ] Multi-user support (for agencies)

### Phase 4: Advanced Features
- [ ] AI caption generation (OpenAI integration)
- [ ] Hashtag suggestions
- [ ] Best time to post recommendations
- [ ] YouTube Shorts support
- [ ] LinkedIn support
- [ ] Facebook support

---

## 12. FAQ

**Q: Do I need to know how to code to use this?**
A: After initial setup (which this guide covers step-by-step), you just use Telegram. No coding needed day-to-day.

**Q: Is this free?**
A: The code is free. You pay for: server (~$5-15/month), and that's it. The social media APIs are free for basic usage.

**Q: What if TikTok bans my account?**
A: This bot uses TikTok's official Content Posting API. As long as you follow their content guidelines, your account is safe.

**Q: Can I post videos?**
A: Version 1 supports text + images. Video support (especially for TikTok) is planned for Version 2.

**Q: How do I add another social media platform later?**
A: A developer adds one new file (the adapter class). The rest of the system doesn't change. This is the beauty of the architecture.

**Q: What happens if a post fails?**
A: You get a Telegram message telling you which platform failed and why. The post is saved and can be retried.

**Q: Will this violate any terms of service?**
A: No. This uses each platform's official API exactly as intended. It's the same as using Hootsuite or Buffer.

**Q: Can multiple people use my bot?**
A: In the MVP, only you (the owner). Multi-user support is planned for Phase 3.

---

## Appendix: File Structure (How The Code Is Organized)

```
social-media-bot/
├── .env.example              # Template for your secret keys
├── .gitignore                # Files to not upload to GitHub
├── docker-compose.yml        # Runs everything with one command
├── Dockerfile                # Instructions to build the app
├── requirements.txt          # Python libraries we need
├── alembic.ini               # Database migration config
│
├── src/
│   ├── main.py               # Entry point — starts the server
│   ├── config.py             # Reads .env file, provides settings
│   │
│   ├── api/                  # API GATEWAY LAYER
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── telegram.py   # Webhook endpoint for Telegram
│   │   │   ├── auth.py       # OAuth endpoints
│   │   │   └── posts.py      # Post creation endpoints
│   │   └── dependencies.py   # Shared dependencies (DB session, etc.)
│   │
│   ├── services/             # SERVICE LAYER (business logic)
│   │   ├── post_service.py   # Orchestrates posting to platforms
│   │   ├── auth_service.py   # Handles OAuth flows
│   │   └── telegram_service.py  # Handles Telegram commands
│   │
│   ├── platforms/            # ADAPTER LAYER
│   │   ├── base.py           # BasePlatformAdapter (abstract)
│   │   ├── registry.py       # Platform registry (maps names to adapters)
│   │   ├── x_adapter.py      # X (Twitter) implementation
│   │   ├── tiktok_adapter.py # TikTok implementation
│   │   └── instagram_adapter.py  # Instagram implementation
│   │
│   ├── models/               # DATABASE LAYER
│   │   ├── user.py
│   │   ├── social_account.py
│   │   ├── post.py
│   │   └── post_platform.py
│   │
│   ├── repositories/         # Database access (Repository Pattern)
│   │   ├── user_repository.py
│   │   ├── account_repository.py
│   │   └── post_repository.py
│   │
│   └── utils/                # Helper utilities
│       ├── image_processor.py   # Resize/crop images per platform
│       ├── text_formatter.py    # Truncate text to platform limits
│       └── security.py          # Encrypt/decrypt tokens
│
├── tests/                    # Automated tests
│   ├── test_post_service.py
│   ├── test_x_adapter.py
│   └── ...
│
└── scripts/                  # Helper scripts
    └── setup.sh              # One-click server setup
```

---

*Last updated: August 2026*
*Next step: Start Phase 1 — Project Scaffolding*
