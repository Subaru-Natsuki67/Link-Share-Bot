import asyncio
import base64
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from pyrogram import Client
from pyrogram.errors import (
    ChatAdminRequired,
    FloodWait,
    MessageDeleteForbidden,
    MessageIdInvalid,
    MessageNotModified,
    UserNotParticipant,
)
from pyrogram.types import ChatInviteLink, InlineKeyboardButton, Message

from config import FORCE_SUB_CHANNEL, LINK_EXPIRY_SECONDS, LOGGER

logger = LOGGER(__name__)

# Token prefix that flags a request-join deep-link
REQ_PREFIX = "req_"


# ──────────────────────────────────────────────────────────────────────────────
#  Low-level base64
# ──────────────────────────────────────────────────────────────────────────────

async def encode(string: str) -> str:
    b64 = base64.urlsafe_b64encode(string.encode("ascii"))
    return b64.decode("ascii").strip("=")


async def decode(b64_string: str) -> str:
    b64_string = b64_string.strip("=")
    padded = b64_string + "=" * (-len(b64_string) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")


# ──────────────────────────────────────────────────────────────────────────────
#  Channel ID ↔ token
# ──────────────────────────────────────────────────────────────────────────────

async def encode_channel_id(channel_id: int) -> str:
    """Normal deep-link token: base64url(str(channel_id))."""
    return await encode(str(channel_id))


async def encode_req_channel_id(channel_id: int) -> str:
    """Request deep-link token: req_ + base64url(str(channel_id))."""
    return f"{REQ_PREFIX}{await encode(str(channel_id))}"


async def decode_channel_token(token: str) -> tuple[Optional[int], bool]:
    """
    Decode any deep-link token → (channel_id, is_request_link).

    Handles:
      req_<b64>   → request-join flow  (is_request_link=True)
      <b64>       → normal invite flow (is_request_link=False)
      Legacy "channel_<id>" prefix (older forks)

    Returns (None, False) on any failure.
    """
    try:
        is_req  = token.startswith(REQ_PREFIX)
        raw_b64 = token[len(REQ_PREFIX):] if is_req else token
        raw     = await decode(raw_b64)

        stripped = raw.strip()
        if stripped.lstrip("-").isdigit():
            return int(stripped), is_req

        if raw.startswith("channel_"):
            return int(raw.split("channel_", 1)[1]), is_req

    except Exception:
        pass

    return None, False


# ──────────────────────────────────────────────────────────────────────────────
#  Build both deep-link URLs  (username fetched live — never stored in DB)
# ──────────────────────────────────────────────────────────────────────────────

async def build_links(client: Client, channel_id: int) -> tuple[str, str]:
    """
    Return (normal_deep_link, request_deep_link).

    Both use the bot's live username from Telegram — renaming the bot
    never breaks existing tokens because the token only encodes channel_id.
    """
    me = await client.get_me()
    bot_username = me.username
    normal_token = await encode_channel_id(channel_id)
    req_token    = await encode_req_channel_id(channel_id)
    return (
        f"https://t.me/{bot_username}?start={normal_token}",
        f"https://t.me/{bot_username}?start={req_token}",
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Invite-link generation
# ──────────────────────────────────────────────────────────────────────────────

async def get_invite_link(client: Client, channel_id: int) -> Optional[str]:
    """
    Generate a temporary, single-use invite link.
    - Expires in LINK_EXPIRY_SECONDS (default 5 min).
    - member_limit=1 → auto-revokes after one use.
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
        logger.error(
            "Bot lacks invite-link admin rights in channel %s.", channel_id
        )
    except FloodWait as e:
        logger.warning("FloodWait %ss — waiting before retry for channel %s.", e.value, channel_id)
        await asyncio.sleep(e.value + 1)
        return await get_invite_link(client, channel_id)
    except Exception as e:
        logger.exception("Error generating invite link for %s: %s", channel_id, e)
    return None


async def get_request_invite_link(client: Client, channel_id: int) -> Optional[str]:
    """
    Generate a temporary request-join link.

    The link creates_join_request=True, meaning the user taps it to
    *send a join request* which the channel admin approves/denies.

    We still set an expiry (LINK_EXPIRY_SECONDS) so the link can't be
    scraped and reused indefinitely — but it has NO member_limit so every
    user who taps the deep-link before expiry can send their request.

    Note: a new fresh link is generated on every deep-link click, so
    users always get a valid URL.
    """
    expire_at = datetime.now(timezone.utc) + timedelta(seconds=LINK_EXPIRY_SECONDS)
    try:
        link: ChatInviteLink = await client.create_chat_invite_link(
            chat_id=channel_id,
            expire_date=expire_at,          # temp — not permanent
            creates_join_request=True,      # sends join request, not direct join
        )
        return link.invite_link
    except ChatAdminRequired:
        logger.error(
            "Bot lacks admin rights in channel %s for request link.", channel_id
        )
    except FloodWait as e:
        logger.warning("FloodWait %ss — waiting before retry for channel %s.", e.value, channel_id)
        await asyncio.sleep(e.value + 1)
        return await get_request_invite_link(client, channel_id)
    except Exception as e:
        logger.exception("Error generating request link for %s: %s", channel_id, e)
    return None


# ──────────────────────────────────────────────────────────────────────────────
#  Force-subscription check
# ──────────────────────────────────────────────────────────────────────────────

async def is_subscribed(client: Client, user_id: int) -> bool:
    """True if FORCE_SUB_CHANNEL is disabled OR the user is an active member."""
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        from pyrogram.enums import ChatMemberStatus
        member = await client.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        return member.status not in (
            ChatMemberStatus.BANNED,
            ChatMemberStatus.LEFT,
        )
    except UserNotParticipant:
        return False
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await is_subscribed(client, user_id)
    except Exception:
        return True   # fail-open — don't lock users out on Telegram glitches


# ──────────────────────────────────────────────────────────────────────────────
#  Safe message helpers  (never crash on stale messages)
# ──────────────────────────────────────────────────────────────────────────────

async def safe_delete(message: Message) -> None:
    """Delete a message, silently ignoring errors (already deleted, no permission, etc.)."""
    try:
        await message.delete()
    except (MessageDeleteForbidden, MessageIdInvalid, Exception):
        pass


async def safe_edit(message: Message, text: str, **kwargs) -> None:
    """Edit a message, silently ignoring MessageNotModified and similar."""
    try:
        await message.edit_text(text, **kwargs)
    except MessageNotModified:
        pass
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        await safe_edit(message, text, **kwargs)
    except Exception as e:
        logger.warning("safe_edit failed: %s", e)


# ──────────────────────────────────────────────────────────────────────────────
#  Pagination keyboard helper
# ──────────────────────────────────────────────────────────────────────────────

def paginate_keyboard(
    items: list[tuple[str, str]],
    page: int,
    per_page: int = 5,
    prefix: str = "page",
) -> tuple[list, int, int]:
    """
    Build paginated keyboard rows.

    Args:
        items    : list of (button_label, callback_data)
        page     : current 0-indexed page
        per_page : items per page
        prefix   : callback_data prefix for nav buttons

    Returns:
        (keyboard_rows, current_page, total_pages)
    """
    total       = len(items)
    total_pages = max(1, math.ceil(total / per_page))
    page        = max(0, min(page, total_pages - 1))

    chunk = items[page * per_page : page * per_page + per_page]
    rows  = [[InlineKeyboardButton(label, callback_data=cb)] for label, cb in chunk]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("« Prev", callback_data=f"{prefix}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next »", callback_data=f"{prefix}:{page + 1}"))
    if nav:
        rows.append(nav)

    return rows, page, total_pages