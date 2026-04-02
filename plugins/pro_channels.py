"""
plugins/pro_channels.py
~~~~~~~~~~~~~~~~~~~~~~~
PRO FEATURE — Auto-link generator on bot-added-to-channel event.

When the bot is promoted to admin in any channel, it automatically:
  1. Registers the channel in the database (if not already registered).
  2. Generates both the Normal deep-link and the Request deep-link.
  3. Sends both links to the bot owner via DM.

This file is completely self-contained.
Delete or remove it from the plugins/ directory at any time — it will
not affect any other feature, command, or file.

No bot username is stored in the database. Links are always built live
so they stay valid even if you rename the bot.
"""

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from config import LOGGER, OWNER_ID
from database import CosmicBotz
from helper_func import build_links

logger = LOGGER(__name__)


# ──────────────────────────────────────────────────────────────────────────────
#  my_chat_member update — fires when the bot's status changes in any chat
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_my_chat_member()
async def on_bot_added_to_channel(client: Client, update: ChatMemberUpdated):
    """
    Triggered every time the bot's membership / admin status changes.
    We only care about the bot being promoted to admin in a channel.
    """
    new = update.new_chat_member

    # Only act when the bot becomes admin (or creator)
    if new is None:
        return
    if new.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        return

    chat = update.chat
    # Only handle channels (not groups/supergroups unless you want that too)
    if str(chat.type) not in ("ChatType.CHANNEL", "channel"):
        # PyroFork exposes enums differently depending on version; handle both
        try:
            from pyrogram.enums import ChatType
            if chat.type != ChatType.CHANNEL:
                return
        except Exception:
            pass

    channel_id = chat.id
    ch_name = chat.title or str(channel_id)

    logger.info(
        "[Pro] Bot promoted to admin in channel %s (%s).", channel_id, ch_name
    )

    # Register channel (no-op if already registered, refreshes name)
    added = await CosmicBotz.add_channel(channel_id, ch_name)
    if not added:
        await CosmicBotz.update_channel_name(channel_id, ch_name)

    # Build both links (live username — never persisted)
    try:
        normal_link, req_deep_link = await build_links(client, channel_id)
    except Exception as e:
        logger.error("[Pro] Failed to build links for %s: %s", channel_id, e)
        # Still notify owner, but without links
        try:
            await client.send_message(
                OWNER_ID,
                f"⚡ <b>[Pro] Bot added to channel</b>\n\n"
                f"📢 <b>{ch_name}</b>  (<code>{channel_id}</code>)\n\n"
                "⚠️ Could not generate links — ensure the bot has invite-link permission.",
            )
        except Exception:
            pass
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Normal Link", url=normal_link)],
        [InlineKeyboardButton("📩 Request Link", url=req_deep_link)],
    ])

    try:
        await client.send_message(
            OWNER_ID,
            f"⚡ <b>[Pro] Bot added as admin!</b>\n\n"
            f"✅ Cʜᴀᴛ <b>{ch_name}</b> (<code>{channel_id}</code>) "
            f"ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ.\n\n"
            f"🔗 Nᴏʀᴍᴀʟ Lɪɴᴋ:\n<code>{normal_link}</code>\n\n"
            f"🔗 Rᴇǫᴜᴇsᴛ Lɪɴᴋ:\n<code>{req_deep_link}</code>",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        logger.info(
            "[Pro] Notified owner with both links for channel %s.", channel_id
        )
    except Exception as e:
        logger.error("[Pro] Could not DM owner for channel %s: %s", channel_id, e)
