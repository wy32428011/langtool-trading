import json
import logging
import time
from typing import Dict, Any, List
from arbitrage.polymarket.active_market_store import get_active_market_store
from arbitrage.polymarket.client import PolyMarketClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_first_market_from_store(store) -> Dict[str, Any]:
    """
    从配置的数据存储中获取第一个市场的数据
    """
    try:
        market = store.get_first_market()
        if not market:
            logger.warning("No markets found in active market store.")
        return market
    except Exception as e:
        logger.error(f"Error fetching first market from active market store: {e}")

    return None

def monitor_orderbook(client: PolyMarketClient, token_ids: List[str], interval: int = 5):
    """
    循环监听指定 token 的订单簿
    """
    if not token_ids:
        logger.warning("No token IDs provided to monitor.")
        return

    logger.info(f"Starting to monitor orderbooks for tokens: {token_ids}")
    
    while True:
        try:
            for token_id in token_ids:
                logger.info(f"Fetching orderbook for token: {token_id}...")
                orderbook = client.get_orderbook(token_id)
                
                # 打印简单的订单簿信息
                # SDK 返回的是 OrderBookSummary 对象，包含 bids 和 asks 列表
                # 每个元素是 OrderSummary 对象，有 price 和 size 属性
                if isinstance(orderbook, dict):
                    bids = orderbook.get("bids", [])
                    asks = orderbook.get("asks", [])
                    best_bid = bids[0] if bids else "N/A"
                    best_ask = asks[0] if asks else "N/A"
                else:
                    bids = getattr(orderbook, "bids", [])
                    asks = getattr(orderbook, "asks", [])
                    best_bid = f"Price: {bids[0].price}, Size: {bids[0].size}" if bids else "N/A"
                    best_ask = f"Price: {asks[0].price}, Size: {asks[0].size}" if asks else "N/A"
                
                print(f"\n--- Orderbook for {token_id} ---")
                print(f"Best Bid: {best_bid}")
                print(f"Best Ask: {best_ask}")
                print(f"Bids Count: {len(bids)}, Asks Count: {len(asks)}")
                print("-" * 30)
            
            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error monitoring orderbook: {e}")
            time.sleep(interval)

def main():
    # 初始化
    store = get_active_market_store()
    poly_client = PolyMarketClient()

    # 1. 从配置的数据存储拿第一个市场
    market = get_first_market_from_store(store)
    if not market:
        logger.error("Could not find any market data in active market store. Please run update_active_markets_to_redis.py first.")
        return
    
    market_id = market.get('id')
    question = market.get('question')
    logger.info(f"Selected market: {question} (ID: {market_id})")
    
    # 2. 解析 token IDs
    # clobTokenIds 可能是 JSON 字符串或列表
    clob_token_ids_raw = market.get('clobTokenIds')
    if isinstance(clob_token_ids_raw, str):
        try:
            token_ids = json.loads(clob_token_ids_raw)
        except:
            token_ids = []
    elif isinstance(clob_token_ids_raw, list):
        token_ids = clob_token_ids_raw
    else:
        token_ids = []
    
    if not token_ids:
        logger.error(f"No clobTokenIds found for market {market_id}")
        return
    
    # 3. 监听订单簿
    monitor_orderbook(poly_client, token_ids)

if __name__ == "__main__":
    main()
