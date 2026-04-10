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

def get_all_markets_from_redis() -> List[Dict[str, Any]]:
    """
    从 Redis 获取所有市场数据
    """
    redis_client = get_redis_client()
    logger.info(f"Fetching all markets from Redis key: {REDIS_KEY_ACTIVE_MARKETS}...")
    
    all_data = redis_client.hgetall(REDIS_KEY_ACTIVE_MARKETS)
    if not all_data:
        logger.warning("No data found in Redis.")
        return []
        
    markets = []
    for market_id, market_json in all_data.items():
        try:
            market = json.loads(market_json)
            markets.append(market)
        except Exception as e:
            logger.error(f"Error parsing JSON for market {market_id}: {e}")
            
    return markets

def show_closed_markets(markets: List[Dict[str, Any]]):
    """
    过滤并展示已关闭的市场
    """
    # 筛选出 active 为 False 的市场
    closed_markets = [m for m in markets if m.get("active") is False]
    
    if not closed_markets:
        print("\n" + "="*80)
        print("No closed markets found in Redis.")
        print("="*80)
        return

    # 按结束日期排序 (如果有的话)
    def get_end_date(m):
        return m.get("endDateISO") or m.get("endDateIso") or "1970-01-01T00:00:00Z"

    closed_markets.sort(key=get_end_date, reverse=True)

    print("\n" + "="*120)
    print(f"Polymarket Closed Markets Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("-" * 120)
    print(f"{'ID':<15} | {'End Date':<25} | {'Topic':<15} | {'Question'}")
    print("-" * 120)

    for m in closed_markets:
        m_id = str(m.get("id", ""))[:15]
        end_date = m.get("endDateISO") or m.get("endDateIso") or "N/A"
        topic = m.get("topic") or "other"
        question = m.get("question", "N/A")
        
        # 截断过长的问题
        if len(question) > 60:
            question = question[:57] + "..."
            
        print(f"{m_id:<15} | {end_date:<25} | {topic:<15} | {question}")

    print("-" * 120)
    print(f"Total Closed Markets found: {len(closed_markets)}")
    print("="*120 + "\n")

if __name__ == "__main__":
    try:
        markets = get_all_markets_from_redis()
        show_closed_markets(markets)
    except Exception as e:
        logger.error(f"Failed to query closed markets: {e}")
