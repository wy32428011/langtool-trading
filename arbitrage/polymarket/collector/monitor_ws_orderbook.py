import json
import logging
import time
from arbitrage.polymarket.client import PolyMarketClient
from arbitrage.polymarket.redis_client import get_redis_client

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REDIS_KEY_ACTIVE_MARKETS = "polymarket:active_markets"

def get_first_tokens_from_redis():
    """从 Redis 中获取第一个活跃市场的所有 Token ID"""
    redis_client = get_redis_client()
    try:
        keys = redis_client.hkeys(REDIS_KEY_ACTIVE_MARKETS)
        if not keys:
            return []
        
        market_json = redis_client.hget(REDIS_KEY_ACTIVE_MARKETS, keys[0])
        market = json.loads(market_json)
        clob_token_ids_raw = market.get('clobTokenIds')
        
        if isinstance(clob_token_ids_raw, str):
            token_ids = json.loads(clob_token_ids_raw)
        else:
            token_ids = clob_token_ids_raw
            
        return token_ids if isinstance(token_ids, list) else []
    except Exception as e:
        logger.error(f"Error fetching tokens from Redis: {e}")
    return []

def main():
    token_ids = get_first_tokens_from_redis()
    if not token_ids:
        logger.error("Could not find any valid token IDs to monitor.")
        return

    client = PolyMarketClient()
    
    def on_orderbook_update(message):
        """WebSocket 消息回调"""
        if message.get("event") == "book":
            data = message.get("data", {})
            asset_id = message.get("asset_id")
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            
            best_bid = bids[0] if bids else "N/A"
            best_ask = asks[0] if asks else "N/A"
            
            print(f"\n[WS Update] Token: {asset_id}")
            print(f"Best Bid: {best_bid}")
            print(f"Best Ask: {best_ask}")
            print(f"Bids: {len(bids)}, Asks: {len(asks)}")
        elif message.get("event") == "subscription_succeeded":
            pass # 已经在 ws_client 中记录日志
        else:
            logger.debug(f"Received other WS message: {message}")

    logger.info(f"Subscribing to WebSocket orderbook for tokens: {token_ids}...")
    # 可以批量订阅
    client.ws_client.subscribe(token_ids, channel="book", callback=on_orderbook_update)
    
    try:
        print("Listening for updates... Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping...")
        client.ws_client.stop()

if __name__ == "__main__":
    main()
