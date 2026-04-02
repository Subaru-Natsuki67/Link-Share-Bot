"""
plugins/admin.py
~~~~~~~~~~~~~~~~
Owner / admin management commands:

  /stats      — DB stats (owner only)
  /status     — Bot uptime & basic info (admins)
  /broadcast  — Send a message to all users (admins)
  /cleanup    — Remove users who blocked the bot (admins)
  /users      — List total user count (admins)
"""
import asyncio
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
#  /stats  (owner only)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("stats") & filters.private & owner_filter)
async def stats_handler(client: Client, message: Message):
    data = await CosmicBotz.stats()
    uptime_str = _format_uptime(client.uptime)

    await message.reply_text(
        "📊 <b>Bot Statistics</b>\n\n"
        f"👤 <b>Total Users:</b> {data['users']}\n"
        f"📢 <b>Registered Channels:</b> {data['channels']}\n"
        f"⏱️ <b>Uptime:</b> {uptime_str}"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /status  (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("status") & filters.private & admin_filter)
async def status_handler(client: Client, message: Message):
    me = await client.get_me()
    uptime_str = _format_uptime(client.uptime)
    data = await CosmicBotz.stats()

    await message.reply_text(
        f"🤖 <b>@{me.username}</b> is <b>online</b>!\n\n"
        f"⏱️ <b>Uptime:</b> {uptime_str}\n"
        f"👤 <b>Users:</b> {data['users']}\n"
        f"📢 <b>Channels:</b> {data['channels']}"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /users  (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("users") & filters.private & admin_filter)
async def users_handler(client: Client, message: Message):
    count = await CosmicBotz.total_users()
    await message.reply_text(f"👤 <b>Total Users:</b> <code>{count}</code>")


# ──────────────────────────────────────────────────────────────────────────────
#  /broadcast  (admins) — reply to a message to broadcast it
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("broadcast") & filters.private & admin_filter)
async def broadcast_handler(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text(
            "❌ Reply to the message you want to broadcast.\n\n"
            "Example:\n<i>[reply to a message]</i> <code>/broadcast</code>"
        )
        return

    to_broadcast = message.reply_to_message
    user_ids = await CosmicBotz.get_all_users()
    total = len(user_ids)

    status_msg = await message.reply_text(
        f"📡 <b>Broadcasting to {total} users…</b>\n"
        "This may take a while."
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

        # Live progress every 50 users
        if (sent + blocked + failed) % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"📡 <b>Broadcast Progress:</b>\n"
                    f"✅ Sent: {sent} | ❌ Failed: {failed} | 🚫 Blocked: {blocked}"
                )
            except Exception:
                pass

    elapsed = (datetime.now() - start).seconds
    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"📤 Sent: <b>{sent}</b>\n"
        f"🚫 Blocked/Deactivated: <b>{blocked}</b>\n"
        f"❌ Failed: <b>{failed}</b>\n"
        f"⏱️ Time: <b>{elapsed}s</b>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /cleanup  — remove blocked/inactive users (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("cleanup") & filters.private & admin_filter)
async def cleanup_handler(client: Client, message: Message):
    user_ids = await CosmicBotz.get_all_users()
    status_msg = await message.reply_text(
        f"🧹 <b>Checking {len(user_ids)} users for blocks / deactivations…</b>"
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
        f"✅ <b>Cleanup Done!</b>\n"
        f"🗑 Removed <b>{removed}</b> inactive/blocked user(s).\n"
        f"👤 Remaining: <b>{await CosmicBotz.total_users()}</b>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Helper
# ──────────────────────────────────────────────────────────────────────────────

def _format_uptime(start: datetime) -> str:
    delta = datetime.now() - start
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    d, h = divmod(h, 24)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m {s}s")
    return " ".join(parts)
