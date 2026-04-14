import json
import logging
from collections import defaultdict
from typing import Dict, Any, List, Tuple

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
    all_data = redis_client.hgetall(REDIS_KEY_ACTIVE_MARKETS)
    if not all_data:
        return []
        
    markets = []
    for market_id, market_json in all_data.items():
        try:
            market = json.loads(market_json)
            markets.append(market)
        except Exception as e:
            logger.error(f"Error parsing JSON for market {market_id}: {e}")
            
    return markets

def find_markets_with_same_topic_and_date():
    """
    查询出所有相同 topic 并且有相同结束日期的 market
    """
    markets = get_all_markets_from_redis()
    if not markets:
        print("No markets found in Redis.")
        return

    # 分组：(topic, endDateISO) -> List[market]
    groups = defaultdict(list)
    
    for m in markets:
        topic = m.get("topic")
        # 兼容性处理 endDateISO 和 endDateIso
        end_date = m.get("endDateISO") or m.get("endDateIso")
        
        # 只有当 topic 有效且 end_date 有效时才进行分组统计
        if topic and topic != "other" and topic != "" and end_date:
            groups[(topic, end_date)].append(m)

    # 过滤出包含多个市场的组
    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

    if not duplicate_groups:
        print("No markets found with same topic and same end date.")
        return

    print("\n" + "="*100)
    print(f"Markets with same Topic and End Date (Total Groups: {len(duplicate_groups)})")
    print("="*100)

    # 按 Topic 和日期排序输出
    for (topic, end_date), items in sorted(duplicate_groups.items()):
        print(f"\n[Topic: {topic}] | [End Date: {end_date}] ({len(items)} markets)")
        for i, m in enumerate(items):
            question = m.get("question", "N/A")
            market_id = m.get("id") or m.get("marketId") or "N/A"
            # 截断过长的标题
            if len(question) > 80:
                question = question[:77] + "..."
            print(f"  {i+1:2}. {question:<80} | ID: {market_id}")

    print("\n" + "="*100)

if __name__ == "__main__":
    try:
        find_markets_with_same_topic_and_date()
    except Exception as e:
        logger.error(f"Failed to find markets with same topic and date: {e}")
