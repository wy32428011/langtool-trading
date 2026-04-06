import logging
from typing import List, Optional
from sqlalchemy import text
from arbitrage.polymarket.engine import polymarket_engine
from arbitrage.polymarket.polymarket_agent import PolyMarketAgent

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOPICS = [
    "Chess", "Coronavirus", "Poker", "Sports", 
    "Ukraine & Russia", "Politics", "NBA Playoffs", "Art", "Tech", 
    "Olympics", "US-current-affairs", "NFTs", "Science", "Business", 
    "Pop-Culture", "Crypto", "Space", "Global Politics"
]

class TopicUpdater:
    """
    事件主题更新器
    
    使用大语言模型 (LLM) 对 Polymarket 的事件进行分类 (当前配置为 2026 年以来的事件)，
    并将其归入预定义的主题列表中（如 Politics, Crypto, Sports 等）。
    """
    def __init__(self, model_type: str = "zdzn"):
        """
        初始化主题更新器
        
        Args:
            model_type: 使用的 LLM 模型类型
        """
        self.agent = PolyMarketAgent(model_type=model_type)
        self.engine = polymarket_engine

    def determine_topic_llm(self, title: Optional[str], description: Optional[str]) -> str:
        """
        使用 LLM 模型根据标题和描述判定事件所属主题
        
        Args:
            title: 事件标题
            description: 事件描述
            
        Returns:
            str: 匹配到的主题名称，若无法匹配则返回 "other"
        """
        if not title and not description:
            return "other"
            
        combined_text = f"Title: {title or 'N/A'}\nDescription: {description or 'N/A'}"
        
        prompt = f"""Analyze the following event title and description from a prediction market and classify it into EXACTLY ONE of the following topics:
{", ".join(TOPICS)}

If it does not fit any of the above topics clearly, return "other".

Event Data:
{combined_text}

Response format: Return ONLY the topic name (one of the strings above or "other"), no explanation, no quotes."""

        try:
            response = self.agent.model.invoke(prompt)
            topic = response.content.strip()
            
            # 简单清洗并验证返回的主题是否在列表中
            # 去除可能的引号或句点
            topic = topic.strip('"').strip("'").strip(".")
            
            # 模糊匹配：如果 LLM 返回了类似 "Politics." 或 "politics"，尝试匹配
            for t in TOPICS:
                if t.lower() == topic.lower():
                    return t
            
            if topic.lower() == "other":
                return "other"
                
            # 如果 LLM 返回了一个不在列表中的词，记录并返回 other
            logger.debug(f"LLM returned unknown topic: {topic}")
            return "other"
        except Exception as e:
            logger.error(f"Error calling LLM for topic determination: {e}")
            return "other"

    def update_event_topics(self, limit: Optional[int] = None):
        """
        扫描数据库中未分类或分类为 "other" 的事件 (仅限 2026 年以来的事件)，
        并使用 LLM 更新其主题
        
        Args:
            limit: 限制更新的记录条数
        """
        # 1. 检查列是否存在，如果不存在则添加
        try:
            with self.engine.begin() as conn:
                try:
                    conn.execute(text("SELECT topic FROM polymarket_events LIMIT 1"))
                    logger.info("Column 'topic' already exists.")
                except Exception:
                    logger.info("Adding 'topic' column to polymarket_events...")
                    conn.execute(text("ALTER TABLE polymarket_events ADD COLUMN topic VARCHAR(128) COMMENT '主题标签'"))
        except Exception as e:
            logger.warning(f"Could not ensure column exists: {e}")

        # 2. 获取未处理或 topic 为空的事件 (仅处理 2026 年以来的事件)
        query_str = """
            SELECT id, title, description 
            FROM polymarket_events 
            WHERE (topic IS NULL OR topic = '' OR topic = 'other')
            AND (creationDate >= '2026-01-01' OR startDate >= '2026-01-01')
        """
        if limit:
            query_str += f" LIMIT {limit}"
        query = text(query_str)
        
        events_to_process = []
        try:
            with self.engine.connect() as conn:
                result = conn.execute(query)
                for row in result:
                    events_to_process.append({
                        "id": row[0],
                        "title": row[1],
                        "description": row[2]
                    })
            
            logger.info(f"Found {len(events_to_process)} events to process.")
            
            # 3. 逐个处理并更新 (LLM 调用通常不适合超大批量 execute)
            total_updated = 0
            update_sql = text("UPDATE polymarket_events SET topic = :topic WHERE id = :id")
            
            for event in events_to_process:
                topic = self.determine_topic_llm(event["title"], event["description"])
                
                with self.engine.begin() as conn:
                    conn.execute(update_sql, {"topic": topic, "id": event["id"]})
                
                total_updated += 1
                if total_updated % 10 == 0:
                    logger.info(f"Updated {total_updated}/{len(events_to_process)} events...")
                    
            logger.info(f"Topic update completed. Total: {total_updated}")
            
        except Exception as e:
            logger.error(f"Error during topic update: {e}")

if __name__ == "__main__":
    import sys
    # 可以通过命令行参数指定 limit，例如 python update_event_topics.py 50
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    updater = TopicUpdater()
    updater.update_event_topics(limit=limit)
