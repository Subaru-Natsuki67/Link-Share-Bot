"""
plugins/channel_mgmt.py
~~~~~~~~~~~~~~~~~~~~~~~~
Admin commands to manage registered channels:

  /addch  <channel_id>       — Register a channel
  /delch  <channel_id>       — Remove a channel
  /channels                  — Show all channels (paginated buttons)
  /links                     — List all channels with shareable deep-links
  /reqlink                   — Show all request-join links (paginated)
  /bulklink <id1> <id2> ...  — Bulk-generate invite links for multiple IDs
"""
import asyncio

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import ADMINS, LOGGER, OWNER_ID
from database import CosmicBotz
from helper_func import (
    encode_channel_id,
    get_invite_link,
    get_request_invite_link,
    paginate_keyboard,
)

logger = LOGGER(__name__)

# ── Reusable admin filter ─────────────────────────────────────────────────────
admin_filter = filters.user(ADMINS)


# ──────────────────────────────────────────────────────────────────────────────
#  /addch  <channel_id>
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("addch") & filters.private & admin_filter)
async def add_channel(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text(
            "❌ <b>Usage:</b> <code>/addch &lt;channel_id&gt;</code>\n\n"
            "Example: <code>/addch -1001234567890</code>"
        )
        return

    raw = message.command[1]
    try:
        channel_id = int(raw)
    except ValueError:
        await message.reply_text("❌ Channel ID must be an integer (e.g. <code>-1001234567890</code>).")
        return

    # Try to fetch channel info to validate
    try:
        chat = await client.get_chat(channel_id)
        ch_name = chat.title or str(channel_id)
    except Exception:
        await message.reply_text(
            "⚠️ Could not fetch channel info. Make sure:\n"
            "• The bot is an <b>admin</b> in the channel.\n"
            "• The channel ID is correct."
        )
        return

    added = await CosmicBotz.add_channel(channel_id, ch_name)
    if not added:
        # Update name in case it changed
        await CosmicBotz.update_channel_name(channel_id, ch_name)
        await message.reply_text(
            f"ℹ️ Channel <b>{ch_name}</b> is already registered.\n"
            "Channel name has been refreshed."
        )
        return

    token = await encode_channel_id(channel_id)
    bot_info = await client.get_me()
    deep_link = f"https://t.me/{bot_info.username}?start={token}"

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔗 Share This Link", url=deep_link)]]
    )
    await message.reply_text(
        f"✅ <b>Channel added:</b> <i>{ch_name}</i>\n\n"
        f"🆔 <b>ID:</b> <code>{channel_id}</code>\n\n"
        f"📎 <b>Shareable deep-link:</b>\n<code>{deep_link}</code>\n\n"
        "Share this link with users — they'll get a fresh temporary invite each time.",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    logger.info("Channel %s (%s) added by admin %s.", channel_id, ch_name, message.from_user.id)


# ──────────────────────────────────────────────────────────────────────────────
#  /delch  <channel_id>
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("delch") & filters.private & admin_filter)
async def del_channel(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ <b>Usage:</b> <code>/delch &lt;channel_id&gt;</code>")
        return

    try:
        channel_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Channel ID must be an integer.")
        return

    removed = await CosmicBotz.remove_channel(channel_id)
    if removed:
        await message.reply_text(f"✅ Channel <code>{channel_id}</code> has been removed.")
        logger.info("Channel %s removed by admin %s.", channel_id, message.from_user.id)
    else:
        await message.reply_text(f"❌ Channel <code>{channel_id}</code> was not found in the database.")


# ──────────────────────────────────────────────────────────────────────────────
#  /channels  — paginated button list
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("channels") & filters.private & admin_filter)
async def list_channels(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text("📭 No channels registered yet.\nUse <code>/addch &lt;channel_id&gt;</code> to add one.")
        return

    await _send_channels_page(client, message, channels, page=0)


async def _send_channels_page(client, message_or_query, channels, page: int):
    bot_info = await client.get_me()
    items = []
    for ch in channels:
        ch_id = ch["_id"]
        name = ch.get("name") or str(ch_id)
        token = await encode_channel_id(ch_id)
        deep_link = f"https://t.me/{bot_info.username}?start={token}"
        items.append((f"📢 {name}", f"chinfo:{ch_id}"))

    rows, cur_page, total_pages = paginate_keyboard(items, page, per_page=5, prefix="chpage")

    text = (
        f"📋 <b>Registered Channels</b>  [{cur_page+1}/{total_pages}]\n\n"
        f"Total: <b>{len(channels)}</b>\n"
        "Click a channel button to get its invite link."
    )

    if isinstance(message_or_query, Message):
        await message_or_query.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))
    else:  # CallbackQuery
        await message_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


@Client.on_callback_query(filters.regex(r"^chpage:(\d+)$") & admin_filter)
async def channels_page_callback(client: Client, cq: CallbackQuery):
    page = int(cq.matches[0].group(1))
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await cq.answer("No channels found.", show_alert=True)
        return
    await cq.answer()
    await _send_channels_page(client, cq, channels, page)


@Client.on_callback_query(filters.regex(r"^chinfo:(-?\d+)$") & admin_filter)
async def channel_info_callback(client: Client, cq: CallbackQuery):
    channel_id = int(cq.matches[0].group(1))
    bot_info = await client.get_me()
    token = await encode_channel_id(channel_id)
    deep_link = f"https://t.me/{bot_info.username}?start={token}"

    ch_doc = await CosmicBotz.get_channel(channel_id)
    name = ch_doc.get("name", str(channel_id)) if ch_doc else str(channel_id)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Copy Deep Link", url=deep_link)],
        [InlineKeyboardButton("🗑 Remove Channel", callback_data=f"rmch:{channel_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="chpage:0")],
    ])
    await cq.edit_message_text(
        f"📢 <b>{name}</b>\n"
        f"🆔 <code>{channel_id}</code>\n\n"
        f"🔗 Deep-link:\n<code>{deep_link}</code>",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


@Client.on_callback_query(filters.regex(r"^rmch:(-?\d+)$") & admin_filter)
async def remove_channel_callback(client: Client, cq: CallbackQuery):
    channel_id = int(cq.matches[0].group(1))
    await CosmicBotz.remove_channel(channel_id)
    await cq.answer(f"Channel {channel_id} removed.", show_alert=True)
    # Go back to page 0
    channels = await CosmicBotz.get_all_channels()
    if channels:
        await _send_channels_page(client, cq, channels, page=0)
    else:
        await cq.edit_message_text("📭 No channels registered.")


# ──────────────────────────────────────────────────────────────────────────────
#  /links  — text list with deep-links
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("links") & filters.private & admin_filter)
async def list_links(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text("📭 No channels registered.")
        return

    bot_info = await client.get_me()
    lines = ["<b>📋 All Channel Deep-Links:</b>\n"]
    for ch in channels:
        ch_id = ch["_id"]
        name = ch.get("name") or str(ch_id)
        token = await encode_channel_id(ch_id)
        link = f"https://t.me/{bot_info.username}?start={token}"
        lines.append(f"• <b>{name}</b>\n  <code>{link}</code>")

    # Split into chunks if very long
    text = "\n\n".join(lines)
    if len(text) > 4000:
        chunks = [lines[0]]
        buf = []
        for line in lines[1:]:
            buf.append(line)
            if len("\n\n".join(buf)) > 3500:
                await message.reply_text("\n\n".join(chunks + buf[:-1]), disable_web_page_preview=True)
                chunks = []
                buf = [line]
        if buf:
            await message.reply_text("\n\n".join(chunks + buf), disable_web_page_preview=True)
    else:
        await message.reply_text(text, disable_web_page_preview=True)


# ──────────────────────────────────────────────────────────────────────────────
#  /reqlink  — request-join links (paginated)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("reqlink") & filters.private & admin_filter)
async def req_links(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text("📭 No channels registered.")
        return

    wait = await message.reply_text("⏳ Generating join-request links…")
    lines = ["<b>📋 Join-Request Links:</b>\n"]

    for ch in channels:
        ch_id = ch["_id"]
        name = ch.get("name") or str(ch_id)
        link = await get_request_invite_link(client, ch_id)
        if link:
            lines.append(f"• <b>{name}</b>\n  <code>{link}</code>")
        else:
            lines.append(f"• <b>{name}</b>\n  ⚠️ Failed (bot not admin?)")

    await wait.delete()
    text = "\n\n".join(lines)
    await message.reply_text(text, disable_web_page_preview=True)


# ──────────────────────────────────────────────────────────────────────────────
#  /bulklink <id1> <id2> ...
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("bulklink") & filters.private & admin_filter)
async def bulk_link(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply_text(
            "❌ <b>Usage:</b> <code>/bulklink &lt;id1&gt; &lt;id2&gt; ...</code>\n"
            "Example: <code>/bulklink -1001234567890 -1009876543210</code>"
        )
        return

    wait = await message.reply_text(f"⏳ Generating invite links for {len(args)} channel(s)…")
    lines = [f"<b>🔗 Bulk Invite Links ({len(args)} channels):</b>\n"]

    bot_info = await client.get_me()
    for raw_id in args:
        try:
            ch_id = int(raw_id)
        except ValueError:
            lines.append(f"• <code>{raw_id}</code> — ❌ Invalid ID")
            continue

        link = await get_invite_link(client, ch_id)
        try:
            chat = await client.get_chat(ch_id)
            name = chat.title or raw_id
        except Exception:
            name = raw_id

        if link:
            lines.append(f"• <b>{name}</b>\n  <code>{link}</code>")
        else:
            lines.append(f"• <b>{name}</b> — ⚠️ Failed")

    await wait.delete()
    await message.reply_text("\n\n".join(lines), disable_web_page_preview=True)
