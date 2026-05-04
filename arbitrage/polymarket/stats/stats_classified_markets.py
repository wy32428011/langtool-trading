import logging
from collections import defaultdict
from typing import Dict, Any, List

from arbitrage.polymarket.active_market_store import get_active_market_store

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_all_markets_from_store() -> List[Dict[str, Any]]:
    """
    从配置的数据存储获取所有市场数据
    """
    return list(get_active_market_store().get_all_markets().values())

def show_classified_markets():
    """
    显示已分类的市场数据详情
    """
    markets = get_all_markets_from_store()
    if not markets:
        print("No markets found in active market store.")
        return

    # 过滤出已分类的市场
    classified_markets = []
    for m in markets:
        topic = m.get("topic")
        if topic and topic != "other" and topic != "":
            classified_markets.append(m)

    if not classified_markets:
        print("No classified markets found.")
        return

    # 按 Topic 分组
    topic_groups = defaultdict(list)
    for m in classified_markets:
        topic_groups[m["topic"]].append(m)

    print("\n" + "="*80)
    print(f"Classified Markets Summary (Total: {len(classified_markets)})")
    print("="*80)

    # 打印各 Topic 统计
    for topic, items in sorted(topic_groups.items()):
        print(f"\n[{topic}] ({len(items)} markets)")
        # 打印该 Topic 下的市场 (限制显示前 20 个，防止屏幕爆炸)
        for i, m in enumerate(sorted(items, key=lambda x: x.get('endDateISO') or x.get('endDateIso', ''))[:20]):
            question = m.get("question", "N/A")
            end_date = m.get("endDateISO") or m.get("endDateIso") or "N/A"
            # 截断过长的标题
            if len(question) > 60:
                question = question[:57] + "..."
            print(f"  {i+1:2}. {question:<60} | Ends: {end_date}")
        
        if len(items) > 20:
            print(f"  ... and {len(items) - 20} more markets")

    print("\n" + "="*80)

if __name__ == "__main__":
    try:
        show_classified_markets()
    except Exception as e:
        logger.error(f"Failed to show classified markets: {e}")
