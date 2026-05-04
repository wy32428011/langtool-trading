import logging
import time
from typing import List, Dict, Any
from arbitrage.polymarket.active_market_store import get_active_market_store
from arbitrage.polymarket.client import PolyMarketClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 更新间隔 (秒)，默认 1 分钟
UPDATE_INTERVAL = 600

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

def update_store_with_markets(store, markets: List[Dict[str, Any]]):
    """
    将市场数据更新到配置的数据存储中。
    """
    if not markets:
        logger.warning("No active markets to update.")

    logger.info(f"Updating {len(markets)} markets to active market store, preserving existing topics...")
    try:
        store.replace_all_markets_preserving_topics(markets)
        logger.info(f"Successfully updated {len(markets)} markets to active market store.")
    except Exception as e:
        logger.error(f"Failed to update active market store: {e}")

def main():
    # 初始化客户端
    client = PolyMarketClient()
    store = get_active_market_store()

    logger.info("Starting Polymarket active markets updater...")
    
    while True:
        try:
            # 1. 拉取所有未关闭的市场
            active_markets = fetch_all_active_markets(client, limit=1000)
            logger.info(f"Total active markets fetched: {len(active_markets)}")
            
            # 2. 更新到配置的数据存储
            update_store_with_markets(store, active_markets)
        except Exception as e:
            logger.error(f"Unexpected error in updater loop: {e}")
            
        logger.info(f"Sleeping for {UPDATE_INTERVAL} seconds before next update...")
        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    main()
