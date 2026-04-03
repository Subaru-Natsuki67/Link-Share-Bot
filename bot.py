"""
PyroFork Bot client.
All imports use the `pyrogram` namespace.
"""
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
            parse_mode=ParseMode.HTML,          # ← Fixed: set here (no await needed)
        )

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        # Install global error handler BEFORE connecting
        from plugins.errors import install_global_error_handler
        install_global_error_handler(self)

        # Initialise DB connection
        CosmicBotz.connect()

        await super().start()

        me = await self.get_me()
        self.uptime = datetime.now()
        self.username = me.username

        logger.info("Bot @%s is running! [workers=%s]", me.username, TG_BOT_WORKERS)

        # ── AUTO BOT COMMANDS (Telegram menu) ─────────────────────────────
        await self.set_bot_commands([
            BotCommand("start", "🚀 Start bot & get help"),
            BotCommand("addch", "➕ Add a new channel"),
            BotCommand("delch", "➖ Delete a channel"),
            BotCommand("channels", "📋 List all added channels"),
            BotCommand("stats", "📊 Bot statistics"),
            BotCommand("status", "📈 Current bot status"),
            BotCommand("broadcast", "📢 Broadcast message to all users"),
            BotCommand("cleanup", "🧹 Cleanup old/expired links"),
            BotCommand("users", "👥 List all bot users"),
            BotCommand("logs", "📜 View recent logs"),
            BotCommand("links", "🔗 Generate normal deep links"),
            BotCommand("reqlink", "📩 Generate request-join links"),
            BotCommand("bulklink", "📦 Bulk generate links"),
            BotCommand("reqmode", "🔄 Toggle request mode"),
            BotCommand("reqtime", "⏳ Set request link expiry time"),
            BotCommand("approveon", "✅ Enable auto-approve join requests"),
            BotCommand("approveoff", "❌ Disable auto-approve"),
        ])

        # Lightweight health-check web server
        runner = web.AppRunner(await web_server())
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()
        logger.info("Web server listening on port %s.", PORT)

    async def stop(self, *args):
        await super().stop()
        logger.info("Bot stopped cleanly.")