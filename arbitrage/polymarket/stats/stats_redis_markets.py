import json
import logging
from collections import Counter
from datetime import datetime
from typing import Dict, Any, List

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

def analyze_markets(markets: List[Dict[str, Any]]):
    """
    分析市场数据并打印统计报告
    """
    if not markets:
        print("\n--- Polymarket Redis Data Stats ---")
        print("No markets found in Redis.")
        return

    total_count = len(markets)
    
    # 1. 分类统计 (Topic)
    topics = []
    unclassified_count = 0
    for m in markets:
        topic = m.get("topic")
        if not topic or topic == "other" or topic == "":
            unclassified_count += 1
            topics.append("Unclassified/Other")
        else:
            topics.append(topic)
    
    topic_counts = Counter(topics)
    
    # 2. 状态统计 (Active)
    active_counts = Counter([m.get("active", "Unknown") for m in markets])
    
    # 3. 结束日期统计 (endDateISO/endDateIso)
    # 统计过去、未来、以及缺失的
    now_iso = datetime.utcnow().isoformat()
    past_count = 0
    future_count = 0
    missing_date_count = 0
    
    for m in markets:
        end_date = m.get("endDateISO") or m.get("endDateIso")
        if not end_date:
            missing_date_count += 1
        elif end_date < now_iso:
            past_count += 1
        else:
            future_count += 1
            
    # 4. Token 统计 (clobTokenIds)
    total_tokens = 0
    markets_with_tokens = 0
    for m in markets:
        tokens = m.get("clobTokenIds", [])
        if isinstance(tokens, str):
            try:
                tokens = json.loads(tokens)
            except:
                tokens = []
        
        if tokens:
            total_tokens += len(tokens)
            markets_with_tokens += 1

    # 5. 打印报告
    print("\n" + "="*50)
    print(f"Polymarket Redis Stats Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("="*50)
    
    print(f"\n[Summary]")
    print(f"- Total Markets in Redis: {total_count}")
    print(f"- Markets with CLOB Tokens: {markets_with_tokens} ({markets_with_tokens/total_count*100:.1f}%)")
    print(f"- Total CLOB Tokens tracked: {total_tokens}")
    
    print(f"\n[Classification Status]")
    print(f"- Classified: {total_count - unclassified_count}")
    print(f"- Unclassified/Other: {unclassified_count}")
    print(f"- Coverage: {(total_count - unclassified_count)/total_count*100:.1f}%")
    
    print(f"\n[Topic Distribution]")
    for topic, count in topic_counts.most_common():
        print(f"  * {topic:<15}: {count:>4} ({count/total_count*100:>5.1f}%)")
        
    print(f"\n[Temporal Distribution (Relative to Now)]")
    print(f"- Future Ends: {future_count:>4} ({future_count/total_count*100:>5.1f}%)")
    print(f"- Past Ends:   {past_count:>4} ({past_count/total_count*100:>5.1f}%)")
    print(f"- Missing Date: {missing_date_count:>4} ({missing_date_count/total_count*100:>5.1f}%)")
    
    print(f"\n[Active Status]")
    for status, count in active_counts.items():
        print(f"- {status}: {count}")
    
    print("="*50 + "\n")

if __name__ == "__main__":
    try:
        markets = get_all_markets_from_redis()
        analyze_markets(markets)
    except Exception as e:
        logger.error(f"Failed to generate stats: {e}")
