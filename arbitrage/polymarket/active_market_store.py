import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from config import settings

logger = logging.getLogger(__name__)

ACTIVE_MARKETS_KEY = "polymarket:active_markets"


class ActiveMarketStore(Protocol):
    def get_all_markets(self) -> Dict[str, Dict[str, Any]]:
        ...

    def get_market(self, market_id: str) -> Optional[Dict[str, Any]]:
        ...

    def get_market_ids(self) -> List[str]:
        ...

    def get_first_market(self) -> Optional[Dict[str, Any]]:
        ...

    def update_market(self, market_id: str, market: Dict[str, Any]) -> None:
        ...

    def replace_all_markets_preserving_topics(self, markets: List[Dict[str, Any]]) -> None:
        ...

    def clear_active_markets(self) -> None:
        ...


class RedisActiveMarketStore:
    def __init__(self, redis_client=None):
        if redis_client is None:
            from arbitrage.polymarket.redis_client import get_redis_client

            redis_client = get_redis_client()
        self.redis_client = redis_client

    def get_all_markets(self) -> Dict[str, Dict[str, Any]]:
        data = self.redis_client.hgetall(ACTIVE_MARKETS_KEY)
        markets = {}
        for market_id, market_json in data.items():
            try:
                markets[str(market_id)] = json.loads(market_json)
            except Exception as exc:
                logger.warning("Failed to parse active market %s from Redis: %s", market_id, exc)
        return markets

    def get_market(self, market_id: str) -> Optional[Dict[str, Any]]:
        market_json = self.redis_client.hget(ACTIVE_MARKETS_KEY, str(market_id))
        if not market_json:
            return None
        try:
            return json.loads(market_json)
        except Exception as exc:
            logger.warning("Failed to parse active market %s from Redis: %s", market_id, exc)
            return None

    def get_market_ids(self) -> List[str]:
        return [str(market_id) for market_id in self.redis_client.hkeys(ACTIVE_MARKETS_KEY)]

    def get_first_market(self) -> Optional[Dict[str, Any]]:
        market_ids = self.get_market_ids()
        if not market_ids:
            return None
        return self.get_market(market_ids[0])

    def update_market(self, market_id: str, market: Dict[str, Any]) -> None:
        self.redis_client.hset(ACTIVE_MARKETS_KEY, str(market_id), json.dumps(market))

    def replace_all_markets_preserving_topics(self, markets: List[Dict[str, Any]]) -> None:
        if not markets:
            self.clear_active_markets()
            return

        existing_markets = self.get_all_markets()
        mapping = {}
        for market in markets:
            market_id = str(market["id"])
            existing_market = existing_markets.get(market_id)
            if existing_market and "topic" in existing_market and "topic" not in market:
                market["topic"] = existing_market["topic"]
            mapping[market_id] = json.dumps(market)

        temp_key = f"{ACTIVE_MARKETS_KEY}:temp"
        pipeline = self.redis_client.pipeline()
        pipeline.delete(temp_key)
        pipeline.hset(temp_key, mapping=mapping)
        pipeline.rename(temp_key, ACTIVE_MARKETS_KEY)
        pipeline.execute()

    def clear_active_markets(self) -> None:
        self.redis_client.delete(ACTIVE_MARKETS_KEY)


class MongoActiveMarketStore:
    def __init__(self, collection=None):
        if collection is None:
            from arbitrage.polymarket.mongo_client import get_polymarket_mongo_db

            db = get_polymarket_mongo_db()
            collection = db[settings.polymarket_mongo_active_markets_collection]
        self.collection = collection

    def get_all_markets(self) -> Dict[str, Dict[str, Any]]:
        return {
            str(doc["_id"]): doc.get("market", {})
            for doc in self.collection.find({}, {"market": 1})
        }

    def get_market(self, market_id: str) -> Optional[Dict[str, Any]]:
        doc = self.collection.find_one({"_id": str(market_id)}, {"market": 1})
        if not doc:
            return None
        return doc.get("market", {})

    def get_market_ids(self) -> List[str]:
        return [str(doc["_id"]) for doc in self.collection.find({}, {"_id": 1})]

    def get_first_market(self) -> Optional[Dict[str, Any]]:
        doc = self.collection.find_one({}, {"market": 1})
        if not doc:
            return None
        return doc.get("market", {})

    def update_market(self, market_id: str, market: Dict[str, Any]) -> None:
        self.collection.replace_one(
            {"_id": str(market_id)},
            {"_id": str(market_id), "market": market, "updated_at": datetime.now(timezone.utc)},
            upsert=True,
        )

    def replace_all_markets_preserving_topics(self, markets: List[Dict[str, Any]]) -> None:
        if not markets:
            self.clear_active_markets()
            return

        from pymongo import ReplaceOne

        existing_markets = self.get_all_markets()
        now = datetime.now(timezone.utc)
        operations = []
        incoming_ids = []

        for market in markets:
            market_id = str(market["id"])
            incoming_ids.append(market_id)
            existing_market = existing_markets.get(market_id)
            if existing_market and "topic" in existing_market and "topic" not in market:
                market["topic"] = existing_market["topic"]
            operations.append(
                ReplaceOne(
                    {"_id": market_id},
                    {"_id": market_id, "market": market, "updated_at": now},
                    upsert=True,
                )
            )

        if operations:
            self.collection.bulk_write(operations, ordered=False)
        self.collection.delete_many({"_id": {"$nin": incoming_ids}})

    def clear_active_markets(self) -> None:
        self.collection.delete_many({})


def get_active_market_store() -> ActiveMarketStore:
    backend = settings.polymarket_active_market_store_backend.strip().lower()
    if backend == "redis":
        return RedisActiveMarketStore()
    if backend in {"mongo", "mongodb"}:
        return MongoActiveMarketStore()
    raise ValueError(f"Unsupported active market store backend: {settings.polymarket_active_market_store_backend}")
