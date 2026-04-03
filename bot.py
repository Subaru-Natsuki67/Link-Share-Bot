import asyncio
from datetime import datetime

import pyrogram.utils
from aiohttp import web
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import BotCommand

from config import (
    API_HASH,
    APP_ID,
    LOG_FILE_NAME,
    LOGGER,
    PORT,
    TG_BOT_TOKEN,
    TG_BOT_WORKERS,
)
from database import CosmicBotz
from plugins import web_server

# Allow big channel IDs (PyroFork / Pyrogram v2)
pyrogram.utils.MIN_CHANNEL_ID = -1009147483647

logger = LOGGER(__name__)


class Bot(Client):
    """Extended Pyrogram Client with startup / shutdown hooks."""

    def __init__(self):
        super().__init__(
            name="LinkShareBot",
            api_hash=API_HASH,
            api_id=APP_ID,
            plugins={"root": "plugins"},
            workers=TG_BOT_WORKERS,
            bot_token=TG_BOT_TOKEN,
            parse_mode=ParseMode.HTML,
        )

    async def start(self):
        # Install global error handler BEFORE connecting
        from plugins.errors import install_global_error_handler
        install_global_error_handler(self)

        # Initialise DB connection
        CosmicBotz.connect()

        await super().start()

        me = await self.get_me()
        self.uptime   = datetime.now()
        self.username = me.username

        # ── Cache bot username to avoid get_me() calls in link-building loops ──
        # This is the FIX for the FloodWait on invoke bug.
        # build_links() reads from this cache — zero Telegram API calls per link.
        from helper_func import set_bot_username
        set_bot_username(me.username)

        logger.info("Bot @%s is running! [workers=%s]", me.username, TG_BOT_WORKERS)

        # ── Set bot command menu ───────────────────────────────────────────────
        try:
            await self.set_bot_commands([
                BotCommand("start",      "sᴛᴀʀᴛ ʙᴏᴛ & ɢᴇᴛ ʜᴇʟᴘ"),
                BotCommand("help",       "ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅ ʟɪsᴛ"),
                BotCommand("about",      "ᴀʙᴏᴜᴛ ᴛʜɪs ʙᴏᴛ"),
                BotCommand("addch",      "ʀᴇɢɪsᴛᴇʀ ᴀ ɴᴇᴡ ᴄʜᴀɴɴᴇʟ"),
                BotCommand("delch",      "ʀᴇᴍᴏᴠᴇ ᴀ ᴄʜᴀɴɴᴇʟ"),
                BotCommand("channels",   "ᴍᴀɴᴀɢᴇ ʀᴇɢɪsᴛᴇʀᴇᴅ ᴄʜᴀɴɴᴇʟs"),
                BotCommand("links",      "ɴᴏʀᴍᴀʟ ᴅᴇᴇᴘ-ʟɪɴᴋs ꜰᴏʀ ᴀʟʟ ᴄʜᴀɴɴᴇʟs"),
                BotCommand("reqlink",    "ʀᴇǫᴜᴇsᴛ ᴅᴇᴇᴘ-ʟɪɴᴋs ꜰᴏʀ ᴀʟʟ ᴄʜᴀɴɴᴇʟs"),
                BotCommand("bulklink",   "ʙᴜʟᴋ ɢᴇɴᴇʀᴀᴛᴇ ʙᴏᴛʜ ʟɪɴᴋs"),
                BotCommand("reqmode",    "ᴛᴏɢɢʟᴇ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇ ꜰᴏʀ ᴀ ᴄʜᴀɴɴᴇʟ"),
                BotCommand("reqtime",    "sᴇᴛ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇ ᴅᴇʟᴀʏ"),
                BotCommand("approveon",  "ᴇɴᴀʙʟᴇ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇ ꜰᴏʀ ᴀʟʟ ᴄʜᴀɴɴᴇʟs"),
                BotCommand("approveoff", "ᴅɪsᴀʙʟᴇ ᴀᴜᴛᴏ-ᴀᴘᴘʀᴏᴠᴇ ꜰᴏʀ ᴀʟʟ ᴄʜᴀɴɴᴇʟs"),
                BotCommand("stats",      "ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs (ᴏᴡɴᴇʀ)"),
                BotCommand("status",     "ʙᴏᴛ ᴏɴʟɪɴᴇ sᴛᴀᴛᴜs"),
                BotCommand("broadcast",  "ʙʀᴏᴀᴅᴄᴀsᴛ ᴛᴏ ᴀʟʟ ᴜsᴇʀs"),
                BotCommand("cleanup",    "ʀᴇᴍᴏᴠᴇ ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs"),
                BotCommand("users",      "ᴛᴏᴛᴀʟ ᴜsᴇʀ ᴄᴏᴜɴᴛ"),
                BotCommand("logs",       "ᴅᴏᴡɴʟᴏᴀᴅ ʟᴏɢ ꜰɪʟᴇ (ᴏᴡɴᴇʀ)"),
            ])
            logger.info("Bot commands menu set.")
        except Exception as e:
            logger.warning("Failed to set bot commands: %s", e)

        # ── Health-check web server ────────────────────────────────────────────
        runner = web.AppRunner(await web_server())
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()
        logger.info("Web server listening on port %s.", PORT)

    async def stop(self, *args):
        await super().stop()
        logger.info("Bot stopped cleanly.")
