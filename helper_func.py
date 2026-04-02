"""
helper_func.py
~~~~~~~~~~~~~~
Shared utilities:
  - Base64 encode / decode for obfuscating channel IDs in deep-links
  - Invite-link generation (temporary, auto-revoke)
  - Force-subscription check
  - Pagination helpers
"""
import asyncio
import base64
import math
import string
import time
from typing import Union

from pyrogram import Client
from pyrogram.errors import (
    ChatAdminRequired,
    FloodWait,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import ChatInviteLink, InlineKeyboardButton, InlineKeyboardMarkup

from config import FORCE_SUB_CHANNEL, LINK_EXPIRY_SECONDS, LOGGER

logger = LOGGER(__name__)


# ──────────────────────────────────────────────────────────────────────────────
#  Encode / Decode  (URL-safe base64, no padding)
# ──────────────────────────────────────────────────────────────────────────────

async def encode(string: str) -> str:
    """Encode a plain string → URL-safe base64 (no '=' padding)."""
    b64 = base64.urlsafe_b64encode(string.encode("ascii"))
    return b64.decode("ascii").strip("=")


async def decode(base64_string: str) -> str:
    """Decode a URL-safe base64 string (padding is added automatically)."""
    base64_string = base64_string.strip("=")
    padded = base64_string + "=" * (-len(base64_string) % 4)
    string_bytes = base64.urlsafe_b64decode(padded.encode("ascii"))
    return string_bytes.decode("ascii")


# ──────────────────────────────────────────────────────────────────────────────
#  Channel ID helpers
# ──────────────────────────────────────────────────────────────────────────────

async def encode_channel_id(channel_id: int) -> str:
    """Turn a channel_id (int) into an encoded deep-link token."""
    return await encode(f"channel_{channel_id}")


async def decode_channel_token(token: str) -> Union[int, None]:
    """
    Decode a deep-link token back to a channel_id int.
    Returns None if token is invalid / not a channel token.
    """
    try:
        raw = await decode(token)
        if raw.startswith("channel_"):
            return int(raw.split("channel_")[1])
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────────────────────────
#  Invite-link generation
# ──────────────────────────────────────────────────────────────────────────────

async def get_invite_link(client: Client, channel_id: int) -> Union[str, None]:
    """
    Create a fresh temporary invite link for *channel_id*.
    - Expires in LINK_EXPIRY_SECONDS (default 5 min)
    - Creates one use only (member_limit=1) so the link auto-revokes
    Returns the invite URL string, or None on failure.
    """
    expire_at = int(time.time()) + LINK_EXPIRY_SECONDS
    try:
        link: ChatInviteLink = await client.create_chat_invite_link(
            chat_id=channel_id,
            expire_date=expire_at,
            member_limit=1,
        )
        return link.invite_link
    except ChatAdminRequired:
        logger.error("Bot is not admin in channel %s (needs invite link permission).", channel_id)
    except FloodWait as e:
        logger.warning("FloodWait %ss while generating invite for %s.", e.value, channel_id)
        await asyncio.sleep(e.value)
        return await get_invite_link(client, channel_id)
    except Exception as e:
        logger.exception("Unexpected error generating invite link for %s: %s", channel_id, e)
    return None


async def get_request_invite_link(client: Client, channel_id: int) -> Union[str, None]:
    """
    Create a join-request invite link (no member limit, no expiry).
    Admins can then approve / deny from channel admin panel.
    """
    try:
        link: ChatInviteLink = await client.create_chat_invite_link(
            chat_id=channel_id,
            creates_join_request=True,
        )
        return link.invite_link
    except ChatAdminRequired:
        logger.error("Bot lacks admin permission in channel %s.", channel_id)
    except Exception as e:
        logger.exception("Error creating request link for %s: %s", channel_id, e)
    return None


# ──────────────────────────────────────────────────────────────────────────────
#  Force-subscription check
# ──────────────────────────────────────────────────────────────────────────────

async def is_subscribed(client: Client, user_id: int) -> bool:
    """Return True if FORCE_SUB_CHANNEL is disabled OR the user is a member."""
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        member = await client.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        return member.status not in (
            member.status.BANNED,
            member.status.LEFT,
        ) if hasattr(member, "status") else True
    except UserNotParticipant:
        return False
    except Exception:
        return True  # fail-open so bot doesn't become unusable


# ──────────────────────────────────────────────────────────────────────────────
#  Pagination keyboard helper
# ──────────────────────────────────────────────────────────────────────────────

def paginate_keyboard(
    items: list[tuple[str, str]],  # [(label, callback_data), ...]
    page: int,
    per_page: int = 5,
    prefix: str = "page",
) -> tuple[list, int, int]:
    """
    Returns (keyboard_rows, current_page, total_pages).
    Adds ← / → navigation buttons when needed.
    """
    total = len(items)
    total_pages = max(1, math.ceil(total / per_page))
    page = max(0, min(page, total_pages - 1))

    start = page * per_page
    chunk = items[start : start + per_page]

    rows = [[InlineKeyboardButton(label, callback_data=cb)] for label, cb in chunk]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"{prefix}:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"{prefix}:{page+1}"))
    if nav:
        rows.append(nav)

    return rows, page, total_pages
