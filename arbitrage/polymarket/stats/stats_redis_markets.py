import json
import logging
from collections import Counter
from datetime import datetime
from typing import Dict, Any, List

from arbitrage.polymarket.active_market_store import get_active_market_store

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_all_markets_from_store() -> List[Dict[str, Any]]:
    """
    从配置的数据存储获取所有市场数据
    """
    logger.info("Fetching all markets from active market store...")
    all_data = get_active_market_store().get_all_markets()
    if not all_data:
        logger.warning("No data found in active market store.")
        return []
    return list(all_data.values())

def analyze_markets(markets: List[Dict[str, Any]]):
    """
    分析市场数据并打印统计报告
    """
    if not markets:
        print("\n--- Polymarket active market store Data Stats ---")
        print("No markets found in active market store.")
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
    print(f"Polymarket active market store Stats Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("="*50)
    
    print(f"\n[Summary]")
    print(f"- Total Markets in active market store: {total_count}")
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
        markets = get_all_markets_from_store()
        analyze_markets(markets)
    except Exception as e:
        logger.error(f"Failed to generate stats: {e}")
