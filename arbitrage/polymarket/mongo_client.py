from pymongo import MongoClient
from config import settings

_client = None


def get_mongo_client():
    global _client
    if _client is None:
        _client = MongoClient(settings.polymarket_mongo_uri)
    return _client


def get_polymarket_mongo_db():
    return get_mongo_client()[settings.polymarket_mongo_db]
