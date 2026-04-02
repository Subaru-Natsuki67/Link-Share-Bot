import logging
import os
from logging.handlers import RotatingFileHandler

# ──────────────────────────────────────────────
#  Logging setup
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler("bot.log", maxBytes=5_000_000, backupCount=3),
        logging.StreamHandler(),
    ],
)
LOGGER = logging.getLogger


def _env(key: str, default=None, required: bool = False):
    val = os.environ.get(key, default)
    if required and not val:
        raise ValueError(f"Environment variable '{key}' is required but not set.")
    return val


# ──────────────────────────────────────────────
#  Telegram credentials
# ──────────────────────────────────────────────
APP_ID: int = int(_env("APP_ID", required=True))
API_HASH: str = _env("API_HASH", required=True)
TG_BOT_TOKEN: str = _env("TG_BOT_TOKEN", required=True)

# ──────────────────────────────────────────────
#  Access control
# ──────────────────────────────────────────────
OWNER_ID: int = int(_env("OWNER_ID", required=True))

# Space-separated admin IDs (OWNER_ID is always an admin)
_raw_admins = _env("ADMINS", default="").split()
ADMINS: list[int] = list({OWNER_ID, *[int(x) for x in _raw_admins if x.isdigit()]})

# ──────────────────────────────────────────────
#  MongoDB
# ──────────────────────────────────────────────
DB_URL: str = _env("DB_URL", required=True)
DB_NAME: str = _env("DB_NAME", default="LinkShareBot")

# ──────────────────────────────────────────────
#  Optional / deployment settings
# ──────────────────────────────────────────────
TG_BOT_WORKERS: int = int(_env("TG_BOT_WORKERS", default=4))
PORT: int = int(_env("PORT", default=8080))

# Force-subscription channel (set to your channel ID or 0 to disable)
FORCE_SUB_CHANNEL: int = int(_env("FORCE_SUB_CHANNEL", default=0))

# How many seconds a generated invite link stays alive (default 5 min)
LINK_EXPIRY_SECONDS: int = int(_env("LINK_EXPIRY_SECONDS", default=300))
