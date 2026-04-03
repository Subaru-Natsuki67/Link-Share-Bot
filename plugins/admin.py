import asyncio
import os
import random
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked
from pyrogram.types import Message

from config import ADMINS, LOG_FILE_NAME, LOGGER, OWNER_ID
from database import CosmicBotz

logger = LOGGER(__name__)

admin_filter = filters.user(ADMINS)
owner_filter = filters.user([OWNER_ID])

# ── Roast lines — small caps ──────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────────────────────
#  Non-admin intercept
# ──────────────────────────────────────────────────────────────────────────────

_ADMIN_COMMANDS = [
    "stats", "status", "broadcast", "cleanup", "users", "logs",
    "addch", "delch", "channels", "links", "reqlink", "bulklink",
    "reqmode", "reqtime", "approveon", "approveoff",
]

@Client.on_message(
    filters.command(_ADMIN_COMMANDS) & filters.private & ~filters.user(ADMINS)
)
async def roast_non_admin(client: Client, message: Message):
    await message.reply_text(_roast())


# ──────────────────────────────────────────────────────────────────────────────
#  /stats  (owner only)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("stats") & filters.private & owner_filter)
async def stats_handler(client: Client, message: Message):
    data       = await CosmicBotz.stats()
    uptime_str = _fmt_uptime(client.uptime)
    me         = await client.get_me()
    await message.reply_text(
        f"<b>❍ @{me.username} — sᴛᴀᴛɪsᴛɪᴄs</b>\n\n"
        f"<blockquote>"
        f"❍ ᴜsᴇʀs      :  {data['users']}\n"
        f"❍ ᴄʜᴀɴɴᴇʟs  :  {data['channels']}\n"
        f"❍ ᴜᴘᴛɪᴍᴇ    :  {uptime_str}"
        f"</blockquote>\n\n"
        f"<i><a href='https://t.me/CosmicBotz'>@CosmicBotz</a></i>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /status  (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("status") & filters.private & admin_filter)
async def status_handler(client: Client, message: Message):
    me         = await client.get_me()
    uptime_str = _fmt_uptime(client.uptime)
    data       = await CosmicBotz.stats()
    await message.reply_text(
        f"<b>❍ @{me.username} ɪs ᴏɴʟɪɴᴇ.</b>\n\n"
        f"<blockquote>"
        f"❍ ᴜᴘᴛɪᴍᴇ    :  {uptime_str}\n"
        f"❍ ᴜsᴇʀs      :  {data['users']}\n"
        f"❍ ᴄʜᴀɴɴᴇʟs  :  {data['channels']}"
        f"</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /users  (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("users") & filters.private & admin_filter)
async def users_handler(client: Client, message: Message):
    count = await CosmicBotz.total_users()
    await message.reply_text(
        f"<blockquote>❍ ᴛᴏᴛᴀʟ ᴜsᴇʀs :  <code>{count}</code></blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /logs  (owner only)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("logs") & filters.private & owner_filter)
async def logs_handler(client: Client, message: Message):
    if not os.path.exists(LOG_FILE_NAME):
        await message.reply_text("<blockquote>ɴᴏ ʟᴏɢ ꜰɪʟᴇ ꜰᴏᴜɴᴅ ʏᴇᴛ.</blockquote>")
        return

    size = os.path.getsize(LOG_FILE_NAME)
    if size == 0:
        await message.reply_text("<blockquote>ʟᴏɢ ꜰɪʟᴇ ɪs ᴇᴍᴘᴛʏ.</blockquote>")
        return

    wait = await message.reply_text("<i>ᴜᴘʟᴏᴀᴅɪɴɢ ʟᴏɢ ꜰɪʟᴇ...</i>")
    try:
        await client.send_document(
            chat_id=message.chat.id,
            document=LOG_FILE_NAME,
            caption=(
                f"<b>❍ ʙᴏᴛ ʟᴏɢs</b>\n\n"
                f"<blockquote>"
                f"❍ ꜰɪʟᴇ  :  <code>{LOG_FILE_NAME}</code>\n"
                f"❍ sɪᴢᴇ  :  <code>{size / 1024:.1f} KB</code>\n"
                f"❍ ᴛɪᴍᴇ  :  <code>{datetime.now().strftime('%d-%b-%y %H:%M:%S')}</code>"
                f"</blockquote>"
            ),
        )
        await wait.delete()
    except Exception as e:
        await wait.edit_text(
            f"<b>ꜰᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ʟᴏɢ ꜰɪʟᴇ.</b>\n\n"
            f"<blockquote><code>{e}</code></blockquote>"
        )


# ──────────────────────────────────────────────────────────────────────────────
#  /broadcast  (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("broadcast") & filters.private & admin_filter)
async def broadcast_handler(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text(
            "<b>ᴜsᴀɢᴇ</b>\n\n"
            "<blockquote>ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴍᴇssᴀɢᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ, "
            "ᴛʜᴇɴ sᴇɴᴅ <code>/broadcast</code>.</blockquote>"
        )
        return

    to_broadcast = message.reply_to_message
    user_ids     = await CosmicBotz.get_all_users()
    total        = len(user_ids)

    status_msg = await message.reply_text(
        f"<blockquote>ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ᴛᴏ <b>{total}</b> ᴜsᴇʀs...</blockquote>"
    )

    sent = blocked = failed = 0
    start = datetime.now()

    for uid in user_ids:
        try:
            await to_broadcast.copy(uid)
            sent += 1
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
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
                    f"<b>❍ ʙʀᴏᴀᴅᴄᴀsᴛ ɪɴ ᴘʀᴏɢʀᴇss...</b>\n\n"
                    f"<blockquote>"
                    f"❍ sᴇɴᴛ     :  {sent}\n"
                    f"❍ ʙʟᴏᴄᴋᴇᴅ  :  {blocked}\n"
                    f"❍ ꜰᴀɪʟᴇᴅ   :  {failed}"
                    f"</blockquote>"
                )
            except Exception:
                pass

    elapsed = (datetime.now() - start).seconds
    await status_msg.edit_text(
        f"<b>❍ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇ.</b>\n\n"
        f"<blockquote>"
        f"❍ sᴇɴᴛ     :  {sent}\n"
        f"❍ ʙʟᴏᴄᴋᴇᴅ  :  {blocked}\n"
        f"❍ ꜰᴀɪʟᴇᴅ   :  {failed}\n"
        f"❍ ᴛɪᴍᴇ     :  {elapsed}s"
        f"</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /cleanup  (admins)
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("cleanup") & filters.private & admin_filter)
async def cleanup_handler(client: Client, message: Message):
    user_ids   = await CosmicBotz.get_all_users()
    status_msg = await message.reply_text(
        f"<blockquote>ᴄʜᴇᴄᴋɪɴɢ <b>{len(user_ids)}</b> ᴜsᴇʀs...</blockquote>"
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

    remaining = await CosmicBotz.total_users()
    await status_msg.edit_text(
        f"<b>❍ ᴄʟᴇᴀɴᴜᴘ ᴅᴏɴᴇ.</b>\n\n"
        f"<blockquote>"
        f"❍ ʀᴇᴍᴏᴠᴇᴅ    :  {removed}\n"
        f"❍ ʀᴇᴍᴀɪɴɪɴɢ  :  {remaining}"
        f"</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Uptime formatter
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_uptime(start: datetime) -> str:
    delta = datetime.now() - start
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    d, h   = divmod(h, 24)
    parts  = []
    if d: parts.append(f"{d}ᴅ")
    if h: parts.append(f"{h}ʜ")
    parts.append(f"{m}ᴍ {s}s")
    return " ".join(parts)
