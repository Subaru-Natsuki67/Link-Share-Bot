"""
plugins/errors.py
~~~~~~~~~~~~~~~~~
Global error / exception handler.

Catches unhandled exceptions in ALL handlers and:
  • Logs them with full traceback.
  • Handles FloodWait by sleeping and NOT crashing.
  • Suppresses known non-critical Telegram API errors silently.
  • Notifies the owner on unexpected critical errors (optional).

The bot will NEVER stop due to a handler exception.
"""
import asyncio
import traceback

from pyrogram import Client
from pyrogram.errors import (
    FloodWait,
    InputUserDeactivated,
    MessageDeleteForbidden,
    MessageIdInvalid,
    MessageNotModified,
    PeerIdInvalid,
    QueryIdInvalid,
    UserIsBlocked,
)

from config import LOGGER, OWNER_ID

logger = LOGGER(__name__)

# ── Non-critical errors we silently swallow ───────────────────────────────────
_SILENT_ERRORS = (
    MessageNotModified,     # editing a message with the same text
    MessageIdInvalid,       # message was deleted before we could act
    MessageDeleteForbidden, # can't delete in this context
    QueryIdInvalid,         # callback query expired (>10 min old)
    UserIsBlocked,          # user blocked the bot
    InputUserDeactivated,   # user deleted their account
    PeerIdInvalid,          # bad peer (stale chat reference)
)


# ──────────────────────────────────────────────────────────────────────────────
#  Disconnect hook — Pyrogram will auto-reconnect, just log it
# ──────────────────────────────────────────────────────────────────────────────

@Client.on_disconnect()
async def on_disconnect(client: Client):
    logger.warning("Bot disconnected — Pyrogram will auto-reconnect.")


# ──────────────────────────────────────────────────────────────────────────────
#  Central error handler
#  Pyrogram calls this for every exception raised inside a handler.
# ──────────────────────────────────────────────────────────────────────────────

async def handle_error(client: Client, exc: Exception) -> None:
    """
    Called by the global error middleware wrapper.
    Do NOT re-raise — returning normally suppresses the error.
    """
    # FloodWait: sleep and let the next message retry naturally
    if isinstance(exc, FloodWait):
        wait = exc.value + 1
        logger.warning("FloodWait received — sleeping %ss.", wait)
        await asyncio.sleep(wait)
        return

    # Silent / expected non-critical errors
    if isinstance(exc, _SILENT_ERRORS):
        logger.debug("Suppressed non-critical error: %s — %s", type(exc).__name__, exc)
        return

    # Anything else: log the full traceback
    tb = traceback.format_exc()
    logger.error("Unhandled exception in handler:\n%s", tb)

    # Optionally notify the owner (comment out if too noisy)
    try:
        short = str(exc)[:300]
        await client.send_message(
            OWNER_ID,
            f"⚠️ <b>Unhandled Bot Error</b>\n\n"
            f"<code>{type(exc).__name__}: {short}</code>\n\n"
            f"<i>Full traceback in logs. Bot is still running.</i>",
        )
    except Exception:
        pass  # Don't let the error notifier crash the error handler


# ──────────────────────────────────────────────────────────────────────────────
#  Decorator-based wrapper  (applied automatically to all handlers via monkey-patch)
#  This wraps every Pyrogram handler so no uncaught exception can kill the bot.
# ──────────────────────────────────────────────────────────────────────────────

_original_dispatch = None


def install_global_error_handler(client: Client) -> None:
    """
    Monkey-patch Client.dispatch to wrap every handler call in try/except.
    Call this once after the client is created (e.g. in bot.py after super().__init__).

    This ensures ALL plugins are covered without modifying each one individually.
    """
    global _original_dispatch

    if _original_dispatch is not None:
        return  # Already installed

    _original_dispatch = client.__class__.dispatch

    async def safe_dispatch(self, update, *args, **kwargs):
        try:
            return await _original_dispatch(self, update, *args, **kwargs)
        except FloodWait as e:
            wait = e.value + 1
            logger.warning("FloodWait %ss caught in dispatch — sleeping.", wait)
            await asyncio.sleep(wait)
        except _SILENT_ERRORS as e:
            logger.debug("Silent error in dispatch: %s", e)
        except Exception as e:
            await handle_error(self, e)

    client.__class__.dispatch = safe_dispatch
    logger.info("Global error handler installed on %s.", client.__class__.__name__)
