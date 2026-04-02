"""
plugins/channel_mgmt.py
~~~~~~~~~~~~~~~~~~~~~~~~
Admin commands to manage registered channels:

  /addch  <channel_id>       — Register a channel (shows normal + request deep-links)
  /delch  <channel_id>       — Remove a channel
  /channels                  — Paginated list of channels with info button
  /links                     — Text list: normal deep-link per channel
  /reqlink                   — Text list: request deep-link per channel
  /bulklink <id1> <id2> ...  — Bulk-generate both link types for multiple IDs

Deep-links are always built using the bot's live username (fetched from Telegram).
Bot username is NEVER stored in the database — renaming the bot keeps all links valid.

Link formats:
  Normal  : https://t.me/<bot>?start=<b64(channel_id)>
  Request : https://t.me/<bot>?start=req_<b64(channel_id)>
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
    build_links,
    encode_channel_id,
    encode_req_channel_id,
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
        await message.reply_text(
            "❌ Channel ID must be an integer (e.g. <code>-1001234567890</code>)."
        )
        return

    # Validate: bot must be admin in the channel
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
        await CosmicBotz.update_channel_name(channel_id, ch_name)
        # Channel already existed — still show both links
        normal_link, req_deep_link = await build_links(client, channel_id)
        await message.reply_text(
            f"ℹ️ <b>Channel already registered.</b> Name refreshed.\n\n"
            f"✅ <b>{ch_name}</b>  (<code>{channel_id}</code>)\n\n"
            f"🔗 Nᴏʀᴍᴀʟ Lɪɴᴋ:\n<code>{normal_link}</code>\n\n"
            f"📩 Rᴇǫᴜᴇsᴛ Lɪɴᴋ:\n<code>{req_deep_link}</code>",
            reply_markup=_link_keyboard(normal_link, req_deep_link),
            disable_web_page_preview=True,
        )
        return

    # Freshly added — build both deep-links (live username, never from DB)
    normal_link, req_deep_link = await build_links(client, channel_id)

    await message.reply_text(
        f"✅ Cʜᴀᴛ <b>{ch_name}</b> (<code>{channel_id}</code>) ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ.\n\n"
        f"🔗 Nᴏʀᴍᴀʟ Lɪɴᴋ:\n<code>{normal_link}</code>\n\n"
        f"🔗 Rᴇǫᴜᴇsᴛ Lɪɴᴋ:\n<code>{req_deep_link}</code>\n\n"
        "<i>Share the Normal Link publicly for temp single-use invites.\n"
        "Use the Request Link when you want to approve members manually.</i>",
        reply_markup=_link_keyboard(normal_link, req_deep_link),
        disable_web_page_preview=True,
    )
    logger.info(
        "Channel %s (%s) added by admin %s.", channel_id, ch_name, message.from_user.id
    )


def _link_keyboard(normal_link: str, req_link: str) -> InlineKeyboardMarkup:
    """Inline keyboard with copy buttons for both link types."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Open Normal Link", url=normal_link)],
        [InlineKeyboardButton("📩 Open Request Link", url=req_link)],
    ])


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
        await message.reply_text(
            f"✅ Channel <code>{channel_id}</code> has been removed from the database."
        )
        logger.info("Channel %s removed by admin %s.", channel_id, message.from_user.id)
    else:
        await message.reply_text(
            f"❌ Channel <code>{channel_id}</code> was not found in the database."
        )


# ──────────────────────────────────────────────────────────────────────────────
#  /channels  — paginated button list
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("channels") & filters.private & admin_filter)
async def list_channels(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text(
            "📭 No channels registered yet.\n"
            "Use <code>/addch &lt;channel_id&gt;</code> to add one."
        )
        return
    await _send_channels_page(client, message, channels, page=0)


async def _send_channels_page(client, message_or_query, channels, page: int):
    items = [
        (f"📢 {ch.get('name') or str(ch['_id'])}", f"chinfo:{ch['_id']}")
        for ch in channels
    ]
    rows, cur_page, total_pages = paginate_keyboard(
        items, page, per_page=5, prefix="chpage"
    )

    text = (
        f"📋 <b>Registered Channels</b>  [{cur_page + 1}/{total_pages}]\n\n"
        f"Total: <b>{len(channels)}</b>\n"
        "Tap a channel to view its links."
    )

    if isinstance(message_or_query, Message):
        await message_or_query.reply_text(
            text, reply_markup=InlineKeyboardMarkup(rows)
        )
    else:  # CallbackQuery
        await message_or_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(rows)
        )


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

    ch_doc = await CosmicBotz.get_channel(channel_id)
    name = ch_doc.get("name", str(channel_id)) if ch_doc else str(channel_id)

    # Build links live — bot username never stored
    normal_link, req_deep_link = await build_links(client, channel_id)

    req_mode = ch_doc.get("req_mode", False) if ch_doc else False
    req_timer = ch_doc.get("req_timer", 0) if ch_doc else 0
    req_status = "✅ ON" if req_mode else "❌ OFF"
    timer_str = f"{req_timer}s" if req_timer else "immediate"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Normal Link", url=normal_link),
         InlineKeyboardButton("📩 Request Link", url=req_deep_link)],
        [InlineKeyboardButton(
            f"Auto-Approve: {req_status}",
            callback_data=f"toggle_req:{channel_id}"
        )],
        [InlineKeyboardButton("🗑 Remove Channel", callback_data=f"rmch:{channel_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="chpage:0")],
    ])

    await cq.edit_message_text(
        f"📢 <b>{name}</b>\n"
        f"🆔 <code>{channel_id}</code>\n\n"
        f"🔗 <b>Normal Link:</b>\n<code>{normal_link}</code>\n\n"
        f"📩 <b>Request Link:</b>\n<code>{req_deep_link}</code>\n\n"
        f"🤖 Auto-Approve: <b>{req_status}</b>  |  Timer: <b>{timer_str}</b>",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


@Client.on_callback_query(filters.regex(r"^toggle_req:(-?\d+)$") & admin_filter)
async def toggle_req_callback(client: Client, cq: CallbackQuery):
    channel_id = int(cq.matches[0].group(1))
    current = await CosmicBotz.get_req_mode(channel_id)
    new_state = not current
    await CosmicBotz.set_req_mode(channel_id, new_state)
    state_str = "✅ ON" if new_state else "❌ OFF"
    await cq.answer(f"Auto-Approve is now {state_str}", show_alert=True)
    # Refresh the info panel
    await channel_info_callback(client, cq)


@Client.on_callback_query(filters.regex(r"^rmch:(-?\d+)$") & admin_filter)
async def remove_channel_callback(client: Client, cq: CallbackQuery):
    channel_id = int(cq.matches[0].group(1))
    await CosmicBotz.remove_channel(channel_id)
    await cq.answer(f"Channel {channel_id} removed.", show_alert=True)
    channels = await CosmicBotz.get_all_channels()
    if channels:
        await _send_channels_page(client, cq, channels, page=0)
    else:
        await cq.edit_message_text("📭 No channels registered.")


# ──────────────────────────────────────────────────────────────────────────────
#  /links  — text list of normal deep-links
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("links") & filters.private & admin_filter)
async def list_links(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text("📭 No channels registered.")
        return

    wait = await message.reply_text("⏳ Building links…")
    lines = ["<b>📋 Normal Deep-Links:</b>\n"]
    for ch in channels:
        ch_id = ch["_id"]
        name = ch.get("name") or str(ch_id)
        normal_link, _ = await build_links(client, ch_id)
        lines.append(f"• <b>{name}</b>\n  <code>{normal_link}</code>")

    await wait.delete()
    await _send_chunked(message, "\n\n".join(lines))


# ──────────────────────────────────────────────────────────────────────────────
#  /reqlink  — text list of request deep-links
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("reqlink") & filters.private & admin_filter)
async def req_links(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text("📭 No channels registered.")
        return

    wait = await message.reply_text("⏳ Building request links…")
    lines = ["<b>📋 Request Deep-Links:</b>\n"]
    for ch in channels:
        ch_id = ch["_id"]
        name = ch.get("name") or str(ch_id)
        _, req_deep_link = await build_links(client, ch_id)
        lines.append(f"• <b>{name}</b>\n  <code>{req_deep_link}</code>")

    await wait.delete()
    await _send_chunked(message, "\n\n".join(lines))


# ──────────────────────────────────────────────────────────────────────────────
#  /bulklink <id1> <id2> ...  — show both link types for each
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

    wait = await message.reply_text(
        f"⏳ Generating links for <b>{len(args)}</b> channel(s)…"
    )
    lines = [f"<b>🔗 Bulk Links ({len(args)} channels):</b>\n"]

    for raw_id in args:
        try:
            ch_id = int(raw_id)
        except ValueError:
            lines.append(f"• <code>{raw_id}</code> — ❌ Invalid ID")
            continue

        try:
            chat = await client.get_chat(ch_id)
            name = chat.title or raw_id
        except Exception:
            name = raw_id

        normal_link, req_deep_link = await build_links(client, ch_id)
        lines.append(
            f"• <b>{name}</b>  (<code>{ch_id}</code>)\n"
            f"  🔗 Normal : <code>{normal_link}</code>\n"
            f"  📩 Request: <code>{req_deep_link}</code>"
        )

    await wait.delete()
    await _send_chunked(message, "\n\n".join(lines))


# ──────────────────────────────────────────────────────────────────────────────
#  Internal: chunked message sender (avoids 4096-char limit)
# ──────────────────────────────────────────────────────────────────────────────

async def _send_chunked(message: Message, text: str, chunk_size: int = 3800):
    """Split long text and send as multiple messages."""
    if len(text) <= chunk_size:
        await message.reply_text(text, disable_web_page_preview=True)
        return

    lines = text.split("\n\n")
    buf = []
    for line in lines:
        candidate = "\n\n".join(buf + [line])
        if len(candidate) > chunk_size and buf:
            await message.reply_text(
                "\n\n".join(buf), disable_web_page_preview=True
            )
            buf = [line]
        else:
            buf.append(line)
    if buf:
        await message.reply_text("\n\n".join(buf), disable_web_page_preview=True)
