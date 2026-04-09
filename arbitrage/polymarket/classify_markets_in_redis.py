import json
import logging
import time
from typing import Dict, Any
from arbitrage.polymarket.redis_client import get_redis_client
from arbitrage.polymarket.update_event_topics import TopicUpdater

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
        判断市场是否未分类或分类为 "other"
        """
        topic = market.get("topic")
        return not topic or topic == "other" or topic == ""

    def classify_and_update(self, batch_size: int = 20):
        """
        拉取所有市场，筛选出未分类的进行分类并批量更新
        """
        logger.info("Scanning Redis for unclassified markets...")
        try:
            # 获取所有市场数据 (Hash 结构)
            all_markets_data = self.redis_client.hgetall(REDIS_KEY_ACTIVE_MARKETS)
            if not all_markets_data:
                logger.info("No markets found in Redis.")
                return 0

            unclassified_markets = []
            for market_id, market_json in all_markets_data.items():
                market = json.loads(market_json)
                if self.is_unclassified(market):
                    unclassified_markets.append((market_id, market))

            if not unclassified_markets:
                logger.info("All markets are already classified.")
                return 0

            logger.info(f"Found {len(unclassified_markets)} unclassified markets.")
            
            # 限制处理数量，避免单次循环时间过长
            to_process = unclassified_markets[:batch_size]
            updated_count = 0
            
            # 准备批量更新
            pipeline = self.redis_client.pipeline()
            
            for market_id, market in to_process:
                # 提取标题和描述进行分类
                # 在市场数据中，question 相当于事件的 title
                question = market.get("question")
                description = market.get("description")
                
                logger.info(f"Classifying market: {question[:50]}...")
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

    def run_forever(self, interval: int = 60, batch_size: int = 20):
        """
        持续运行分类任务
        """
        logger.info(f"Starting Redis Market Classifier loop (interval={interval}s, batch_size={batch_size})...")
        while True:
            updated = self.classify_and_update(batch_size=batch_size)
            
            # 如果还有未处理的，可以缩短等待时间或者继续处理
            # 简单起见，这里统一 sleep
            if updated > 0:
                logger.info(f"Processed {updated} markets, sleeping for {interval} seconds...")
            else:
                logger.info(f"No markets processed, sleeping for {interval} seconds...")
            
            time.sleep(interval)

def main():
    import sys
    model_type = sys.argv[1] if len(sys.argv) > 1 else "zdzn"
    classifier = RedisMarketClassifier(model_type=model_type)
    
    # 开始无限循环
    try:
        classifier.run_forever(interval=30, batch_size=10)
    except KeyboardInterrupt:
        logger.info("Classifier stopped by user.")

if __name__ == "__main__":
    main()
