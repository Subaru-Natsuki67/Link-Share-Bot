"""
plugins/start.py
~~~~~~~~~~~~~~~~
Handles /start  — including deep-link tokens that resolve to temporary
invite links for private channels.

Deep-link format:
    t.me/<botusername>?start=<encoded_token>

Where <encoded_token> = base64url( "channel_<channel_id>" )
"""
import asyncio

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ADMINS, FORCE_SUB_CHANNEL, LOGGER, OWNER_ID
from database import CosmicBotz
from helper_func import (
    decode_channel_token,
    encode_channel_id,
    get_invite_link,
    is_subscribed,
)

logger = LOGGER(__name__)

# ──────────────────────────────────────────────────────────────────────────────
#  Force-sub keyboard builder
# ──────────────────────────────────────────────────────────────────────────────

async def _force_sub_keyboard(client: Client, deep_token: str) -> InlineKeyboardMarkup:
    """Build a keyboard asking the user to join FORCE_SUB_CHANNEL first."""
    try:
        chat = await client.get_chat(FORCE_SUB_CHANNEL)
        link = chat.invite_link or (
            await client.create_chat_invite_link(FORCE_SUB_CHANNEL)
        ).invite_link
    except Exception:
        link = "https://t.me"

    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔔 Join Channel", url=link)],
            [
                InlineKeyboardButton(
                    "✅ I've Joined",
                    callback_data=f"check_sub:{deep_token}",
                )
            ],
        ]
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /start  (no payload)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("start") & filters.private & ~filters.forwarded)
async def start_handler(client: Client, message: Message):
    user = message.from_user
    # Register user
    if await CosmicBotz.add_user(user.id):
        logger.info("New user registered: %s (%s)", user.id, user.username)

    args = message.command  # ['start'] or ['start', '<token>']

    # ── Deep-link with channel token ──────────────────────────────────────────
    if len(args) > 1:
        token = args[1]
        channel_id = await decode_channel_token(token)

        if channel_id is None:
            await message.reply_text(
                "❌ <b>Invalid or expired link.</b>\n"
                "Please ask the owner for a fresh link."
            )
            return

        # Force-sub check
        if FORCE_SUB_CHANNEL and not await is_subscribed(client, user.id):
            keyboard = await _force_sub_keyboard(client, token)
            await message.reply_text(
                "🔒 <b>You must join our channel to use this bot.</b>\n\n"
                "Click the button below, then tap <b>I've Joined</b>.",
                reply_markup=keyboard,
            )
            return

        # Verify channel is in DB
        if not await CosmicBotz.is_channel_exist(channel_id):
            await message.reply_text(
                "❌ <b>This channel is no longer registered with the bot.</b>"
            )
            return

        wait_msg = await message.reply_text("🔗 <i>Generating your invite link…</i>")

        invite_url = await get_invite_link(client, channel_id)
        await wait_msg.delete()

        if not invite_url:
            await message.reply_text(
                "⚠️ <b>Failed to generate invite link.</b>\n"
                "The bot may not have admin rights in that channel."
            )
            return

        channel_doc = await CosmicBotz.get_channel(channel_id)
        ch_name = channel_doc.get("name", "the channel") if channel_doc else "the channel"

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"📢 Join {ch_name}", url=invite_url)]]
        )
        await message.reply_text(
            f"✅ <b>Here is your invite link for <i>{ch_name}</i>!</b>\n\n"
            "⏳ <b>This link expires in 5 minutes and is single-use.</b>\n"
            "Do not share it with others.",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        return

    # ── Plain /start — welcome message ────────────────────────────────────────
    bot_info = await client.get_me()
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👤 Owner", url=f"tg://user?id={OWNER_ID}"),
                InlineKeyboardButton(
                    "➕ Add to Channel",
                    url=f"https://t.me/{bot_info.username}?startchannel=true",
                ),
            ]
        ]
    )
    await message.reply_text(
        f"👋 <b>Hello, {user.mention}!</b>\n\n"
        "I help share <b>private Telegram channel links</b> securely.\n\n"
        "✅ Links are <b>temporary & single-use</b> — no permanent invite URLs ever exposed.\n"
        "🔒 Channels stay protected from copyright strikes.\n\n"
        "<b>Owners / Admins:</b> use <code>/addch &lt;channel_id&gt;</code> to register a channel,\n"
        "then use <code>/channels</code> to get shareable deep-links.",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Callback: "I've Joined" button after force-sub
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^check_sub:(.+)$"))
async def check_sub_callback(client: Client, callback_query):
    user = callback_query.from_user
    token = callback_query.matches[0].group(1)

    if not await is_subscribed(client, user.id):
        await callback_query.answer(
            "❌ You haven't joined yet! Please join and try again.", show_alert=True
        )
        return

    await callback_query.answer("✅ Verified!", show_alert=False)
    await callback_query.message.delete()

    # Re-trigger start with the token
    channel_id = await decode_channel_token(token)
    if channel_id is None:
        await client.send_message(user.id, "❌ Invalid or expired link.")
        return

    if not await CosmicBotz.is_channel_exist(channel_id):
        await client.send_message(user.id, "❌ Channel is no longer registered.")
        return

    invite_url = await get_invite_link(client, channel_id)
    if not invite_url:
        await client.send_message(
            user.id,
            "⚠️ Failed to generate link. Bot may lack admin rights in the channel.",
        )
        return

    channel_doc = await CosmicBotz.get_channel(channel_id)
    ch_name = channel_doc.get("name", "the channel") if channel_doc else "the channel"

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"📢 Join {ch_name}", url=invite_url)]]
    )
    await client.send_message(
        user.id,
        f"✅ <b>Your invite link for <i>{ch_name}</i>:</b>\n\n"
        "⏳ Expires in 5 minutes. Single-use only.",
        reply_markup=keyboard,
    )
