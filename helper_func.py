"""
helper_func.py
~~~~~~~~~~~~~~
Shared utilities:
  - Base64 encode / decode for obfuscating channel IDs in deep-links
  - Two deep-link flavours:
      Normal  →  ?start=<b64(channel_id)>        → bot generates temp invite
      Request →  ?start=req_<b64(channel_id)>    → bot forwards to request-join link
  - Invite-link generation (temporary, auto-revoke)
  - Request-join link generation (permanent, approval required)
  - Force-subscription check
  - Pagination helpers
"""
import asyncio
import base64
import math
from datetime import datetime, timedelta, timezone
from typing import Union

from pyrogram import Client
from pyrogram.errors import ChatAdminRequired, FloodWait, UserNotParticipant
from pyrogram.types import ChatInviteLink, InlineKeyboardButton

from config import FORCE_SUB_CHANNEL, LINK_EXPIRY_SECONDS, LOGGER

logger = LOGGER(__name__)

# ── Token prefix for request-join deep-links ─────────────────────────────────
REQ_PREFIX = "req_"


# ──────────────────────────────────────────────────────────────────────────────
#  Low-level base64 helpers
# ──────────────────────────────────────────────────────────────────────────────

async def encode(string: str) -> str:
    """Encode a plain string → URL-safe base64 (no '=' padding)."""
    b64 = base64.urlsafe_b64encode(string.encode("ascii"))
    return b64.decode("ascii").strip("=")


async def decode(base64_string: str) -> str:
    """Decode a URL-safe base64 string (padding is added automatically)."""
    base64_string = base64_string.strip("=")
    padded = base64_string + "=" * (-len(base64_string) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")


# ──────────────────────────────────────────────────────────────────────────────
#  Channel ID → deep-link token helpers
# ──────────────────────────────────────────────────────────────────────────────

async def encode_channel_id(channel_id: int) -> str:
    """
    Encode channel_id for a *normal* deep-link.
    Token = base64url( str(channel_id) )
    e.g. -1002492815676  →  "LTEwMDI0OTI4MTU2NzY"
    """
    return await encode(str(channel_id))


async def encode_req_channel_id(channel_id: int) -> str:
    """
    Encode channel_id for a *request-join* deep-link.
    Token = "req_" + base64url( str(channel_id) )
    e.g. -1002492815676  →  "req_LTEwMDI0OTI4MTU2NzY"
    """
    b64 = await encode(str(channel_id))
    return f"{REQ_PREFIX}{b64}"


async def decode_channel_token(token: str) -> tuple[Union[int, None], bool]:
    """
    Decode any deep-link token back to (channel_id, is_request_link).

    Handles:
      • req_<b64>  → request-join flow  (is_request_link = True)
      • <b64>      → normal invite flow  (is_request_link = False)
      • Legacy old-format tokens (bare base64 of channel_id int string)

    Returns (None, False) if the token cannot be decoded.
    """
    try:
        is_req = token.startswith(REQ_PREFIX)
        raw_b64 = token[len(REQ_PREFIX):] if is_req else token

        raw = await decode(raw_b64)

        # ── New format: base64(channel_id_string) e.g. "-1001234567890" ──────
        stripped = raw.strip()
        if stripped.lstrip("-").isdigit():
            return int(stripped), is_req

        # ── Even older "channel_<id>" format from some forks ─────────────────
        if raw.startswith("channel_"):
            return int(raw.split("channel_", 1)[1]), is_req

    except Exception:
        pass
    return None, False


# ──────────────────────────────────────────────────────────────────────────────
#  Build both deep-link URLs (bot username fetched live — never from DB)
# ──────────────────────────────────────────────────────────────────────────────

async def build_links(client: Client, channel_id: int) -> tuple[str, str]:
    """
    Return (normal_deep_link, request_deep_link) for channel_id.
    Bot username is fetched from Telegram at call time so renaming the bot
    never breaks anything — nothing is persisted in the database.
    """
    me = await client.get_me()
    bot_username = me.username

    normal_token = await encode_channel_id(channel_id)
    req_token    = await encode_req_channel_id(channel_id)

    normal_link = f"https://t.me/{bot_username}?start={normal_token}"
    req_link    = f"https://t.me/{bot_username}?start={req_token}"
    return normal_link, req_link


# ──────────────────────────────────────────────────────────────────────────────
#  Invite-link generation
# ──────────────────────────────────────────────────────────────────────────────

async def get_invite_link(client: Client, channel_id: int) -> Union[str, None]:
    """
    Create a fresh temporary invite link for *channel_id*.
    - Expires in LINK_EXPIRY_SECONDS (default 5 min)
    - Single-use (member_limit=1) so it auto-revokes after one join.
    Returns the invite URL string, or None on failure.
    """
    expire_at = datetime.now(timezone.utc) + timedelta(seconds=LINK_EXPIRY_SECONDS)
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
        return True  # fail-open so the bot doesn't become unusable


# ──────────────────────────────────────────────────────────────────────────────
#  Pagination keyboard helper
# ──────────────────────────────────────────────────────────────────────────────

def paginate_keyboard(
    items: list[tuple[str, str]],   # [(label, callback_data), ...]
    page: int,
    per_page: int = 5,
    prefix: str = "page",
) -> tuple[list, int, int]:
    """
    Returns (keyboard_rows, current_page, total_pages).
    Adds ◀ / ▶ navigation buttons when needed.
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
