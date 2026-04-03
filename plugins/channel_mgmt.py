import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified, QueryIdInvalid
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import ADMINS, LOGGER
from database import CosmicBotz
from helper_func import (
    build_links,
    paginate_keyboard,
    safe_delete,
)

logger = LOGGER(__name__)
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

    try:
        channel_id = int(message.command[1])
    except ValueError:
        await message.reply_text(
            "❌ Channel ID must be an integer (e.g. <code>-1001234567890</code>)."
        )
        return

    wait = await message.reply_text("⏳ Validating channel…")

    try:
        chat   = await client.get_chat(channel_id)
        ch_name = chat.title or str(channel_id)
    except Exception:
        await safe_delete(wait)
        await message.reply_text(
            "⚠️ <b>Could not fetch channel info.</b> Make sure:\n"
            "• The bot is an <b>admin</b> in the channel.\n"
            "• The channel ID is correct."
        )
        return

    added = await CosmicBotz.add_channel(channel_id, ch_name)
    if not added:
        await CosmicBotz.update_channel_name(channel_id, ch_name)

    normal_link, req_link = await build_links(client, channel_id)
    await safe_delete(wait)

    status = "✅ Cʜᴀᴛ" if added else "ℹ️ Cʜᴀᴛ (ᴀʟʀᴇᴀᴅʏ ʀᴇɢɪsᴛᴇʀᴇᴅ, ɴᴀᴍᴇ ʀᴇꜰʀᴇsʜᴇᴅ)"
    await message.reply_text(
        f"{status} <b>{ch_name}</b> (<code>{channel_id}</code>) ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ.\n\n"
        f"🔗 Nᴏʀᴍᴀʟ Lɪɴᴋ:\n<code>{normal_link}</code>\n\n"
        f"🔗 Rᴇǫᴜᴇsᴛ Lɪɴᴋ:\n<code>{req_link}</code>\n\n"
        "<i>Share the Normal Link for instant joins.\n"
        "Use the Request Link when you want to approve members manually.</i>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Open Normal Link",  url=normal_link)],
            [InlineKeyboardButton("📩 Open Request Link", url=req_link)],
        ]),
        disable_web_page_preview=True,
    )
    if added:
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
        await message.reply_text(
            f"✅ Channel <code>{channel_id}</code> removed from the database."
        )
        logger.info("Channel %s removed by admin %s.", channel_id, message.from_user.id)
    else:
        await message.reply_text(
            f"❌ Channel <code>{channel_id}</code> not found in the database."
        )


# ──────────────────────────────────────────────────────────────────────────────
#  /channels  — paginated list with per-channel info panel
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


async def _send_channels_page(client, target, channels: list[dict], page: int):
    """
    Render paginated channel list.
    target can be a Message (reply) or CallbackQuery (edit).
    Fixes the name-not-showing bug: we use ch["name"] directly from the DB doc.
    """
    # Build items as (label, callback_data) using the stored name
    items = []
    for ch in channels:
        ch_id   = ch["_id"]
        # ← BUG FIX: was using ch.get("name") or str(ch_id) but the dict key
        #   from Motor always returns the stored string — ensure we always have
        #   a non-empty label here.
        ch_name = (ch.get("name") or "").strip() or f"Channel {ch_id}"
        items.append((f"📢 {ch_name}", f"chinfo:{ch_id}"))

    rows, cur_page, total_pages = paginate_keyboard(
        items, page, per_page=5, prefix="chpage"
    )

    header = (
        f"📋 <b>Registered Channels</b>  [{cur_page + 1}/{total_pages}]\n"
        f"Total: <b>{len(channels)}</b> — tap a channel to manage it."
    )

    kb = InlineKeyboardMarkup(rows)

    if isinstance(target, Message):
        await target.reply_text(header, reply_markup=kb)
    else:
        try:
            await target.edit_message_text(header, reply_markup=kb)
        except (MessageNotModified, QueryIdInvalid):
            pass


@Client.on_callback_query(filters.regex(r"^chpage:(\d+)$") & admin_filter)
async def channels_page_cb(client: Client, cq: CallbackQuery):
    page     = int(cq.matches[0].group(1))
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        try:
            await cq.answer("No channels found.", show_alert=True)
        except QueryIdInvalid:
            pass
        return
    try:
        await cq.answer()
    except QueryIdInvalid:
        pass
    await _send_channels_page(client, cq, channels, page)


@Client.on_callback_query(filters.regex(r"^chinfo:(-?\d+)$") & admin_filter)
async def channel_info_cb(client: Client, cq: CallbackQuery):
    channel_id = int(cq.matches[0].group(1))
    ch_doc     = await CosmicBotz.get_channel(channel_id)

    if not ch_doc:
        try:
            await cq.answer("Channel not found in DB.", show_alert=True)
        except QueryIdInvalid:
            pass
        return

    ch_name    = (ch_doc.get("name") or "").strip() or f"Channel {channel_id}"
    req_mode   = ch_doc.get("req_mode", False)
    req_timer  = ch_doc.get("req_timer", 0)
    req_status = "✅ ON" if req_mode else "❌ OFF"
    timer_str  = f"{req_timer}s delay" if req_timer else "immediate"

    normal_link, req_link = await build_links(client, channel_id)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Normal Link",  url=normal_link),
            InlineKeyboardButton("📩 Request Link", url=req_link),
        ],
        [InlineKeyboardButton(
            f"🤖 Auto-Approve: {req_status}",
            callback_data=f"toggle_req:{channel_id}",
        )],
        [InlineKeyboardButton("🗑 Remove Channel", callback_data=f"rmch:{channel_id}")],
        [InlineKeyboardButton("🔙 Back",           callback_data="chpage:0")],
    ])

    try:
        await cq.edit_message_text(
            f"📢 <b>{ch_name}</b>\n"
            f"🆔 <code>{channel_id}</code>\n\n"
            f"🔗 <b>Normal:</b>\n<code>{normal_link}</code>\n\n"
            f"📩 <b>Request:</b>\n<code>{req_link}</code>\n\n"
            f"🤖 Auto-Approve: <b>{req_status}</b>  |  Timer: <b>{timer_str}</b>",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except (MessageNotModified, QueryIdInvalid):
        pass

    try:
        await cq.answer()
    except QueryIdInvalid:
        pass


@Client.on_callback_query(filters.regex(r"^toggle_req:(-?\d+)$") & admin_filter)
async def toggle_req_cb(client: Client, cq: CallbackQuery):
    channel_id = int(cq.matches[0].group(1))
    current    = await CosmicBotz.get_req_mode(channel_id)
    new_state  = not current
    await CosmicBotz.set_req_mode(channel_id, new_state)
    label = "✅ ON" if new_state else "❌ OFF"
    try:
        await cq.answer(f"Auto-Approve is now {label}", show_alert=True)
    except QueryIdInvalid:
        pass
    # Refresh the info panel
    await channel_info_cb(client, cq)


@Client.on_callback_query(filters.regex(r"^rmch:(-?\d+)$") & admin_filter)
async def remove_channel_cb(client: Client, cq: CallbackQuery):
    channel_id = int(cq.matches[0].group(1))
    await CosmicBotz.remove_channel(channel_id)
    try:
        await cq.answer(f"Channel {channel_id} removed.", show_alert=True)
    except QueryIdInvalid:
        pass

    channels = await CosmicBotz.get_all_channels()
    if channels:
        await _send_channels_page(client, cq, channels, page=0)
    else:
        try:
            await cq.edit_message_text("📭 No channels registered.")
        except (MessageNotModified, QueryIdInvalid):
            pass


# ──────────────────────────────────────────────────────────────────────────────
#  /links  — normal deep-links
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("links") & filters.private & admin_filter)
async def list_links(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text("📭 No channels registered.")
        return

    wait  = await message.reply_text("⏳ Building links…")
    lines = ["<b>📋 Normal Deep-Links:</b>\n"]
    for ch in channels:
        ch_id   = ch["_id"]
        ch_name = (ch.get("name") or "").strip() or f"Channel {ch_id}"
        normal_link, _ = await build_links(client, ch_id)
        lines.append(f"• <b>{ch_name}</b>  (<code>{ch_id}</code>)\n  <code>{normal_link}</code>")

    await safe_delete(wait)
    await _send_chunked(message, "\n\n".join(lines))


# ──────────────────────────────────────────────────────────────────────────────
#  /reqlink  — request deep-links
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("reqlink") & filters.private & admin_filter)
async def req_links(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text("📭 No channels registered.")
        return

    wait  = await message.reply_text("⏳ Building request links…")
    lines = ["<b>📋 Request Deep-Links:</b>\n"]
    for ch in channels:
        ch_id   = ch["_id"]
        ch_name = (ch.get("name") or "").strip() or f"Channel {ch_id}"
        _, req_link = await build_links(client, ch_id)
        lines.append(f"• <b>{ch_name}</b>  (<code>{ch_id}</code>)\n  <code>{req_link}</code>")

    await safe_delete(wait)
    await _send_chunked(message, "\n\n".join(lines))


# ──────────────────────────────────────────────────────────────────────────────
#  /bulklink <id1> <id2>...  — both link types for each channel
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("bulklink") & filters.private & admin_filter)
async def bulk_link(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply_text(
            "❌ <b>Usage:</b> <code>/bulklink &lt;id1&gt; &lt;id2&gt; ...</code>"
        )
        return

    wait  = await message.reply_text(f"⏳ Generating links for <b>{len(args)}</b> channel(s)…")
    lines = [f"<b>🔗 Bulk Links ({len(args)} channels):</b>\n"]

    for raw_id in args:
        try:
            ch_id = int(raw_id)
        except ValueError:
            lines.append(f"• <code>{raw_id}</code> — ❌ Invalid ID")
            continue

        try:
            chat    = await client.get_chat(ch_id)
            ch_name = chat.title or raw_id
        except Exception:
            ch_name = raw_id

        normal_link, req_link = await build_links(client, ch_id)
        lines.append(
            f"• <b>{ch_name}</b>  (<code>{ch_id}</code>)\n"
            f"  🔗 Normal : <code>{normal_link}</code>\n"
            f"  📩 Request: <code>{req_link}</code>"
        )

    await safe_delete(wait)
    await _send_chunked(message, "\n\n".join(lines))


# ──────────────────────────────────────────────────────────────────────────────
#  Internal: split-send long text safely
# ──────────────────────────────────────────────────────────────────────────────

async def _send_chunked(message: Message, text: str, chunk_size: int = 3800):
    if len(text) <= chunk_size:
        await message.reply_text(text, disable_web_page_preview=True)
        return

    lines = text.split("\n\n")
    buf: list[str] = []
    for line in lines:
        candidate = "\n\n".join(buf + [line])
        if len(candidate) > chunk_size and buf:
            await message.reply_text("\n\n".join(buf), disable_web_page_preview=True)
            buf = [line]
        else:
            buf.append(line)
    if buf:
        await message.reply_text("\n\n".join(buf), disable_web_page_preview=True)
