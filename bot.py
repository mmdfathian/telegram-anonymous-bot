#!/usr/bin/env python3
"""
Telegram Anonymous Bot - Personal & Experimental
A bot that forwards user messages to owner and allows owner to reply anonymously.

Features:
- Long Polling with run_polling()
- Message forwarding with metadata
- Reply-to-forward mapping (in-memory + SQLite persistence)
- Anti-spam rate limiting
- Supports: text, photo, video, document, audio, voice, sticker
- Railway-ready deployment
"""

import os
import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

from telegram import (
    Update,
    Message,
    User,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode


# ============================================================================
# Configuration & Constants
# ============================================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])

# Rate limiting: max messages per window
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 60  # seconds

# SQLite database path
DB_PATH = Path(__file__).parent / "messages.db"

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class MessageMapping:
    """Maps owner's forwarded message to original user."""
    owner_message_id: int
    user_chat_id: int
    user_message_id: int
    timestamp: float


# ============================================================================
# Database Layer (SQLite)
# ============================================================================

class MessageDatabase:
    """SQLite-backed message mapping storage for persistence across restarts."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS message_mappings (
                    owner_message_id INTEGER PRIMARY KEY,
                    user_chat_id INTEGER NOT NULL,
                    user_message_id INTEGER NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_chat
                ON message_mappings (user_chat_id)
            """)
            conn.commit()

    def save_mapping(self, mapping: MessageMapping) -> None:
        """Save a message mapping."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO message_mappings VALUES (?, ?, ?, ?)",
                (mapping.owner_message_id, mapping.user_chat_id,
                 mapping.user_message_id, mapping.timestamp)
            )
            conn.commit()

    def get_mapping(self, owner_message_id: int) -> Optional[MessageMapping]:
        """Retrieve mapping by owner's message ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM message_mappings WHERE owner_message_id = ?",
                (owner_message_id,)
            )
            row = cursor.fetchone()
            if row:
                return MessageMapping(*row)
            return None

    def delete_mapping(self, owner_message_id: int) -> bool:
        """Delete a mapping after successful reply."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM message_mappings WHERE owner_message_id = ?",
                (owner_message_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def cleanup_old(self, max_age_seconds: float = 86400 * 30) -> int:
        """Remove mappings older than max_age_seconds (default 30 days)."""
        cutoff = time.time() - max_age_seconds
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM message_mappings WHERE timestamp < ?",
                (cutoff,)
            )
            conn.commit()
            return cursor.rowcount


# In-memory cache for fast lookups (populated from DB on startup)
_message_cache: Dict[int, MessageMapping] = {}


# ============================================================================
# Rate Limiter (Simple Sliding Window)
# ============================================================================

class RateLimiter:
    """Simple per-user rate limiter using sliding window."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: Dict[int, list] = {}

    def is_allowed(self, user_id: int) -> bool:
        """Check if user is within rate limit."""
        now = time.time()
        if user_id not in self._requests:
            self._requests[user_id] = []

        # Remove expired timestamps
        self._requests[user_id] = [
            ts for ts in self._requests[user_id]
            if now - ts < self.window
        ]

        if len(self._requests[user_id]) >= self.max_requests:
            return False

        self._requests[user_id].append(now)
        return True

    def get_remaining(self, user_id: int) -> int:
        """Get remaining requests in current window."""
        now = time.time()
        if user_id not in self._requests:
            return self.max_requests
        valid = [ts for ts in self._requests[user_id] if now - ts < self.window]
        return max(0, self.max_requests - len(valid))


rate_limiter = RateLimiter(RATE_LIMIT_MAX, RATE_LIMIT_WINDOW)


# ============================================================================
# Helper Functions
# ============================================================================

def format_user_info(user: User) -> str:
    """Format user information for owner."""
    username = f"@{user.username}" if user.username else "ندارد"
    return (
        f"📨 <b>پیام جدید از کاربر</b>\n\n"
        f"👤 <b>نام:</b> {user.full_name}\n"
        f"🔗 <b>یوزرنیم:</b> {username}\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>"
    )


async def forward_to_owner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_msg: Message
) -> Optional[Message]:
    """Forward user message to owner with metadata."""
    user = update.effective_user
    if not user:
        return None

    # Send user info first
    info_text = format_user_info(user)
    info_msg = await context.bot.send_message(
        chat_id=OWNER_ID,
        text=info_text,
        parse_mode=ParseMode.HTML,
    )

    # Forward/copy the actual message
    try:
        if user_msg.text:
            forwarded = await context.bot.send_message(
                chat_id=OWNER_ID,
                text=user_msg.text_html or user_msg.text,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=info_msg.message_id,
            )
        elif user_msg.photo:
            forwarded = await context.bot.send_photo(
                chat_id=OWNER_ID,
                photo=user_msg.photo[-1].file_id,
                caption=user_msg.caption_html or user_msg.caption,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=info_msg.message_id,
            )
        elif user_msg.video:
            forwarded = await context.bot.send_video(
                chat_id=OWNER_ID,
                video=user_msg.video.file_id,
                caption=user_msg.caption_html or user_msg.caption,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=info_msg.message_id,
            )
        elif user_msg.document:
            forwarded = await context.bot.send_document(
                chat_id=OWNER_ID,
                document=user_msg.document.file_id,
                caption=user_msg.caption_html or user_msg.caption,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=info_msg.message_id,
            )
        elif user_msg.audio:
            forwarded = await context.bot.send_audio(
                chat_id=OWNER_ID,
                audio=user_msg.audio.file_id,
                caption=user_msg.caption_html or user_msg.caption,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=info_msg.message_id,
            )
        elif user_msg.voice:
            forwarded = await context.bot.send_voice(
                chat_id=OWNER_ID,
                voice=user_msg.voice.file_id,
                caption=user_msg.caption_html or user_msg.caption,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=info_msg.message_id,
            )
        elif user_msg.sticker:
            forwarded = await context.bot.send_sticker(
                chat_id=OWNER_ID,
                sticker=user_msg.sticker.file_id,
                reply_to_message_id=info_msg.message_id,
            )
        else:
            # Fallback: try to copy
            forwarded = await context.bot.copy_message(
                chat_id=OWNER_ID,
                from_chat_id=user_msg.chat_id,
                message_id=user_msg.message_id,
                reply_to_message_id=info_msg.message_id,
            )

        return forwarded

    except Exception as e:
        logger.error(f"Failed to forward message: {e}")
        return None


async def send_reply_to_user(
    context: ContextTypes.DEFAULT_TYPE,
    user_chat_id: int,
    reply_msg: Message
) -> bool:
    """Send owner's reply to the original user."""
    try:
        if reply_msg.text:
            await context.bot.send_message(
                chat_id=user_chat_id,
                text=reply_msg.text_html or reply_msg.text,
                parse_mode=ParseMode.HTML,
            )
        elif reply_msg.photo:
            await context.bot.send_photo(
                chat_id=user_chat_id,
                photo=reply_msg.photo[-1].file_id,
                caption=reply_msg.caption_html or reply_msg.caption,
                parse_mode=ParseMode.HTML,
            )
        elif reply_msg.video:
            await context.bot.send_video(
                chat_id=user_chat_id,
                video=reply_msg.video.file_id,
                caption=reply_msg.caption_html or reply_msg.caption,
                parse_mode=ParseMode.HTML,
            )
        elif reply_msg.document:
            await context.bot.send_document(
                chat_id=user_chat_id,
                document=reply_msg.document.file_id,
                caption=reply_msg.caption_html or reply_msg.caption,
                parse_mode=ParseMode.HTML,
            )
        elif reply_msg.audio:
            await context.bot.send_audio(
                chat_id=user_chat_id,
                audio=reply_msg.audio.file_id,
                caption=reply_msg.caption_html or reply_msg.caption,
                parse_mode=ParseMode.HTML,
            )
        elif reply_msg.voice:
            await context.bot.send_voice(
                chat_id=user_chat_id,
                voice=reply_msg.voice.file_id,
                caption=reply_msg.caption_html or reply_msg.caption,
                parse_mode=ParseMode.HTML,
            )
        elif reply_msg.sticker:
            await context.bot.send_sticker(
                chat_id=user_chat_id,
                sticker=reply_msg.sticker.file_id,
            )
        else:
            # Fallback: try to copy
            await context.bot.copy_message(
                chat_id=user_chat_id,
                from_chat_id=reply_msg.chat_id,
                message_id=reply_msg.message_id,
            )
        return True

    except Exception as e:
        logger.error(f"Failed to send reply to user {user_chat_id}: {e}")
        return False


# ============================================================================
# Handlers
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    if not user:
        return

    if user.id == OWNER_ID:
        # Owner gets admin instructions
        text = (
            "🛠 <b>پنل مدیریت بات ناشناس</b>\n\n"
            "برای پاسخ دادن به کاربران:\n"
            "۱. پیامی که بات برای شما فوروارد کرده را پیدا کنید\n"
            "۲. روی آن پیام <b>Reply</b> (پاسخ) بزنید\n"
            "۳. پاسخ خود را بنویسید و بفرستید\n\n"
            "پاسخ به‌صورت ناشناس از طرف بات برای کاربر ارسال می‌شود.\n"
            "کاربر هرگز اطلاعات حساب شخصی شما را نخواهد دید."
        )
    else:
        # Regular user gets welcome message
        text = (
            "👋 <b>سلام! به بات پیام ناشناس خوش آمدید.</b>\n\n"
            "📨 هر پیامی که اینجا بفرستید، مستقیماً برای صاحب بات ارسال می‌شود.\n"
            "✍️ لطفاً پیام خود را بنویسید و بفرستید..."
        )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def handle_user_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle private messages from regular users."""
    user = update.effective_user
    message = update.message

    if not user or not message:
        return

    # Ignore messages from owner in this handler
    if user.id == OWNER_ID:
        return

    # Rate limiting
    if not rate_limiter.is_allowed(user.id):
        remaining_time = RATE_LIMIT_WINDOW
        await message.reply_text(
            f"⏳ <b>محدودیت ارسال پیام</b>\n\n"
            f"شما در {RATE_LIMIT_WINDOW} ثانیه گذشته {RATE_LIMIT_MAX} پیام ارسال کرده‌اید.\n"
            f"لطفاً چند لحظه صبر کنید و دوباره تلاش کنید.",
            parse_mode=ParseMode.HTML
        )
        return

    # Forward to owner
    forwarded = await forward_to_owner(update, context, message)

    if forwarded:
        # Save mapping (both in-memory and SQLite)
        mapping = MessageMapping(
            owner_message_id=forwarded.message_id,
            user_chat_id=user.id,
            user_message_id=message.message_id,
            timestamp=time.time(),
        )
        _message_cache[forwarded.message_id] = mapping
        db.save_mapping(mapping)

        # Confirm to user
        await message.reply_text(
            "✅ <b>پیام شما ارسال شد.</b>\n"
            "صاحب بات به زودی پاسخ خواهد داد.",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.reply_text(
            "❌ <b>خطا در ارسال پیام.</b>\n"
            "لطفاً دوباره تلاش کنید.",
            parse_mode=ParseMode.HTML
        )


async def handle_owner_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle replies from owner to forwarded messages."""
    message = update.message

    if not message or message.from_user.id != OWNER_ID:
        return

    # Check if this is a reply to a forwarded message
    if not message.reply_to_message:
        return

    replied_msg_id = message.reply_to_message.message_id

    # Look up mapping (check cache first, then DB)
    mapping = _message_cache.get(replied_msg_id)
    if not mapping:
        mapping = db.get_mapping(replied_msg_id)
        if mapping:
            _message_cache[replied_msg_id] = mapping

    if not mapping:
        await message.reply_text(
            "❌ <b>خطا: مپینگ پیام پیدا نشد.</b>\n\n"
            "احتمالات:\n"
            "• پیام خیلی قدیمی است و مپینگ منقضی شده\n"
            "• بات ریستارت شده و مپینگ در حافظه نبوده (SQLite حل می‌کند)\n"
            "• پیام مورد نظر فوروارد شده توسط این بات نیست",
            parse_mode=ParseMode.HTML
        )
        return

    # Send reply to user
    success = await send_reply_to_user(context, mapping.user_chat_id, message)

    if success:
        await message.reply_text(
            f"✅ <b>پاسخ به کاربر ارسال شد.</b>\n"
            f"🆔 User ID: <code>{mapping.user_chat_id}</code>",
            parse_mode=ParseMode.HTML
        )
        # Clean up mapping after successful reply
        db.delete_mapping(replied_msg_id)
        _message_cache.pop(replied_msg_id, None)
    else:
        await message.reply_text(
            "❌ <b>خطا در ارسال پاسخ به کاربر.</b>\n"
            "ممکن است کاربر بات را بلاک کرده باشد.",
            parse_mode=ParseMode.HTML
        )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Log errors."""
    logger.error(f"Exception while handling update: {context.error}", exc_info=context.error)


# ============================================================================
# Application Setup
# ============================================================================

def load_mappings_to_cache() -> int:
    """Load all mappings from SQLite to in-memory cache on startup."""
    global _message_cache
    count = 0
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT * FROM message_mappings")
        for row in cursor.fetchall():
            mapping = MessageMapping(*row)
            _message_cache[mapping.owner_message_id] = mapping
            count += 1
    return count


def main() -> None:
    """Main entry point."""
    # Load mappings from SQLite
    loaded = load_mappings_to_cache()
    logger.info(f"Loaded {loaded} message mappings from database")

    # Build application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))

    # User messages (private chats, not from owner)
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.User(OWNER_ID) & ~filters.COMMAND,
            handle_user_message,
        )
    )

    # Owner replies (private chat, from owner, is a reply)
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.User(OWNER_ID) & filters.REPLY,
            handle_owner_reply,
        )
    )

    # Error handler
    application.add_error_handler(error_handler)

    # Run with long polling
    logger.info("Starting bot with long polling...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    # Initialize database
    db = MessageDatabase(DB_PATH)
    # Cleanup old mappings on startup
    cleaned = db.cleanup_old()
    if cleaned:
        logger.info(f"Cleaned up {cleaned} old mappings")

    main()
