import json
import logging
import time
from typing import List, Dict, Any
from arbitrage.polymarket.client import PolyMarketClient
from arbitrage.polymarket.redis_client import get_redis_client

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Redis Key
REDIS_KEY_ACTIVE_MARKETS = "polymarket:active_markets"
# 更新间隔 (秒)，默认 1 分钟
UPDATE_INTERVAL = 60

def fetch_all_active_markets(client: PolyMarketClient, limit: int = 100) -> List[Dict[str, Any]]:
    """
    分页拉取所有 active=True 的市场
    """
    all_markets = []
    offset = 0
    
    while True:
        logger.info(f"Fetching active markets from API (offset={offset})...")
        try:
            markets = client.get_markets(limit=limit, offset=offset, active=True)
            if not markets:
                break
            
            all_markets.extend(markets)
            
            if len(markets) < limit:
                break
            
            offset += limit
        except Exception as e:
            logger.error(f"Error fetching markets at offset {offset}: {e}")
            break
            
    return all_markets

def update_redis_with_markets(redis_client, markets: List[Dict[str, Any]]):
    """
    将市场数据更新到 Redis 中 (使用 HSET)
    """
    if not markets:
        logger.warning("No active markets to update.")
        # 如果获取不到活跃市场，考虑是否需要清空 Redis 里的数据，或者保持原样
        # 考虑到“如果是已经关闭的就移除”，如果没有活跃市场，那么 Redis 里的也应该被清空
        # 这里我们执行删除操作
        redis_client.delete(REDIS_KEY_ACTIVE_MARKETS)
        logger.info(f"Cleared Redis key: {REDIS_KEY_ACTIVE_MARKETS} as no active markets were found.")
        return

    logger.info(f"Updating {len(markets)} markets to Redis...")
    
    # 准备 HSET 数据 (field: market_id, value: market_json)
    mapping = {m['id']: json.dumps(m) for m in markets}
    
    # 管道操作以提高效率
    pipeline = redis_client.pipeline()
    # 这里我们采用全量更新策略，先写入一个新的临时 Key 然后 RENAME (原子性)
    # 这也确保了旧的已关闭市场会被自动从 Redis 中“移除”
    
    temp_key = f"{REDIS_KEY_ACTIVE_MARKETS}:temp"
    pipeline.delete(temp_key)
    # HSET 接受 mapping 参数 (redis-py >= 4.0)
    pipeline.hset(temp_key, mapping=mapping)
    pipeline.rename(temp_key, REDIS_KEY_ACTIVE_MARKETS)
    
    try:
        pipeline.execute()
        logger.info(f"Successfully updated {len(markets)} markets to Redis key: {REDIS_KEY_ACTIVE_MARKETS}")
    except Exception as e:
        logger.error(f"Failed to update Redis: {e}")

def main():
    # 初始化客户端
    client = PolyMarketClient()
    redis_client = get_redis_client()
    
    logger.info("Starting Polymarket active markets updater...")
    
    while True:
        try:
            # 1. 拉取所有未关闭的市场
            active_markets = fetch_all_active_markets(client, limit=1000)
            logger.info(f"Total active markets fetched: {len(active_markets)}")
            
            # 2. 更新到 Redis
            update_redis_with_markets(redis_client, active_markets)
        except Exception as e:
            logger.error(f"Unexpected error in updater loop: {e}")
            
        logger.info(f"Sleeping for {UPDATE_INTERVAL} seconds before next update...")
        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    main()
