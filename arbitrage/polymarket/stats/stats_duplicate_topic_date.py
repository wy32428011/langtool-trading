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

def find_markets_with_same_topic_and_date():
    """
    查询出所有相同 topic 并且有相同结束日期的 market
    """
    markets = get_all_markets_from_store()
    if not markets:
        print("No markets found in active market store.")
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
