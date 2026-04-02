"""
database/mongodb.py
~~~~~~~~~~~~~~~~~~~
Async MongoDB wrapper — every public method is awaitable.
"""
import time
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from config import DB_NAME, DB_URL, LOGGER

logger = LOGGER(__name__)


class _Database:
    """Internal singleton that wraps Motor (async PyMongo)."""

    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None
        self._db       = None
        self._users    = None
        self._channels = None

    # ────────────────────────────────────────────
    #  Connection
    # ────────────────────────────────────────────

    def connect(self):
        """Call once at bot startup to initialise the Motor client."""
        self._client   = AsyncIOMotorClient(DB_URL)
        self._db       = self._client[DB_NAME]
        self._users    = self._db["users"]
        self._channels = self._db["channels"]
        logger.info("Connected to MongoDB database '%s'.", DB_NAME)

    # ────────────────────────────────────────────
    #  User methods
    # ────────────────────────────────────────────

    async def add_user(self, user_id: int) -> bool:
        """Add a user if not already present. Returns True if newly added."""
        if await self._users.find_one({"_id": user_id}):
            return False
        await self._users.insert_one({"_id": user_id, "joined": int(time.time())})
        return True

    async def is_user_exist(self, user_id: int) -> bool:
        return bool(await self._users.find_one({"_id": user_id}))

    async def total_users(self) -> int:
        return await self._users.count_documents({})

    async def get_all_users(self) -> list[int]:
        cursor = self._users.find({}, {"_id": 1})
        return [doc["_id"] async for doc in cursor]

    async def remove_user(self, user_id: int) -> bool:
        result = await self._users.delete_one({"_id": user_id})
        return result.deleted_count > 0

    # ────────────────────────────────────────────
    #  Channel methods
    # ────────────────────────────────────────────

    async def add_channel(self, channel_id: int, channel_name: str = "") -> bool:
        """Register a channel. Returns True if newly added."""
        if await self._channels.find_one({"_id": channel_id}):
            return False
        await self._channels.insert_one({
            "_id":       channel_id,
            "name":      channel_name,
            "added":     int(time.time()),
            "req_mode":  False,
            "req_timer": 0,
        })
        return True

    async def remove_channel(self, channel_id: int) -> bool:
        result = await self._channels.delete_one({"_id": channel_id})
        return result.deleted_count > 0

    async def is_channel_exist(self, channel_id: int) -> bool:
        return bool(await self._channels.find_one({"_id": channel_id}))

    async def get_channel(self, channel_id: int) -> Optional[dict]:
        return await self._channels.find_one({"_id": channel_id})

    async def get_all_channels(self) -> list[dict]:
        cursor = self._channels.find({})
        return [doc async for doc in cursor]

    async def total_channels(self) -> int:
        return await self._channels.count_documents({})

    async def update_channel_name(self, channel_id: int, name: str):
        await self._channels.update_one(
            {"_id": channel_id}, {"$set": {"name": name}}, upsert=True
        )

    async def set_req_mode(self, channel_id: int, enabled: bool):
        await self._channels.update_one(
            {"_id": channel_id}, {"$set": {"req_mode": enabled}}
        )

    async def get_req_mode(self, channel_id: int) -> bool:
        doc = await self._channels.find_one({"_id": channel_id}, {"req_mode": 1})
        return doc.get("req_mode", False) if doc else False

    async def set_req_timer(self, channel_id: int, seconds: int):
        await self._channels.update_one(
            {"_id": channel_id}, {"$set": {"req_timer": seconds}}
        )

    async def get_req_timer(self, channel_id: int) -> int:
        doc = await self._channels.find_one({"_id": channel_id}, {"req_timer": 1})
        return doc.get("req_timer", 0) if doc else 0

    # ────────────────────────────────────────────
    #  Stats
    # ────────────────────────────────────────────

    async def stats(self) -> dict:
        return {
            "users":    await self.total_users(),
            "channels": await self.total_channels(),
        }


# Public singleton — imported everywhere as `CosmicBotz`
CosmicBotz = _Database()
