"""
plugins/req_mode.py
~~~~~~~~~~~~~~~~~~~
Commands for join-request auto-approval.

  /reqmode  <channel_id>              — Toggle auto-approval ON/OFF (one channel)
  /reqtime  [<channel_id>] <seconds>  — Set timer for one channel OR all channels
                                        If channel_id is omitted → applies to ALL
  /approveon                          — Enable auto-approve for ALL channels
  /approveoff                         — Disable auto-approve for ALL channels

Also handles ChatJoinRequest to auto-approve when mode is ON.
"""
import asyncio

from pyrogram import Client, filters
from pyrogram.types import ChatJoinRequest, Message

from config import ADMINS, LOGGER
from database import CosmicBotz

logger = LOGGER(__name__)
admin_filter = filters.user(ADMINS)


# ──────────────────────────────────────────────────────────────────────────────
#  /reqmode <channel_id>
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("reqmode") & filters.private & admin_filter)
async def req_mode_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text(
            "<b>ᴜsᴀɢᴇ:</b> <code>/reqmode &lt;channel_id&gt;</code>\n\n"
            "<blockquote>ᴛᴏɢɢʟᴇs ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴀʟ ᴏꜰ ᴊᴏɪɴ ʀᴇǫᴜᴇsᴛs ᴏɴ/ᴏꜰꜰ.\n"
            "ᴛᴏ ᴛᴏɢɢʟᴇ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴀᴛ ᴏɴᴄᴇ ᴜsᴇ /approveon ᴏʀ /approveoff.</blockquote>"
        )
        return

    try:
        ch_id = int(message.command[1])
    except ValueError:
        await message.reply_text(
            "<blockquote>❌ ᴄʜᴀɴɴᴇʟ ɪᴅ ᴍᴜsᴛ ʙᴇ ᴀɴ ɪɴᴛᴇɢᴇʀ.</blockquote>"
        )
        return

    if not await CosmicBotz.is_channel_exist(ch_id):
        await message.reply_text(
            "<blockquote>❌ ᴄʜᴀɴɴᴇʟ ɴᴏᴛ ʀᴇɢɪsᴛᴇʀᴇᴅ. ᴜsᴇ /addch ꜰɪʀsᴛ.</blockquote>"
        )
        return

    current   = await CosmicBotz.get_req_mode(ch_id)
    new_state = not current
    await CosmicBotz.set_req_mode(ch_id, new_state)

    state_str = "✅ <b>ᴏɴ</b>" if new_state else "❌ <b>ᴏꜰꜰ</b>"
    await message.reply_text(
        f"<blockquote>🤖 ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴀʟ ꜰᴏʀ <code>{ch_id}</code> ɪs ɴᴏᴡ {state_str}.</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /reqtime  [<channel_id>] <seconds>
#  One arg  → apply to ALL channels (global default)
#  Two args → apply to one specific channel
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("reqtime") & filters.private & admin_filter)
async def req_time_cmd(client: Client, message: Message):
    args = message.command[1:]   # strip "/reqtime"

    if not args:
        global_timer = await CosmicBotz.get_global_req_timer()
        await message.reply_text(
            "<b>ᴜsᴀɢᴇ:</b>\n\n"
            "<blockquote>"
            "<code>/reqtime &lt;seconds&gt;</code>  — sᴇᴛ ꜰᴏʀ <b>ᴀʟʟ</b> ᴄʜᴀɴɴᴇʟs\n"
            "<code>/reqtime &lt;channel_id&gt; &lt;seconds&gt;</code>  — sᴇᴛ ꜰᴏʀ ᴏɴᴇ ᴄʜᴀɴɴᴇʟ\n\n"
            f"ᴄᴜʀʀᴇɴᴛ ɢʟᴏʙᴀʟ ᴅᴇꜰᴀᴜʟᴛ: <b>{global_timer}s</b> "
            f"({'ɪᴍᴍᴇᴅɪᴀᴛᴇ' if global_timer == 0 else f'{global_timer}s ᴅᴇʟᴀʏ'})"
            "</blockquote>"
        )
        return

    # ── One argument: /reqtime <seconds> → global ─────────────────────────────
    if len(args) == 1:
        try:
            seconds = int(args[0])
            if seconds < 0:
                raise ValueError
        except ValueError:
            await message.reply_text(
                "<blockquote>❌ sᴇᴄᴏɴᴅs ᴍᴜsᴛ ʙᴇ ᴀ ɴᴏɴ-ɴᴇɢᴀᴛɪᴠᴇ ɪɴᴛᴇɢᴇʀ.</blockquote>"
            )
            return

        channels = await CosmicBotz.get_all_channels()
        await CosmicBotz.set_global_req_timer(seconds)

        delay_str = "ɪᴍᴍᴇᴅɪᴀᴛᴇʟʏ" if seconds == 0 else f"ᴀꜰᴛᴇʀ <b>{seconds}s</b>"
        await message.reply_text(
            f"<b>✅ ɢʟᴏʙᴀʟ ᴛɪᴍᴇʀ ᴜᴘᴅᴀᴛᴇᴅ.</b>\n\n"
            f"<blockquote>"
            f"❍ ᴀʟʟ <b>{len(channels)}</b> ᴄʜᴀɴɴᴇʟs ɴᴏᴡ ᴀᴘᴘʀᴏᴠᴇ ʀᴇǫᴜᴇsᴛs {delay_str}.\n"
            f"❍ ɴᴇᴡ ᴄʜᴀɴɴᴇʟs ᴀᴅᴅᴇᴅ ʟᴀᴛᴇʀ ᴡɪʟʟ ᴀʟsᴏ ɪɴʜᴇʀɪᴛ ᴛʜɪs ᴅᴇꜰᴀᴜʟᴛ."
            f"</blockquote>"
        )
        logger.info("Global req_timer set to %ss by admin %s.", seconds, message.from_user.id)
        return

    # ── Two arguments: /reqtime <channel_id> <seconds> → one channel ──────────
    if len(args) == 2:
        try:
            ch_id   = int(args[0])
            seconds = int(args[1])
            if seconds < 0:
                raise ValueError
        except ValueError:
            await message.reply_text(
                "<blockquote>❌ ᴄʜᴀɴɴᴇʟ ɪᴅ ᴀɴᴅ sᴇᴄᴏɴᴅs ᴍᴜsᴛ ʙᴇ ɴᴏɴ-ɴᴇɢᴀᴛɪᴠᴇ ɪɴᴛᴇɢᴇʀs.</blockquote>"
            )
            return

        if not await CosmicBotz.is_channel_exist(ch_id):
            await message.reply_text(
                "<blockquote>❌ ᴄʜᴀɴɴᴇʟ ɴᴏᴛ ʀᴇɢɪsᴛᴇʀᴇᴅ.</blockquote>"
            )
            return

        await CosmicBotz.set_req_timer(ch_id, seconds)
        delay_str = "ɪᴍᴍᴇᴅɪᴀᴛᴇʟʏ" if seconds == 0 else f"ᴀꜰᴛᴇʀ <b>{seconds}s</b>"
        await message.reply_text(
            f"<blockquote>✅ ᴄʜᴀɴɴᴇʟ <code>{ch_id}</code>: ʀᴇǫᴜᴇsᴛs ᴀᴘᴘʀᴏᴠᴇᴅ {delay_str}.</blockquote>"
        )
        return

    # Too many args
    await message.reply_text(
        "<blockquote>❌ ᴛᴏᴏ ᴍᴀɴʏ ᴀʀɢᴜᴍᴇɴᴛs.\n"
        "ᴜsᴇ <code>/reqtime &lt;seconds&gt;</code> ᴏʀ "
        "<code>/reqtime &lt;channel_id&gt; &lt;seconds&gt;</code></blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /approveon  — GLOBAL enable
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("approveon") & filters.private & admin_filter)
async def approve_on(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text(
            "<blockquote>📭 ɴᴏ ᴄʜᴀɴɴᴇʟs ʀᴇɢɪsᴛᴇʀᴇᴅ ʏᴇᴛ.</blockquote>"
        )
        return

    for ch in channels:
        await CosmicBotz.set_req_mode(ch["_id"], True)

    await message.reply_text(
        f"<blockquote>✅ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴀʟ <b>ᴇɴᴀʙʟᴇᴅ</b> ꜰᴏʀ ᴀʟʟ <b>{len(channels)}</b> ᴄʜᴀɴɴᴇʟ(s).</blockquote>"
    )
    logger.info("Global approveon by admin %s.", message.from_user.id)


# ──────────────────────────────────────────────────────────────────────────────
#  /approveoff  — GLOBAL disable
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("approveoff") & filters.private & admin_filter)
async def approve_off(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text(
            "<blockquote>📭 ɴᴏ ᴄʜᴀɴɴᴇʟs ʀᴇɢɪsᴛᴇʀᴇᴅ ʏᴇᴛ.</blockquote>"
        )
        return

    for ch in channels:
        await CosmicBotz.set_req_mode(ch["_id"], False)

    await message.reply_text(
        f"<blockquote>❌ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴀʟ <b>ᴅɪsᴀʙʟᴇᴅ</b> ꜰᴏʀ ᴀʟʟ <b>{len(channels)}</b> ᴄʜᴀɴɴᴇʟ(s).</blockquote>"
    )
    logger.info("Global approveoff by admin %s.", message.from_user.id)


# ──────────────────────────────────────────────────────────────────────────────
#  ChatJoinRequest — auto-approve if mode is ON for that channel
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
        logger.warning("Auto-approve failed: user %s in %s: %s", user_id, ch_id, e)
