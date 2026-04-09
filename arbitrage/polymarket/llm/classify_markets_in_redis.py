import json
import logging
import time
from typing import Dict, Any, Optional
from arbitrage.polymarket.redis_client import get_redis_client
from arbitrage.polymarket.llm.update_event_topics import TopicUpdater

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Redis Key
REDIS_KEY_ACTIVE_MARKETS = "polymarket:active_markets"

class RedisMarketClassifier:
    """
    Redis 市场分类器
    
    不断从 Redis 中拉取未分类的活跃市场，并使用 LLM 进行主题分类，然后更新回 Redis。
    """
    def __init__(self, model_type: str = "zdzn"):
        self.redis_client = get_redis_client()
        self.updater = TopicUpdater(model_type=model_type)

    def is_unclassified(self, market: Dict[str, Any]) -> bool:
        """
        判断市场是否未分类
        """
        topic = market.get("topic")
        # 只有当 topic 缺失、为空或显式为 None 时才视为未分类。
        # 如果 topic 已经是 "other"，说明已经被处理过一次且 LLM 判定为其他，不再重复处理。
        return topic is None or topic == ""

    def get_end_date(self, market: Dict[str, Any]) -> Optional[str]:
        """
        兼容处理 endDateISO 和 endDateIso
        """
        return market.get("endDateISO") or market.get("endDateIso")

    def classify_and_update(self, batch_size: int = 20):
        """
        拉取所有市场，筛选出未分类的进行分类并批量更新
        优先处理具有相同结束日期的数据
        """
        logger.debug("Scanning Redis for unclassified markets...")
        try:
            # 获取所有市场数据 (Hash 结构)
            all_markets_data = self.redis_client.hgetall(REDIS_KEY_ACTIVE_MARKETS)
            if not all_markets_data:
                logger.info("No markets found in Redis.")
                return 0

            unclassified_markets = []
            for market_id, market_json in all_markets_data.items():
                try:
                    market = json.loads(market_json)
                    if self.is_unclassified(market):
                        unclassified_markets.append((market_id, market))
                except Exception as e:
                    logger.error(f"Error parsing market {market_id}: {e}")

            if not unclassified_markets:
                return 0

            logger.info(f"Found {len(unclassified_markets)} unclassified markets.")
            
            # 根据结束日期进行分类优先级排序
            # 统计每个有效结束日期出现的次数
            date_counts = {}
            for _, market in unclassified_markets:
                end_date = self.get_end_date(market)
                if end_date:
                    date_counts[end_date] = date_counts.get(end_date, 0) + 1
            
            # 将市场分为两组：有重复有效结束日期的和其它的（包含唯一的或日期为空的）
            duplicates = []
            others = []
            for market_id, market in unclassified_markets:
                end_date = self.get_end_date(market)
                if end_date and date_counts.get(end_date, 0) > 1:
                    duplicates.append((market_id, market))
                else:
                    others.append((market_id, market))
            
            # 合并，重复的排在前面
            sorted_unclassified = duplicates + others
            
            # 限制处理数量，避免单次循环时间过长
            to_process = sorted_unclassified[:batch_size]
            updated_count = 0
            
            # 准备批量更新
            pipeline = self.redis_client.pipeline()
            
            for market_id, market in to_process:
                # 提取标题和描述进行分类
                # 在市场数据中，question 相当于事件的 title
                question = market.get("question")
                description = market.get("description")
                end_date = self.get_end_date(market)
                
                logger.info(f"Classifying market: {question[:50]}... (endDate: {end_date})")
                topic = self.updater.determine_topic_llm(question, description)
                
                # 更新 topic 字段
                market["topic"] = topic
                
                # 写回 Redis
                pipeline.hset(REDIS_KEY_ACTIVE_MARKETS, market_id, json.dumps(market))
                updated_count += 1

            if updated_count > 0:
                pipeline.execute()
                logger.info(f"Successfully updated {updated_count} markets in Redis.")
            
            return updated_count

        except Exception as e:
            logger.error(f"Error during Redis market classification: {e}")
            return 0

    def run_forever(self, batch_size: int = 20):
        """
        持续运行分类任务
        """
        logger.info(f"Starting Redis Market Classifier loop (batch_size={batch_size})...")
        while True:
            updated = self.classify_and_update(batch_size=batch_size)
            
            # 持续处理，直到没有新数据
            if updated > 0:
                logger.info(f"Processed {updated} markets, checking for more...")
            else:
                # 如果没有处理任何市场，短暂等待 1 秒防止 CPU 占用过高
                # 之前用户说不用 sleep，但这是在有数据处理的情况下的反馈。
                # 在没有数据时，极短的 sleep 是必要的，否则会变成死循环空转。
                time.sleep(1)

def main():
    import sys
    model_type = sys.argv[1] if len(sys.argv) > 1 else "zdzn"
    classifier = RedisMarketClassifier(model_type=model_type)
    
    # 开始无限循环
    try:
        classifier.run_forever(batch_size=10)
    except KeyboardInterrupt:
        logger.info("Classifier stopped by user.")

if __name__ == "__main__":
    main()
