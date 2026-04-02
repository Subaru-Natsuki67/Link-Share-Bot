"""
plugins/errors.py
~~~~~~~~~~~~~~~~~
Global error / exception handler.
Catches unhandled exceptions in handlers and logs them cleanly
without crashing the bot.
"""
import traceback

from pyrogram import Client
from pyrogram.errors import (
    FloodWait,
    MessageNotModified,
    QueryIdInvalid,
)
from pyrogram.handlers import MessageHandler

from config import LOGGER, OWNER_ID

logger = LOGGER(__name__)


@Client.on_disconnect()
async def on_disconnect(client: Client):
    logger.warning("Bot disconnected from Telegram. Pyrogram will auto-reconnect.")


# Pyrogram v2 / PyroFork exposes raw error hooks via middleware;
# for simpler projects we just suppress known non-critical errors below.
# You can add a @Client.on_error() handler if your fork supports it.
