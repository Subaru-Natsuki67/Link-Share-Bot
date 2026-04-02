"""
plugins/req_mode.py
~~~~~~~~~~~~~~~~~~~
Commands for managing join-request auto-approval:

  /reqmode  — Toggle auto-approval mode ON/OFF for a channel
  /reqtime  — Set auto-approve timer (seconds)
  /approveon  <channel_id>  — Enable per-channel
  /approveoff <channel_id>  — Disable per-channel

Also handles the ChatJoinRequest update to auto-approve when mode is ON.
"""
import asyncio

from pyrogram import Client, filters
from pyrogram.types import (
    ChatJoinRequest,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import ADMINS, LOGGER
from database import CosmicBotz

logger = LOGGER(__name__)
admin_filter = filters.user(ADMINS)


# ──────────────────────────────────────────────────────────────────────────────
#  /reqmode  — toggle for a specific channel
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("reqmode") & filters.private & admin_filter)
async def req_mode_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text(
            "❌ <b>Usage:</b> <code>/reqmode &lt;channel_id&gt;</code>\n\n"
            "Toggles auto-approval of join requests ON/OFF for the channel."
        )
        return

    try:
        ch_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Channel ID must be an integer.")
        return

    if not await CosmicBotz.is_channel_exist(ch_id):
        await message.reply_text("❌ Channel not registered. Use <code>/addch</code> first.")
        return

    current = await CosmicBotz.get_req_mode(ch_id)
    new_state = not current
    await CosmicBotz.set_req_mode(ch_id, new_state)

    state_str = "✅ <b>ON</b>" if new_state else "❌ <b>OFF</b>"
    await message.reply_text(
        f"Auto-approval for channel <code>{ch_id}</code> is now {state_str}."
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /reqtime  — set auto-approve delay
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("reqtime") & filters.private & admin_filter)
async def req_time_cmd(client: Client, message: Message):
    if len(message.command) < 3:
        await message.reply_text(
            "❌ <b>Usage:</b> <code>/reqtime &lt;channel_id&gt; &lt;seconds&gt;</code>\n\n"
            "Set to <code>0</code> to approve immediately.\n"
            "Example: <code>/reqtime -1001234567890 30</code>"
        )
        return

    try:
        ch_id = int(message.command[1])
        seconds = int(message.command[2])
        if seconds < 0:
            raise ValueError
    except ValueError:
        await message.reply_text("❌ Channel ID and seconds must be non-negative integers.")
        return

    if not await CosmicBotz.is_channel_exist(ch_id):
        await message.reply_text("❌ Channel not registered.")
        return

    await CosmicBotz.set_req_timer(ch_id, seconds)
    if seconds == 0:
        await message.reply_text(
            f"✅ Channel <code>{ch_id}</code>: join requests will be approved <b>immediately</b>."
        )
    else:
        await message.reply_text(
            f"✅ Channel <code>{ch_id}</code>: join requests will be approved after <b>{seconds}s</b>."
        )


# ──────────────────────────────────────────────────────────────────────────────
#  /approveon  /approveoff
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("approveon") & filters.private & admin_filter)
async def approve_on(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ <b>Usage:</b> <code>/approveon &lt;channel_id&gt;</code>")
        return
    try:
        ch_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Channel ID must be an integer.")
        return

    if not await CosmicBotz.is_channel_exist(ch_id):
        await message.reply_text("❌ Channel not registered.")
        return

    await CosmicBotz.set_req_mode(ch_id, True)
    await message.reply_text(
        f"✅ Auto-approval <b>enabled</b> for channel <code>{ch_id}</code>."
    )


@Client.on_message(filters.command("approveoff") & filters.private & admin_filter)
async def approve_off(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ <b>Usage:</b> <code>/approveoff &lt;channel_id&gt;</code>")
        return
    try:
        ch_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Channel ID must be an integer.")
        return

    if not await CosmicBotz.is_channel_exist(ch_id):
        await message.reply_text("❌ Channel not registered.")
        return

    await CosmicBotz.set_req_mode(ch_id, False)
    await message.reply_text(
        f"❌ Auto-approval <b>disabled</b> for channel <code>{ch_id}</code>."
    )


# ──────────────────────────────────────────────────────────────────────────────
#  ChatJoinRequest handler — auto-approve if mode is ON
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_chat_join_request()
async def handle_join_request(client: Client, request: ChatJoinRequest):
    ch_id = request.chat.id
    user_id = request.from_user.id

    if not await CosmicBotz.is_channel_exist(ch_id):
        return  # Not a managed channel

    req_mode = await CosmicBotz.get_req_mode(ch_id)
    if not req_mode:
        return  # Auto-approve is OFF

    delay = await CosmicBotz.get_req_timer(ch_id)
    if delay > 0:
        await asyncio.sleep(delay)

    try:
        await client.approve_chat_join_request(ch_id, user_id)
        logger.info("Auto-approved join request: user %s in channel %s.", user_id, ch_id)
    except Exception as e:
        logger.warning("Failed to approve join request for user %s in %s: %s", user_id, ch_id, e)
