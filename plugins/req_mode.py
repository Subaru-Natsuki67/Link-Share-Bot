"""
plugins/req_mode.py
~~~~~~~~~~~~~~~~~~~
Join-request auto-approval management.

  /reqmode <channel_id>   — Toggle auto-approve ON/OFF for a specific channel
  /reqtime <ch_id> <sec>  — Set auto-approve timer for a specific channel

  /approveon              — Enable  auto-approve GLOBALLY (all managed channels)
  /approveoff             — Disable auto-approve GLOBALLY (all managed channels)

  ChatJoinRequest handler — fires for every incoming join request
"""
import asyncio

from pyrogram import Client, filters
from pyrogram.types import ChatJoinRequest, Message

from config import ADMINS, LOGGER
from database import CosmicBotz

logger = LOGGER(__name__)
admin_filter = filters.user(ADMINS)


# ──────────────────────────────────────────────────────────────────────────────
#  /reqmode <channel_id>  — per-channel toggle
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("reqmode") & filters.private & admin_filter)
async def req_mode_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text(
            "<b>ᴜsᴀɢᴇ:</b> <code>/reqmode &lt;channel_id&gt;</code>\n\n"
            "<blockquote>ᴛᴏɢɢʟᴇs ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴀʟ ᴏꜰ ᴊᴏɪɴ ʀᴇǫᴜᴇsᴛs ᴏɴ/ᴏꜰꜰ ꜰᴏʀ ᴏɴᴇ ᴄʜᴀɴɴᴇʟ.\n"
            "ᴛᴏ ᴛᴏɢɢʟᴇ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴀᴛ ᴏɴᴄᴇ ᴜsᴇ /approveon ᴏʀ /approveoff.</blockquote>"
        )
        return

    try:
        ch_id = int(message.command[1])
    except ValueError:
        await message.reply_text(
            "<blockquote>❌ Channel ID must be an integer.</blockquote>"
        )
        return

    if not await CosmicBotz.is_channel_exist(ch_id):
        await message.reply_text(
            "<blockquote>❌ Channel not registered. Use <code>/addch</code> first.</blockquote>"
        )
        return

    current   = await CosmicBotz.get_req_mode(ch_id)
    new_state = not current
    await CosmicBotz.set_req_mode(ch_id, new_state)

    state_str = "✅ <b>ON</b>" if new_state else "❌ <b>OFF</b>"
    await message.reply_text(
        f"<blockquote>🤖 Auto-approval for channel <code>{ch_id}</code> is now {state_str}.</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /reqtime <channel_id> <seconds>  — per-channel timer
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("reqtime") & filters.private & admin_filter)
async def req_time_cmd(client: Client, message: Message):
    if len(message.command) < 3:
        await message.reply_text(
            "<b>ᴜsᴀɢᴇ:</b> <code>/reqtime &lt;channel_id&gt; &lt;seconds&gt;</code>\n\n"
            "<blockquote>sᴇᴛ ᴛᴏ <code>0</code> ᴛᴏ ᴀᴘᴘʀᴏᴠᴇ ɪᴍᴍᴇᴅɪᴀᴛᴇʟʏ.\n"
            "ᴇxᴀᴍᴘʟᴇ: <code>/reqtime -1001234567890 30</code></blockquote>"
        )
        return

    try:
        ch_id   = int(message.command[1])
        seconds = int(message.command[2])
        if seconds < 0:
            raise ValueError
    except ValueError:
        await message.reply_text(
            "<blockquote>❌ Channel ID and seconds must be non-negative integers.</blockquote>"
        )
        return

    if not await CosmicBotz.is_channel_exist(ch_id):
        await message.reply_text(
            "<blockquote>❌ Channel not registered.</blockquote>"
        )
        return

    await CosmicBotz.set_req_timer(ch_id, seconds)

    if seconds == 0:
        await message.reply_text(
            f"<blockquote>✅ Channel <code>{ch_id}</code>: join requests approved <b>immediately</b>.</blockquote>"
        )
    else:
        await message.reply_text(
            f"<blockquote>✅ Channel <code>{ch_id}</code>: join requests approved after <b>{seconds}s</b>.</blockquote>"
        )


# ──────────────────────────────────────────────────────────────────────────────
#  /approveon  — GLOBAL enable (no channel_id needed)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("approveon") & filters.private & admin_filter)
async def approve_on(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text(
            "<blockquote>📭 No channels registered yet. Use <code>/addch</code> first.</blockquote>"
        )
        return

    count = 0
    for ch in channels:
        await CosmicBotz.set_req_mode(ch["_id"], True)
        count += 1

    await message.reply_text(
        f"<blockquote>✅ Auto-approval <b>enabled</b> for all <b>{count}</b> registered channel(s).</blockquote>"
    )
    logger.info("Global approveon by admin %s — %d channels.", message.from_user.id, count)


# ──────────────────────────────────────────────────────────────────────────────
#  /approveoff  — GLOBAL disable (no channel_id needed)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("approveoff") & filters.private & admin_filter)
async def approve_off(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text(
            "<blockquote>📭 No channels registered yet.</blockquote>"
        )
        return

    count = 0
    for ch in channels:
        await CosmicBotz.set_req_mode(ch["_id"], False)
        count += 1

    await message.reply_text(
        f"<blockquote>❌ Auto-approval <b>disabled</b> for all <b>{count}</b> registered channel(s).</blockquote>"
    )
    logger.info("Global approveoff by admin %s — %d channels.", message.from_user.id, count)


# ──────────────────────────────────────────────────────────────────────────────
#  ChatJoinRequest handler — auto-approve when mode is ON for that channel
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_chat_join_request()
async def handle_join_request(client: Client, request: ChatJoinRequest):
    ch_id   = request.chat.id
    user_id = request.from_user.id

    if not await CosmicBotz.is_channel_exist(ch_id):
        return

    if not await CosmicBotz.get_req_mode(ch_id):
        return

    delay = await CosmicBotz.get_req_timer(ch_id)
    if delay > 0:
        await asyncio.sleep(delay)

    try:
        await client.approve_chat_join_request(ch_id, user_id)
        logger.info("Auto-approved: user %s → channel %s.", user_id, ch_id)
    except Exception as e:
        logger.warning("Failed auto-approve user %s in %s: %s", user_id, ch_id, e)