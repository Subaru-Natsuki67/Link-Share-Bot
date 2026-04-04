import time
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from config import DB_NAME, DB_URL, LOGGER

logger = LOGGER(__name__)

_GLOBAL_TIMER_ID = "__global__"


class _Database:

    def __init__(self):
        self._client:   Optional[AsyncIOMotorClient] = None
        self._db       = None
        self._users    = None
        self._channels = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self):
        self._client   = AsyncIOMotorClient(DB_URL)
        self._db       = self._client[DB_NAME]
        self._users    = self._db["users"]
        self._channels = self._db["channels"]
        logger.info("Connected to MongoDB '%s'.", DB_NAME)

    # ── User methods ──────────────────────────────────────────────────────────

    async def add_user(self, user_id: int) -> bool:
        if await self._users.find_one({"_id": user_id}):
            return False
        await self._users.insert_one({"_id": user_id, "joined": int(time.time())})
        return True

    async def is_user_exist(self, user_id: int) -> bool:
        return bool(await self._users.find_one({"_id": user_id}))

    async def total_users(self) -> int:
        return await self._users.count_documents({})

    async def get_all_users(self) -> list[int]:
        return [doc["_id"] async for doc in self._users.find({}, {"_id": 1})]

    async def remove_user(self, user_id: int) -> bool:
        result = await self._users.delete_one({"_id": user_id})
        return result.deleted_count > 0

    # ── Channel methods ───────────────────────────────────────────────────────

    async def add_channel(self, channel_id: int, channel_name: str = "") -> bool:
        """Register a channel. Returns True if newly added."""
        if await self._channels.find_one({"_id": channel_id}):
            return False
        # Inherit global timer if set
        global_timer = await self.get_global_req_timer()
        await self._channels.insert_one({
            "_id":        channel_id,
            "name":       channel_name,
            "added":      int(time.time()),
            "req_mode":   False,
            "req_timer":  global_timer,
            "link_count": 0,
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
        return [doc async for doc in self._channels.find({"_id": {"$ne": _GLOBAL_TIMER_ID}})]

    async def total_channels(self) -> int:
        return await self._channels.count_documents({"_id": {"$ne": _GLOBAL_TIMER_ID}})

    async def update_channel_name(self, channel_id: int, name: str):
        await self._channels.update_one(
            {"_id": channel_id}, {"$set": {"name": name}}, upsert=True
        )

    # ── req_mode ──────────────────────────────────────────────────────────────

    async def set_req_mode(self, channel_id: int, enabled: bool):
        await self._channels.update_one(
            {"_id": channel_id}, {"$set": {"req_mode": enabled}}
        )

    async def get_req_mode(self, channel_id: int) -> bool:
        doc = await self._channels.find_one({"_id": channel_id}, {"req_mode": 1})
        return doc.get("req_mode", False) if doc else False

    # ── req_timer (per-channel + global default) ──────────────────────────────

    async def set_req_timer(self, channel_id: int, seconds: int):
        await self._channels.update_one(
            {"_id": channel_id}, {"$set": {"req_timer": seconds}}
        )

    async def get_req_timer(self, channel_id: int) -> int:
        doc = await self._channels.find_one({"_id": channel_id}, {"req_timer": 1})
        return doc.get("req_timer", 0) if doc else 0

    async def set_global_req_timer(self, seconds: int):
        """Set default timer for all existing channels AND store as global default."""
        # Update all existing channels
        await self._channels.update_many(
            {"_id": {"$ne": _GLOBAL_TIMER_ID}},
            {"$set": {"req_timer": seconds}}
        )
        # Store global default (used when adding new channels)
        await self._channels.update_one(
            {"_id": _GLOBAL_TIMER_ID},
            {"$set": {"req_timer": seconds}},
            upsert=True,
        )

    async def get_global_req_timer(self) -> int:
        doc = await self._channels.find_one({"_id": _GLOBAL_TIMER_ID})
        return doc.get("req_timer", 0) if doc else 0

    # ── Link count tracking ───────────────────────────────────────────────────

    async def increment_link_count(self, channel_id: int):
        """Increment the link-generation counter for a channel."""
        await self._channels.update_one(
            {"_id": channel_id},
            {"$inc": {"link_count": 1}},
        )

    async def get_link_count(self, channel_id: int) -> int:
        doc = await self._channels.find_one({"_id": channel_id}, {"link_count": 1})
        return doc.get("link_count", 0) if doc else 0

    async def get_top_channels(self, limit: int = 10) -> list[dict]:
        """Return channels sorted by link_count descending."""
        cursor = self._channels.find(
            {"_id": {"$ne": _GLOBAL_TIMER_ID}},
            {"name": 1, "link_count": 1}
        ).sort("link_count", -1).limit(limit)
        return [doc async for doc in cursor]

    # ── Stats ─────────────────────────────────────────────────────────────────

    async def stats(self) -> dict:
        total_links = 0
        async for doc in self._channels.find(
            {"_id": {"$ne": _GLOBAL_TIMER_ID}}, {"link_count": 1}
        ):
            total_links += doc.get("link_count", 0)
        return {
            "users":       await self.total_users(),
            "channels":    await self.total_channels(),
            "total_links": total_links,
        }


CosmicBotz = _Database()
