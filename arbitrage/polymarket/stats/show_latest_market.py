import json
import logging
from typing import Dict, Any, List
from datetime import datetime

from arbitrage.polymarket.active_market_store import get_active_market_store

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_latest_market() -> Dict[str, Any]:
    """
    从配置的数据存储获取最近一个更新的市场数据
    """
    logger.info("Fetching markets from active market store...")

    all_data = get_active_market_store().get_all_markets()
    if not all_data:
        logger.warning("No data found in active market store.")
        return None

    latest_market = None
    latest_time = ""

    # 尝试寻找具有最新 updatedAt 字段的市场
    for market in all_data.values():
        update_time = market.get("updatedAt") or market.get("createdAt") or market.get("updatedAtISO") or market.get("createdAtISO") or ""

        if not latest_market:
            latest_market = market
            latest_time = update_time
        elif update_time > latest_time:
            latest_market = market
            latest_time = update_time

    return latest_market

def show_market(market: Dict[str, Any]):
    """
    漂亮打印市场数据
    """
    if not market:
        print("\n--- No Market Data Found ---")
        return

    print("\n" + "="*50)
    print(f"Latest Polymarket Market Data Found in active market store")
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
