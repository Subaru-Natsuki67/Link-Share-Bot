import asyncio
import random

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified, QueryIdInvalid
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import (
    ABOUT_TEXT,
    FORCE_SUB_CHANNEL,
    HELP_TEXT,
    LOGGER,
    OWNER_ID,
    START_PICS,
    START_TEXT,
)
from database import CosmicBotz
from helper_func import (
    decode_channel_token,
    get_invite_link,
    get_request_invite_link,
    is_subscribed,
    safe_delete,
)

logger = LOGGER(__name__)


# ──────────────────────────────────────────────────────────────────────────────
#  Built-in default texts  (used when env vars are empty)
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_START = (
    "👋 <b>Hello, {mention}!</b>\n\n"
    "I help share <b>private Telegram channel links</b> securely.\n\n"
    "✅ Links are <b>temporary & single-use</b> — no permanent invite URLs ever exposed.\n"
    "🔒 Channels stay protected from copyright strikes.\n\n"
    "Tap <b>Help</b> below for the full command list."
)

_DEFAULT_HELP = (
    "📖 <b>Help — How This Bot Works</b>\n\n"
    "This bot gives you a <b>secure temporary link</b> to join a private "
    "Telegram channel — the real invite is never shared publicly.\n\n"
    "<b>For users:</b>\n"
    "• Tap a share link you received from the channel.\n"
    "• Normal link → instant join (valid 5 min, single-use).\n"
    "• Request link → sends a join request; admin approves.\n"
    "• If your link expired, click the original post link again.\n\n"
    "<b>For admins:</b>\n"
    "• <code>/addch &lt;id&gt;</code> — register a channel\n"
    "• <code>/delch &lt;id&gt;</code> — remove a channel\n"
    "• <code>/channels</code> — manage & get links\n"
    "• <code>/links</code> — all normal deep-links\n"
    "• <code>/reqlink</code> — all request deep-links\n"
    "• <code>/reqmode &lt;id&gt;</code> — toggle auto-approve requests\n"
    "• <code>/broadcast</code> — message all users\n"
    "• <code>/logs</code> — download log file (owner only)\n"
    "• <code>/stats</code> — bot statistics (owner only)"
)

_DEFAULT_ABOUT = (
    "ℹ️ <b>About This Bot</b>\n\n"
    "🤖 <b>CosmicBotz Link Share Bot</b>\n"
    "Built with ❤️ using PyroFork + MongoDB.\n\n"
    "🔒 Keeps private channels safe — no permanent invite links ever exposed.\n\n"
    "⚡ <b>Features:</b>\n"
    "• Temp single-use invite links (5 min expiry)\n"
    "• Temp request-join links (admin approves)\n"
    "• Auto-approve join requests with optional delay\n"
    "• Force-subscribe gate before link access\n"
    "• Broadcast to all users\n"
    "• Multiple start pictures (random pick)\n"
    "• Fully config-driven — no DB needed for bot texts"
)


# ──────────────────────────────────────────────────────────────────────────────
#  Text / pic helpers
# ──────────────────────────────────────────────────────────────────────────────

def _start_text(mention: str) -> str:
    base = START_TEXT or _DEFAULT_START
    return base.replace("{mention}", mention)

def _help_text() -> str:
    return HELP_TEXT or _DEFAULT_HELP

def _about_text() -> str:
    return ABOUT_TEXT or _DEFAULT_ABOUT

def _pick_pic() -> str | None:
    """Pick a random URL from START_PICS, or None if list is empty."""
    return random.choice(START_PICS) if START_PICS else None


# ──────────────────────────────────────────────────────────────────────────────
#  Keyboard builders
# ──────────────────────────────────────────────────────────────────────────────

async def _start_keyboard(client: Client) -> InlineKeyboardMarkup:
    me = await client.get_me()
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Owner", url=f"tg://user?id={OWNER_ID}"),
            InlineKeyboardButton(
                "➕ Add to Channel",
                url=f"https://t.me/{me.username}?startchannel=true",
            ),
        ],
        [
            InlineKeyboardButton("❓ Help",  callback_data="cb_help"),
            InlineKeyboardButton("ℹ️ About", callback_data="cb_about"),
        ],
    ])

def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Back", callback_data="cb_start")]]
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /start
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("start") & filters.private & ~filters.forwarded)
async def start_handler(client: Client, message: Message):
    user = message.from_user
    try:
        if await CosmicBotz.add_user(user.id):
            logger.info("New user registered: %s (%s)", user.id, user.username)
    except Exception as e:
        logger.warning("DB add_user failed for %s: %s", user.id, e)

    args = message.command

    # ── Deep-link flow ────────────────────────────────────────────────────────
    if len(args) > 1:
        token = args[1]
        channel_id, is_req = await decode_channel_token(token)

        if channel_id is None:
            await message.reply_text(
                "❌ <b>Invalid or expired link.</b>\n"
                "Please click the original post link again to get a fresh one."
            )
            return

        # Force-sub gate
        if FORCE_SUB_CHANNEL and not await is_subscribed(client, user.id):
            kb = await _force_sub_keyboard(client, token)
            await message.reply_text(
                "🔒 <b>You must join our channel to use this bot.</b>\n\n"
                "Click the button below, then tap <b>I've Joined</b>.",
                reply_markup=kb,
            )
            return

        # Ensure channel is known — auto-register if bot is still admin
        if not await CosmicBotz.is_channel_exist(channel_id):
            try:
                chat = await client.get_chat(channel_id)
                await CosmicBotz.add_channel(channel_id, chat.title or str(channel_id))
            except Exception:
                await message.reply_text(
                    "❌ <b>This channel is no longer accessible.</b>\n"
                    "The bot may have been removed or the channel was deleted."
                )
                return

        channel_doc = await CosmicBotz.get_channel(channel_id)
        ch_name = (channel_doc or {}).get("name") or str(channel_id)

        # ── Request-join flow ─────────────────────────────────────────────────
        if is_req:
            wait_msg = await message.reply_text("⏳ <i>Generating your link…</i>")
            req_url  = await get_request_invite_link(client, channel_id)
            await safe_delete(wait_msg)

            if not req_url:
                await message.reply_text(
                    "⚠️ <b>Failed to generate link.</b>\n"
                    "The bot may not have invite-link admin rights in that channel."
                )
                return

            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📩 Request to Join", url=req_url)
            ]])
            await message.reply_text(
                f"ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ! ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ\n\n"
                f"📢 <b>{ch_name}</b>\n\n"
                "<i>Note: If the link is expired, please click the post link again to get a new one.</i>",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            return

        # ── Normal (temp invite) flow ─────────────────────────────────────────
        wait_msg   = await message.reply_text("⏳ <i>Generating your link…</i>")
        invite_url = await get_invite_link(client, channel_id)
        await safe_delete(wait_msg)

        if not invite_url:
            await message.reply_text(
                "⚠️ <b>Failed to generate invite link.</b>\n"
                "The bot may not have admin rights in that channel.\n\n"
                "<i>Please click the post link again to retry.</i>"
            )
            return

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Join Now", url=invite_url)
        ]])
        await message.reply_text(
            f"ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ! ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ\n\n"
            f"📢 <b>{ch_name}</b>\n\n"
            "⏳ <b>This link expires in 5 minutes and is single-use.</b>\n"
            "<i>Note: If the link is expired, please click the post link again to get a new one.</i>",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        return

    # ── Plain /start — welcome ────────────────────────────────────────────────
    text     = _start_text(user.mention)
    pic      = _pick_pic()
    keyboard = await _start_keyboard(client)

    if pic:
        try:
            await message.reply_photo(photo=pic, caption=text, reply_markup=keyboard)
            return
        except Exception as e:
            logger.warning("Start photo failed (url=%s): %s — falling back to text.", pic, e)

    await message.reply_text(text, reply_markup=keyboard, disable_web_page_preview=True)


# ──────────────────────────────────────────────────────────────────────────────
#  /help
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    await message.reply_text(_help_text(), disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"^cb_help$"))
async def help_callback(client: Client, cq: CallbackQuery):
    try:
        await cq.edit_message_text(
            _help_text(), reply_markup=_back_keyboard(), disable_web_page_preview=True
        )
    except (MessageNotModified, QueryIdInvalid):
        pass
    await _safe_answer(cq)


# ──────────────────────────────────────────────────────────────────────────────
#  /about
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("about") & filters.private)
async def about_handler(client: Client, message: Message):
    await message.reply_text(_about_text(), disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"^cb_about$"))
async def about_callback(client: Client, cq: CallbackQuery):
    try:
        await cq.edit_message_text(
            _about_text(), reply_markup=_back_keyboard(), disable_web_page_preview=True
        )
    except (MessageNotModified, QueryIdInvalid):
        pass
    await _safe_answer(cq)


# ──────────────────────────────────────────────────────────────────────────────
#  Back to start
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^cb_start$"))
async def back_to_start_callback(client: Client, cq: CallbackQuery):
    text     = _start_text(cq.from_user.mention)
    keyboard = await _start_keyboard(client)
    try:
        await cq.edit_message_text(
            text, reply_markup=keyboard, disable_web_page_preview=True
        )
    except (MessageNotModified, QueryIdInvalid):
        pass
    await _safe_answer(cq)


# ──────────────────────────────────────────────────────────────────────────────
#  Force-sub keyboard
# ──────────────────────────────────────────────────────────────────────────────

async def _force_sub_keyboard(client: Client, deep_token: str) -> InlineKeyboardMarkup:
    try:
        chat = await client.get_chat(FORCE_SUB_CHANNEL)
        link = chat.invite_link or (
            await client.create_chat_invite_link(FORCE_SUB_CHANNEL)
        ).invite_link
    except Exception:
        link = "https://t.me"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔔 Join Channel", url=link)],
        [InlineKeyboardButton("✅ I've Joined",  callback_data=f"check_sub:{deep_token}")],
    ])


# ──────────────────────────────────────────────────────────────────────────────
#  Force-sub verification callback
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^check_sub:(.+)$"))
async def check_sub_callback(client: Client, cq: CallbackQuery):
    user  = cq.from_user
    token = cq.matches[0].group(1)

    if not await is_subscribed(client, user.id):
        await _safe_answer(cq, "❌ You haven't joined yet! Please join and try again.", alert=True)
        return

    await _safe_answer(cq, "✅ Verified!")
    await safe_delete(cq.message)

    channel_id, is_req = await decode_channel_token(token)
    if channel_id is None:
        await client.send_message(user.id, "❌ Invalid or expired link.")
        return

    if not await CosmicBotz.is_channel_exist(channel_id):
        await client.send_message(user.id, "❌ Channel is no longer registered.")
        return

    channel_doc = await CosmicBotz.get_channel(channel_id)
    ch_name = (channel_doc or {}).get("name") or str(channel_id)

    if is_req:
        req_url = await get_request_invite_link(client, channel_id)
        if not req_url:
            await client.send_message(
                user.id,
                "⚠️ Failed to generate request link. Bot may lack admin rights."
            )
            return
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📩 Request to Join", url=req_url)
        ]])
        await client.send_message(
            user.id,
            f"ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ! ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ\n\n"
            f"📢 <b>{ch_name}</b>\n\n"
            "<i>Note: If the link is expired, please click the post link again to get a new one.</i>",
            reply_markup=keyboard,
        )
        return

    invite_url = await get_invite_link(client, channel_id)
    if not invite_url:
        await client.send_message(
            user.id,
            "⚠️ Failed to generate invite link. Bot may lack admin rights."
        )
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📢 Join Now", url=invite_url)
    ]])
    await client.send_message(
        user.id,
        f"ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ! ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ\n\n"
        f"📢 <b>{ch_name}</b>\n\n"
        "⏳ <b>Expires in 5 minutes. Single-use only.</b>\n"
        "<i>Note: If the link is expired, please click the post link again to get a new one.</i>",
        reply_markup=keyboard,
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Internal: safe callback answer (never crash on expired query)
# ──────────────────────────────────────────────────────────────────────────────

async def _safe_answer(cq: CallbackQuery, text: str = "", alert: bool = False) -> None:
    try:
        await cq.answer(text, show_alert=alert)
    except QueryIdInvalid:
        pass
    except Exception as e:
        logger.debug("cq.answer failed: %s", e)
