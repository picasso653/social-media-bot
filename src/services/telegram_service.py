import contextlib
import json
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from src.api.dependencies import async_session_factory
from src.config import settings
from src.platforms.registry import PlatformRegistry
from src.services.auth_service import AuthService
from src.services.post_service import PostService

logger = logging.getLogger(__name__)

PLATFORM_TAGS = {
    "#x": "x",
    "#twitter": "x",
    "#tiktok": "tiktok",
    "#tt": "tiktok",
    "#instagram": "instagram",
    "#ig": "instagram",
}

VALID_PLATFORMS = {"x", "tiktok", "instagram"}


@contextlib.asynccontextmanager
async def _db_services():
    session = async_session_factory()
    auth_svc = AuthService(session=session)
    post_svc = PostService(session=session, auth_service=auth_svc)
    try:
        yield session, auth_svc, post_svc
        await session.commit()
    finally:
        await session.close()


def extract_platforms_from_text(text: str) -> list[str]:
    found: set[str] = set()
    lower_text = text.lower()
    for tag, platform in PLATFORM_TAGS.items():
        if tag in lower_text:
            found.add(platform)
    return list(found)


def remove_platform_tags(text: str) -> str:
    parts = text.split()
    filtered = [p for p in parts if p.lower() not in PLATFORM_TAGS]
    return " ".join(filtered).strip()


class TelegramService:
    _instance: Optional["TelegramService"] = None

    def __new__(cls) -> "TelegramService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.application: Optional[Application] = None

    def get_application(self) -> Application:
        if self.application is None:
            self.application = self._build_application()
        return self.application

    def _build_application(self) -> Application:
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set.")

        app = Application.builder().token(settings.telegram_bot_token).build()

        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("help", self._handle_help))
        app.add_handler(CommandHandler("connect", self._handle_connect))
        app.add_handler(CommandHandler("disconnect", self._handle_disconnect))
        app.add_handler(CommandHandler("status", self._handle_status))
        app.add_handler(CommandHandler("history", self._handle_history))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_message))
        app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo_message))
        app.add_handler(CallbackQueryHandler(self._handle_callback))

        return app

    async def process_update(self, update_data: dict) -> None:
        app = self.get_application()
        update = Update.de_json(update_data, app.bot)
        await app.process_update(update)

    async def set_webhook(self) -> None:
        if not settings.telegram_webhook_url:
            return
        app = self.get_application()
        await app.initialize()
        await app.bot.set_webhook(url=settings.telegram_webhook_url)

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        keyboard = [
            [InlineKeyboardButton("📝 New Post", callback_data="new_post")],
            [
                InlineKeyboardButton("🔗 Connect X", callback_data="connect_x"),
                InlineKeyboardButton("🔗 Connect TikTok", callback_data="connect_tiktok"),
            ],
            [InlineKeyboardButton("🔗 Connect Instagram", callback_data="connect_instagram")],
            [
                InlineKeyboardButton("📊 My Accounts", callback_data="status"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
        ]
        await update.message.reply_text(
            "🤖 *Welcome to Social Media Bot!*\n\n"
            "Send me text or a photo to post to your connected accounts.\n"
            "Use hashtags to pick platforms:\n"
            "  `#x` `#tiktok` `#ig`\n\n"
            "Type /help to see all commands.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "📋 *Available Commands*\n\n"
            "/start — Welcome message\n"
            "/help — This list\n"
            "/connect `<platform>` — Link a social account\n"
            "/disconnect `<platform>` — Unlink an account\n"
            "/status — See which accounts are connected\n"
            "/history — Your last 10 posts\n\n"
            "*Posting*\n"
            "Just send text or a photo to post.\n"
            "Add `#x` `#tiktok` `#ig` to select platforms.",
            parse_mode="Markdown",
        )

    async def _handle_connect(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        args = context.args
        if not args:
            keyboard = [
                [
                    InlineKeyboardButton("X (Twitter)", callback_data="connect_x"),
                    InlineKeyboardButton("TikTok", callback_data="connect_tiktok"),
                ],
                [InlineKeyboardButton("Instagram", callback_data="connect_instagram")],
            ]
            await update.message.reply_text(
                "Which platform would you like to connect?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        platform = args[0].lower()
        if platform not in VALID_PLATFORMS:
            await update.message.reply_text(
                f"❌ Unknown platform: `{platform}`\nValid: `x`, `tiktok`, `instagram`",
                parse_mode="Markdown",
            )
            return

        telegram_id = update.effective_user.id
        async with _db_services() as (session, auth_svc, post_svc):
            auth_url = await auth_svc.start_oauth(platform, telegram_id)

        await update.message.reply_text(
            f"🔗 *Connect {platform.upper()}*\n\n"
            f"[Click here to authorize]({auth_url})\n\n"
            "After authorizing, come back here and your account will be linked.",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    async def _handle_disconnect(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        args = context.args
        if not args:
            await update.message.reply_text("Usage: `/disconnect <platform>`\nExample: `/disconnect x`", parse_mode="Markdown")
            return

        platform = args[0].lower()
        if platform not in VALID_PLATFORMS:
            await update.message.reply_text(f"❌ Unknown platform: `{platform}`", parse_mode="Markdown")
            return

        telegram_id = update.effective_user.id
        async with _db_services() as (session, auth_svc, post_svc):
            success = await auth_svc.disconnect_platform(str(telegram_id), platform)

        if success:
            await update.message.reply_text(f"✅ Disconnected from {platform.upper()}")
        else:
            await update.message.reply_text(f"❌ Could not disconnect from {platform.upper()}. Was it connected?")

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        telegram_id = update.effective_user.id
        async with _db_services() as (session, auth_svc, post_svc):
            platforms = await auth_svc.get_connected_platforms(str(telegram_id))

        if not platforms:
            await update.message.reply_text(
                "📊 *Account Status*\n\nNo accounts connected yet.\nUse /connect to link one.",
                parse_mode="Markdown",
            )
            return

        lines = ["📊 *Account Status*\n"]
        for display_name in platforms:
            lines.append(f"  ✅ {display_name}")

        keyboard = [[InlineKeyboardButton("➕ Connect Another", callback_data="connect_menu")]]
        await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    async def _handle_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        telegram_id = update.effective_user.id
        async with _db_services() as (session, auth_svc, post_svc):
            history = await post_svc.get_user_history(str(telegram_id), limit=10)

        if not history:
            await update.message.reply_text("📝 *Post History*\n\nNo posts yet. Send something!")
            return

        lines = ["📝 *Recent Posts*\n"]
        for entry in history:
            dt = entry.get("created_at", "unknown")
            content_preview = (entry.get("text_content") or "")[:50]
            statuses = entry.get("platform_statuses", {})
            status_line = " ".join(f"{p}:{'✅' if s else '❌'}" for p, s in statuses.items())
            lines.append(f"• *{dt}* — _{content_preview}_ — {status_line}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        telegram_id = update.effective_user.id
        text = update.message.text.strip()

        platforms = extract_platforms_from_text(text)
        clean_text = remove_platform_tags(text)

        if not clean_text:
            await update.message.reply_text("Please send some text to post.")
            return

        await update.message.reply_text("⏳ Processing your post...")

        async with _db_services() as (session, auth_svc, post_svc):
            result = await post_svc.create_post(
                user_id=str(telegram_id),
                content=clean_text,
                media=None,
                platforms=platforms if platforms else None,
            )

        await update.message.reply_text(self._format_post_result(result))

    async def _handle_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        telegram_id = update.effective_user.id
        caption = update.message.caption or ""

        platforms = extract_platforms_from_text(caption)
        clean_caption = remove_platform_tags(caption)

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        await update.message.reply_text("⏳ Uploading and posting your photo...")

        async with _db_services() as (session, auth_svc, post_svc):
            result = await post_svc.create_post(
                user_id=str(telegram_id),
                content=clean_caption,
                media=bytes(image_bytes),
                platforms=platforms if platforms else None,
            )

        await update.message.reply_text(self._format_post_result(result))

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        data = query.data
        telegram_id = update.effective_user.id

        if data == "new_post":
            await query.message.reply_text("Send me text or a photo and I'll post it for you!")

        elif data == "status":
            async with _db_services() as (session, auth_svc, post_svc):
                platforms = await auth_svc.get_connected_platforms(str(telegram_id))
            if platforms:
                await query.edit_message_text(
                    "📊 *Account Status*\n\n" + "\n".join(f"  ✅ {p}" for p in platforms),
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text("No accounts connected yet. Use /connect to get started.")

        elif data == "help":
            await query.message.reply_text("📋 Use /help for available commands.\nSend text or photos to post.")

        elif data == "connect_menu":
            keyboard = [
                [
                    InlineKeyboardButton("X (Twitter)", callback_data="connect_x"),
                    InlineKeyboardButton("TikTok", callback_data="connect_tiktok"),
                ],
                [InlineKeyboardButton("Instagram", callback_data="connect_instagram")],
            ]
            await query.edit_message_text("Choose a platform to connect:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("connect_"):
            platform = data.replace("connect_", "")
            async with _db_services() as (session, auth_svc, post_svc):
                auth_url = await auth_svc.start_oauth(platform, telegram_id)
            await query.edit_message_text(
                f"🔗 *Connect {platform.upper()}*\n\n"
                f"[Click here to authorize]({auth_url})\n\n"
                "After authorizing, your account will be linked.",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

        elif data.startswith("disconnect_"):
            platform = data.replace("disconnect_", "")
            async with _db_services() as (session, auth_svc, post_svc):
                success = await auth_svc.disconnect_platform(str(telegram_id), platform)
            if success:
                await query.edit_message_text(f"✅ Disconnected from {platform.upper()}")
            else:
                await query.edit_message_text(f"❌ Could not disconnect {platform.upper()}")

    def _format_post_result(self, result: dict) -> str:
        status = result.get("status", "unknown")
        platform_results = result.get("platform_results", {})
        all_platforms = result.get("platforms", [])

        if status == "no_accounts":
            return (
                "❌ *No accounts connected!*\n\n"
                "Use /connect to link your social media accounts first."
            )

        lines = ["📊 *Post Results*\n"]
        for platform in all_platforms:
            pr = platform_results.get(platform, {})
            display = pr.get("display_name", platform.upper())
            success = pr.get("success", False)
            error = pr.get("error", "")
            if success:
                lines.append(f"  ✅ *{display}* — Posted!")
            else:
                lines.append(f"  ❌ *{display}* — {error or 'Unknown error'}")

        if not all_platforms:
            lines.append("  ⚠️ No platforms were targeted.")
        return "\n".join(lines)


telegram_service = TelegramService()
