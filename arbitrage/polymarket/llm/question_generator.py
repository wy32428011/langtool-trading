import json
import logging
from typing import List, Dict, Any
from sqlalchemy import text
from arbitrage.polymarket.engine import polymarket_engine
from arbitrage.polymarket.llm.polymarket_agent import PolyMarketAgent

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from agent import Agent

class MarketQuestionGenerator:
    """
    市场问题生成器
    
    该类负责从数据库 (StarRocks) 中获取 Polymarket 的市场数据，
    并利用 PolyMarketAgent (LLM) 为市场的每个可能结果生成特定的疑问句。
    """
    def __init__(self, model_type: str = "zdzn"):
        """
        初始化市场问题生成器
        
        Args:
            model_type: 使用的 LLM 模型类型 ("zdzn", "deepseek", "v" 等)
        """
        self.engine = polymarket_engine
        self.agent = PolyMarketAgent(model_type=model_type)

    def fetch_markets(self, limit: int = 1000, market_ids: List[str] = None) -> List[Dict[str, Any]]:
        """
        从 StarRocks 获取市场数据
        
        Args:
            limit: 获取结果的数量限制
            market_ids: 可选的 ID 列表，用于获取特定市场
            
        Returns:
            List[Dict]: 市场数据的字典列表
        """
        if market_ids:
            # 根据指定 ID 列表查询
            ids_str = "'" + "','".join(market_ids) + "'"
            query = f"SELECT question, outcomes, id, description FROM polymarket_markets WHERE id IN ({ids_str})"
        else:
            # 随机取（带 limit）
            query = f"SELECT question, outcomes, id, description FROM polymarket_markets LIMIT {limit}"
        
        return self._execute_query(query)

    def fetch_markets_by_category_and_date(self, category: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """
        查询具有相同到期日期或相同类别的市场集合 (用于聚合分析)
        
        Args:
            category: 市场分类 (可选)
            end_date: 到期日期 (可选)，格式如 '2024-05-15'
            
        Returns:
            List[Dict]: 匹配要求的市场数据列表
        """
        if category and end_date:
            # 如果都提供，则过滤特定类别和日期
            query = f"SELECT question, outcomes, id, description FROM polymarket_markets WHERE category = '{category}' AND endDateIso = '{end_date}'"
        elif category:
            # 如果只提供 category，查询该类别下，在同一天到期 (endDateIso 相同) 的市场集合
            query = f"""
                SELECT question, outcomes, id, description 
                FROM polymarket_markets 
                WHERE category = '{category}' 
                AND endDateIso IN (
                    SELECT endDateIso 
                    FROM polymarket_markets 
                    WHERE category = '{category}' 
                    GROUP BY endDateIso 
                    HAVING COUNT(*) > 1
                )
                ORDER BY endDateIso
            """
        elif end_date:
            # 如果只提供 end_date，查询该日期下，属于相同 category 的市场集合
            query = f"""
                SELECT question, outcomes, id, description 
                FROM polymarket_markets 
                WHERE endDateIso = '{end_date}' 
                AND category IN (
                    SELECT category 
                    FROM polymarket_markets 
                    WHERE endDateIso = '{end_date}' 
                    GROUP BY category 
                    HAVING COUNT(*) > 1
                )
                ORDER BY category
            """
        else:
            # 如果都不提供，则查询整表中 endDateIso 和 category 相同的市场集合
            # 这里通常意味着返回所有具有相同 (endDateIso, category) 组合且该组合下有多个市场的记录
            query = """
                SELECT question, outcomes, id, description 
                FROM polymarket_markets 
                WHERE (endDateIso, category) IN (
                    SELECT endDateIso, category 
                    FROM polymarket_markets 
                    GROUP BY endDateIso, category 
                    HAVING COUNT(*) > 1
                )
                ORDER BY endDateIso, category
            """
        
        return self._execute_query(query)

    def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        执行 SQL 查询并处理结果
        
        Args:
            query: SQL 查询字符串
            
        Returns:
            List[Dict]: 解析后的市场数据字典列表
        """
        markets = []
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                for row in result:
                    # row 是一个元组 (question, outcomes, id, description)
                    # outcomes 在 SR 中存储为 JSON 字符串
                    try:
                        outcomes = json.loads(row[1]) if isinstance(row[1], str) else row[1]
                    except:
                        outcomes = row[1]
                    
                    markets.append({
                        "question": row[0],
                        "outcomes": outcomes,
                        "id": row[2],
                        "description": row[3]
                    })
            logger.info(f"Fetched {len(markets)} markets from database.")
        except Exception as e:
            logger.error(f"Error fetching markets: {str(e)}")
        return markets

    def generate_questions(self, limit: int = 1000, market_ids: List[str] = None, category: str = None, end_date: str = None):
        """
        生成疑问句的主逻辑
        
        根据提供的参数（ID、限制、类别或日期）获取市场，并调用 Agent 为每个结果生成具体的问题。
        
        Args:
            limit: 市场数量限制
            market_ids: 指定的市场 ID 列表
            category: 过滤的类别
            end_date: 过滤的结束日期
            
        Returns:
            List[Dict]: 包含原始数据和生成的问题列表的结果集
        """
        if category or end_date:
            markets = self.fetch_markets_by_category_and_date(category=category, end_date=end_date)
            # 如果提供了 limit，对结果进行切片
            if limit and len(markets) > limit:
                markets = markets[:limit]
        else:
            markets = self.fetch_markets(limit=limit, market_ids=market_ids)
            
        results = []
        
        for idx, market in enumerate(markets):
            question = market.get("question")
            outcomes = market.get("outcomes")
            market_id = market.get("id")
            description = market.get("description")
            
            if not question or not outcomes:
                continue
            
            generated_list = self.agent.generate_questions(question, outcomes, description)
            results.append({
                "id": market_id,
                "original_question": question,
                "outcomes": outcomes,
                "description": description,
                "generated_questions": generated_list
            })
            
            if (idx + 1) % 10 == 0:
                logger.info(f"Processed {idx + 1}/{len(markets)} markets.")
                
        return results

if __name__ == "__main__":
    # 示例运行
    generator = MarketQuestionGenerator(model_type="v")
    
    # 模式1: 按 ID 查询
    print("--- Mode 1: Fetch by ID ---")
    questions = generator.generate_questions(limit=10, market_ids=["114971"])
    for q in questions[:1]: # 仅打印第一个示例
        print(f"Original: {q['original_question']}")
        print(f"Generated: {q['generated_questions']}")

    # 模式2: 按类别和日期查询 (聚合模式)
    print("\n--- Mode 2: Fetch by Category and Date (Aggregated) ---")
    # 假设查询 'Politics' 类别下同一天到期的市场
    questions_agg = generator.generate_questions(category="Politics", limit=5)
    print(f"Fetched {len(questions_agg)} markets in aggregated mode.")
    for q in questions_agg[:1]:
        print(f"Original: {q['original_question']}")
        print(f"Generated: {q['generated_questions']}")

    agent_factory = Agent()
    polymarket_agent = agent_factory.get_polymarket_agent(model_type="v")

    for q in questions:
        print(f"Original: {q['original_question']}")
        print(f"Outcomes: {q['outcomes']}")
        print(f"Generated Questions:")
        for idx, gq in enumerate(q['generated_questions']):
            print(f"  [{idx}] {gq}")
        print("-" * 30)
        # 批量分析生成的疑问句
        statements = [{"question": gq} for gq in q['generated_questions']]
        result1 = polymarket_agent.analyze_market(statements)
        print(json.dumps(result1, indent=2))
        print("-" * 30)
