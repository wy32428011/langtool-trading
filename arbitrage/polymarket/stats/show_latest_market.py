import json
import logging
from typing import Dict, Any, List
from datetime import datetime

from arbitrage.polymarket.redis_client import get_redis_client

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Redis Key
REDIS_KEY_ACTIVE_MARKETS = "polymarket:active_markets"

def get_latest_market() -> Dict[str, Any]:
    """
    从 Redis 获取最近一个更新的市场数据
    """
    redis_client = get_redis_client()
    logger.info(f"Fetching markets from Redis key: {REDIS_KEY_ACTIVE_MARKETS}...")
    
    all_data = redis_client.hgetall(REDIS_KEY_ACTIVE_MARKETS)
    if not all_data:
        logger.warning("No data found in Redis.")
        return None
        
    latest_market = None
    latest_time = ""
    
    # 尝试寻找具有最新 updatedAt 字段的市场
    for market_id, market_json in all_data.items():
        try:
            market = json.loads(market_json)
            # 兼容可能的字段名: updatedAt, createdAt, updatedAtISO, createdAtISO
            update_time = market.get("updatedAt") or market.get("createdAt") or market.get("updatedAtISO") or market.get("createdAtISO") or ""
            
            if not latest_market:
                latest_market = market
                latest_time = update_time
            elif update_time > latest_time:
                latest_market = market
                latest_time = update_time
        except Exception as e:
            logger.error(f"Error parsing JSON for market {market_id}: {e}")
            
    return latest_market

def show_market(market: Dict[str, Any]):
    """
    漂亮打印市场数据
    """
    if not market:
        print("\n--- No Market Data Found ---")
        return

    print("\n" + "="*50)
    print(f"Latest Polymarket Market Data Found in Redis")
    print("="*50)
    
    # 按照缩进打印 JSON
    print(json.dumps(market, indent=4, ensure_ascii=False))
    
    print("="*50 + "\n")

if __name__ == "__main__":
    try:
        market = get_latest_market()
        show_market(market)
    except Exception as e:
        logger.error(f"Failed to fetch market data: {e}")
