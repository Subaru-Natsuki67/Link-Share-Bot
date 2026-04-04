"""
plugins/utils.py
~~~~~~~~~~~~~~~~
Utility commands available to all users and admins.

Public (anyone):
  /start  — handled in start.py
  /ping   — ᴘɪɴɢ ʙᴏᴛ ʟᴀᴛᴇɴᴄʏ
  /myid   — ɢᴇᴛ ʏᴏᴜʀ ᴏᴡɴ ᴜsᴇʀ ɪᴅ
  /id     — ɢᴇᴛ ᴀɴʏᴏɴᴇ's ɪᴅ (ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇɪʀ ᴍᴇssᴀɢᴇ)

Admin only:
  /top    — ᴛᴏᴘ 10 ᴍᴏsᴛ-ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟs
  /checkch — ᴠᴇʀɪꜰʏ ʙᴏᴛ sᴛɪʟʟ ʜᴀs ᴀᴅᴍɪɴ ɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs
"""
import time

from pyrogram import Client, filters
from pyrogram.errors import ChatAdminRequired, UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ADMINS, LOGGER
from database import CosmicBotz

logger = LOGGER(__name__)
admin_filter = filters.user(ADMINS)


# ──────────────────────────────────────────────────────────────────────────────
#  /ping  — anyone
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("ping") & filters.private)
async def ping_handler(client: Client, message: Message):
    start = time.monotonic()
    sent  = await message.reply_text("<i>ᴘɪɴɢɪɴɢ...</i>")
    latency = (time.monotonic() - start) * 1000
    await sent.edit_text(
        f"<blockquote>🏓 ᴘᴏɴɢ!\n❍ ʟᴀᴛᴇɴᴄʏ : <b>{latency:.0f}ms</b></blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /myid  — anyone: get your own user ID + username
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("myid") & filters.private)
async def myid_handler(client: Client, message: Message):
    user = message.from_user
    uname = f"@{user.username}" if user.username else "ɴᴏ ᴜsᴇʀɴᴀᴍᴇ"
    await message.reply_text(
        f"<blockquote>"
        f"❍ ɪᴅ       : <code>{user.id}</code>\n"
        f"❍ ᴜsᴇʀɴᴀᴍᴇ : {uname}\n"
        f"❍ ɴᴀᴍᴇ    : {user.mention}"
        f"</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /id  — anyone: get your own or reply-target's ID
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("id") & filters.private)
async def id_handler(client: Client, message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    uname  = f"@{target.username}" if target.username else "ɴᴏɴᴇ"
    await message.reply_text(
        f"<blockquote>"
        f"❍ ɪᴅ       : <code>{target.id}</code>\n"
        f"❍ ᴜsᴇʀɴᴀᴍᴇ : {uname}\n"
        f"❍ ɴᴀᴍᴇ    : {target.mention}"
        f"</blockquote>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  /top  — admins: top 10 channels by link-generation count
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("top") & filters.private & admin_filter)
async def top_handler(client: Client, message: Message):
    channels = await CosmicBotz.get_top_channels(limit=10)
    if not channels:
        await message.reply_text(
            "<blockquote>📭 ɴᴏ ʟɪɴᴋs ɢᴇɴᴇʀᴀᴛᴇᴅ ʏᴇᴛ.</blockquote>"
        )
        return

    lines = ["<b>📊 ᴛᴏᴘ ᴄʜᴀɴɴᴇʟs ʙʏ ʟɪɴᴋ ᴄᴏᴜɴᴛ</b>\n"]
    medals = ["🥇", "🥈", "🥉"] + ["❍"] * 7

    for i, ch in enumerate(channels):
        name  = (ch.get("name") or "").strip() or f"Channel {ch['_id']}"
        count = ch.get("link_count", 0)
        lines.append(f"{medals[i]} <b>{name}</b>  —  <code>{count}</code> ʟɪɴᴋs")

    await message.reply_text("\n".join(lines))


# ──────────────────────────────────────────────────────────────────────────────
#  /checkch  — admins: verify bot still has admin rights in all channels
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("checkch") & filters.private & admin_filter)
async def checkch_handler(client: Client, message: Message):
    channels = await CosmicBotz.get_all_channels()
    if not channels:
        await message.reply_text(
            "<blockquote>📭 ɴᴏ ᴄʜᴀɴɴᴇʟs ʀᴇɢɪsᴛᴇʀᴇᴅ.</blockquote>"
        )
        return

    wait = await message.reply_text(
        f"<blockquote>🔍 ᴄʜᴇᴄᴋɪɴɢ <b>{len(channels)}</b> ᴄʜᴀɴɴᴇʟs…</blockquote>"
    )

    ok_list:     list[str] = []
    broken_list: list[str] = []

    for ch in channels:
        ch_id   = ch["_id"]
        ch_name = (ch.get("name") or "").strip() or f"Channel {ch_id}"
        try:
            me     = await client.get_chat_member(ch_id, "me")
            from pyrogram.enums import ChatMemberStatus
            if me.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                ok_list.append(f"✅ <b>{ch_name}</b>  <code>{ch_id}</code>")
            else:
                broken_list.append(f"⚠️ <b>{ch_name}</b>  <code>{ch_id}</code>  (ᴅᴇᴍᴏᴛᴇᴅ)")
        except (ChatAdminRequired, UserNotParticipant, Exception):
            broken_list.append(f"❌ <b>{ch_name}</b>  <code>{ch_id}</code>  (ɴᴏ ᴀᴄᴄᴇss)")

    await wait.delete()

    text_parts = [f"<b>🔍 ᴄʜᴀɴɴᴇʟ ʜᴇᴀʟᴛʜ ᴄʜᴇᴄᴋ</b>  [{len(channels)} ᴛᴏᴛᴀʟ]\n"]

    if ok_list:
        text_parts.append("<b>ᴡᴏʀᴋɪɴɢ:</b>")
        text_parts.extend(ok_list)

    if broken_list:
        text_parts.append("\n<b>ɪssᴜᴇs ꜰᴏᴜɴᴅ:</b>")
        text_parts.extend(broken_list)
        text_parts.append(
            "\n<blockquote>ᴜsᴇ /delch &lt;ɪᴅ&gt; ᴛᴏ ʀᴇᴍᴏᴠᴇ ʙʀᴏᴋᴇɴ ᴄʜᴀɴɴᴇʟs, "
            "ᴏʀ ʀᴇ-ᴀᴅᴅ ᴛʜᴇ ʙᴏᴛ ᴀs ᴀᴅᴍɪɴ ᴀɴᴅ ᴜsᴇ /addch ᴀɢᴀɪɴ.</blockquote>"
        )
    else:
        text_parts.append("\n<blockquote>✅ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴀʀᴇ ʜᴇᴀʟᴛʜʏ!</blockquote>")

    await message.reply_text("\n".join(text_parts))
