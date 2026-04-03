import asyncio
import os
import random
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked
from pyrogram.types import Message

from config import ADMINS, LOGGER, OWNER_ID
from database import CosmicBotz

logger = LOGGER(__name__)

admin_filter = filters.user(ADMINS)
owner_filter = filters.user([OWNER_ID])

# ──────────────────────────────────────────────────────────────────────────────
#  Roasts for non-admins trying admin commands
# ──────────────────────────────────────────────────────────────────────────────

_ROASTS = [
    "ʙʀᴏ ʀᴇᴀʟʟʏ ᴛʜᴏᴜɢʜᴛ ʜᴇ ᴡᴀs ᴀɴ ᴀᴅᴍɪɴ. 💀",
    "ᴛʜᴇ ᴀᴜᴅᴀᴄɪᴛʏ. ɢᴇɴᴜɪɴᴇʟʏ ɪᴍᴘʀᴇssɪᴠᴇ.",
    "ʙᴏʟᴅ ᴍᴏᴠᴇ. ᴜɴꜰᴏʀᴛᴜɴᴀᴛᴇʟʏ, ɴᴏ.",
    "sɪʀ ᴛʜɪs ɪs ᴀ ᴛᴇʟᴇɢʀᴀᴍ ʙᴏᴛ, ɴᴏᴛ ᴀ ᴅᴇᴍᴏᴄʀᴀᴄʏ.",
    "ɴɪᴄᴇ ᴛʀʏ. ᴀᴅᴍɪɴ ᴘʀɪᴠɪʟᴇɢᴇs ɴᴏᴛ ɪɴᴄʟᴜᴅᴇᴅ ᴡɪᴛʜ ʏᴏᴜʀ ꜰʀᴇᴇ ᴀᴄᴄᴏᴜɴᴛ.",
    "ʏᴏᴜ'ʀᴇ ʟɪᴋᴇ 6 ᴘᴇʀᴍɪssɪᴏɴ ʟᴇᴠᴇʟs sʜᴏʀᴛ ᴏꜰ ᴜsɪɴɢ ᴛʜᴀᴛ ᴄᴏᴍᴍᴀɴᴅ.",
    "ɪ'ᴅ sᴀʏ ᴛʀʏ ᴀɢᴀɪɴ, ʙᴜᴛ ɪᴛ ᴡᴏɴ'ᴛ ʜᴇʟᴘ.",
    "ɴᴏᴛ ʏᴏᴜ. ɴᴇᴠᴇʀ ʏᴏᴜ.",
    "ᴛʜᴀᴛ ᴄᴏᴍᴍᴀɴᴅ ɪs ᴀʙᴏᴠᴇ ʏᴏᴜʀ ᴘᴀʏ ɢʀᴀᴅᴇ. ᴀᴄᴛᴜᴀʟʟʏ, ᴀɴʏ ᴘᴀʏ ɢʀᴀᴅᴇ.",
    "ɪᴍᴀɢɪɴᴇ ʜᴀᴠɪɴɢ ᴀᴅᴍɪɴ ᴀᴄᴄᴇss. ᴍᴜsᴛ ʙᴇ ɴɪᴄᴇ.",
    "ᴛʜᴇ ᴀɴsᴡᴇʀ ɪs ɴᴏ. ᴛʜᴇ ᴀɴsᴡᴇʀ ᴡɪʟʟ ᴀʟᴡᴀʏs ʙᴇ ɴᴏ.",
    "ᴇʀʀᴏʀ 403: ʏᴏᴜ'ʀᴇ ɴᴏᴛ ᴛʜᴀᴛ ɢᴜʏ.",
    "ᴡʜᴏ ᴛᴏʟᴅ ʏᴏᴜ ᴛʜᴀᴛ ᴡᴏᴜʟᴅ ᴡᴏʀᴋ? ꜰɪʀᴇ ᴛʜᴇᴍ.",
    "ɪ'ᴠᴇ sᴇᴇɴ ʙᴏᴛs ᴡɪᴛʜ ᴍᴏʀᴇ ᴀᴅᴍɪɴ ʀɪɢʜᴛs ᴛʜᴀɴ ʏᴏᴜ.",
    "ᴏɴᴇ ᴅᴀʏ ʏᴏᴜ'ʟʟ ꜰɪɴᴅ ᴀ ᴄᴏᴍᴍᴀɴᴅ ʏᴏᴜ ᴄᴀɴ ᴜsᴇ. ᴛᴏᴅᴀʏ ɪs ɴᴏᴛ ᴛʜᴀᴛ ᴅᴀʏ.",
    "ᴀʜ ʏᴇs, ᴛʜᴇ ᴄʟᴀssɪᴄ 'ʟᴇᴛ ᴍᴇ ᴊᴜsᴛ ᴛʀʏ ᴀɴᴅ sᴇᴇ' ᴍᴏᴠᴇ.",
    "ʏᴏᴜʀ ᴘᴇʀᴍɪssɪᴏɴ ʟᴇᴠᴇʟ: 🚫  ʀᴇǫᴜɪʀᴇᴅ ᴘᴇʀᴍɪssɪᴏɴ ʟᴇᴠᴇʟ: ᴀᴅᴍɪɴ.",
]

def _roast() -> str:
    return random.choice(_ROASTS)

# Handler that fires BEFORE admin commands for non-admins — catches all
# admin-only commands and returns a roast instead of silently ignoring.
_ADMIN_CMDS = ["stats", "status", "users", "broadcast", "cleanup", "logs",
               "addch", "delch", "channels", "links", "reqlink", "bulklink",
               "reqmode", "reqtime", "approveon", "approveoff"]

@Client.on_message(
    filters.command(_ADMIN_CMDS) & filters.private & ~filters.user(ADMINS),
    group=-1,   # lower group number = higher priority in Pyrogram
)
async def roast_non_admin(client: Client, message: Message):
    await message.reply_text(f"<blockquote>{_roast()}</blockquote>")
    message.stop_propagation()


# ──────────────────────────────────────────────────────────────────────────────
#  /stats  (owner only)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("stats") & filters.private & owner_filter)
async def stats_handler(client: Client, message: Message):
    data      = await CosmicBotz.stats()
    uptime_str = _format_uptime(client.uptime)
    await message.reply_text(
        "<b>📊 ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs</b>\n\n"
        "<blockquote>"
        f"❍ ᴜsᴇʀs    : <b>{data['users']}</b>\n"
        f"❍ ᴄʜᴀɴɴᴇʟs : <b>{data['channels']}</b>\n"
        f"❍ ᴜᴘᴛɪᴍᴇ   : <b>{uptime_str}</b>"
        "</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /status  (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("status") & filters.private & admin_filter)
async def status_handler(client: Client, message: Message):
    me        = await client.get_me()
    uptime_str = _format_uptime(client.uptime)
    data      = await CosmicBotz.stats()
    await message.reply_text(
        f"🤖 <b>@{me.username}</b> ɪs <b>ᴏɴʟɪɴᴇ</b>!\n\n"
        "<blockquote>"
        f"❍ ᴜᴘᴛɪᴍᴇ   : <b>{uptime_str}</b>\n"
        f"❍ ᴜsᴇʀs    : <b>{data['users']}</b>\n"
        f"❍ ᴄʜᴀɴɴᴇʟs : <b>{data['channels']}</b>"
        "</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /users  (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("users") & filters.private & admin_filter)
async def users_handler(client: Client, message: Message):
    count = await CosmicBotz.total_users()
    await message.reply_text(
        f"<blockquote>👤 ᴛᴏᴛᴀʟ ᴜsᴇʀs: <b>{count}</b></blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /broadcast  (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("broadcast") & filters.private & admin_filter)
async def broadcast_handler(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text(
            "<blockquote>❌ ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴍᴇssᴀɢᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ, ᴛʜᴇɴ sᴇɴᴅ /broadcast.</blockquote>"
        )
        return

    to_broadcast = message.reply_to_message
    user_ids     = await CosmicBotz.get_all_users()
    total        = len(user_ids)

    status_msg = await message.reply_text(
        f"<blockquote>📡 ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ᴛᴏ <b>{total}</b> ᴜsᴇʀs…</blockquote>"
    )

    sent = blocked = failed = 0
    start = datetime.now()

    for uid in user_ids:
        try:
            await to_broadcast.copy(uid)
            sent += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await to_broadcast.copy(uid)
                sent += 1
            except Exception:
                failed += 1
        except (UserIsBlocked, InputUserDeactivated):
            blocked += 1
        except Exception:
            failed += 1

        if (sent + blocked + failed) % 50 == 0:
            try:
                await status_msg.edit_text(
                    "<blockquote>"
                    f"📡 ᴘʀᴏɢʀᴇss:\n"
                    f"✅ sᴇɴᴛ: <b>{sent}</b>  ❌ ꜰᴀɪʟᴇᴅ: <b>{failed}</b>  🚫 ʙʟᴏᴄᴋᴇᴅ: <b>{blocked}</b>"
                    "</blockquote>"
                )
            except Exception:
                pass

    elapsed = (datetime.now() - start).seconds
    await status_msg.edit_text(
        "<b>✅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇ!</b>\n\n"
        "<blockquote>"
        f"❍ sᴇɴᴛ    : <b>{sent}</b>\n"
        f"❍ ʙʟᴏᴄᴋᴇᴅ : <b>{blocked}</b>\n"
        f"❍ ꜰᴀɪʟᴇᴅ  : <b>{failed}</b>\n"
        f"❍ ᴛɪᴍᴇ    : <b>{elapsed}s</b>"
        "</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /cleanup  (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("cleanup") & filters.private & admin_filter)
async def cleanup_handler(client: Client, message: Message):
    user_ids   = await CosmicBotz.get_all_users()
    status_msg = await message.reply_text(
        f"<blockquote>🧹 ᴄʜᴇᴄᴋɪɴɢ <b>{len(user_ids)}</b> ᴜsᴇʀs ꜰᴏʀ ʙʟᴏᴄᴋs / ᴅᴇᴀᴄᴛɪᴠᴀᴛɪᴏɴs…</blockquote>"
    )
    removed = 0
    for uid in user_ids:
        try:
            await client.send_chat_action(uid, "typing")
        except (UserIsBlocked, InputUserDeactivated):
            await CosmicBotz.remove_user(uid)
            removed += 1
        except Exception:
            pass

    await status_msg.edit_text(
        "<b>✅ ᴄʟᴇᴀɴᴜᴘ ᴅᴏɴᴇ!</b>\n\n"
        "<blockquote>"
        f"❍ ʀᴇᴍᴏᴠᴇᴅ   : <b>{removed}</b>\n"
        f"❍ ʀᴇᴍᴀɪɴɪɴɢ : <b>{await CosmicBotz.total_users()}</b>"
        "</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /logs  (owner only) — send bot.log as a document
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("logs") & filters.private & owner_filter)
async def logs_handler(client: Client, message: Message):
    log_file = "bot.log"
    if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
        await message.reply_text(
            "<blockquote>📭 ʟᴏɢ ꜰɪʟᴇ ɪs ᴇᴍᴘᴛʏ ᴏʀ ᴅᴏᴇs ɴᴏᴛ ᴇxɪsᴛ.</blockquote>"
        )
        return
    await message.reply_document(
        document=log_file,
        caption="<blockquote>📜 ʜᴇʀᴇ ɪs ᴛʜᴇ ʟᴀᴛᴇsᴛ ʙᴏᴛ ʟᴏɢ.</blockquote>",
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Internal helper
# ──────────────────────────────────────────────────────────────────────────────

def _format_uptime(start: datetime) -> str:
    delta = datetime.now() - start
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    d, h   = divmod(h, 24)
    parts  = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    parts.append(f"{m}m {s}s")
    return " ".join(parts)
