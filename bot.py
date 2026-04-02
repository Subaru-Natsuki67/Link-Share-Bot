"""
bot.py
~~~~~~
PyroFork Bot client.  All imports use the `pyrogram` namespace
(PyroFork is a drop-in fork; it installs as `pyrofork` but exposes
exactly the same `pyrogram.*` package).
"""
import asyncio
from datetime import datetime

import pyrogram.utils
from aiohttp import web
from pyrogram import Client
from pyrogram.enums import ParseMode

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
        )

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        # Initialise DB connection first
        CosmicBotz.connect()

        await super().start()

        me = await self.get_me()
        self.uptime = datetime.now()
        self.username = me.username
        await self.set_parse_mode(ParseMode.HTML)

        logger.info("Bot @%s is running! [workers=%s]", me.username, TG_BOT_WORKERS)

        # Lightweight health-check web server (keeps Heroku/Koyeb dyno awake)
        runner = web.AppRunner(await web_server())
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()
        logger.info("Web server listening on port %s.", PORT)

    async def stop(self, *args):
        await super().stop()
        logger.info("Bot stopped cleanly.")
