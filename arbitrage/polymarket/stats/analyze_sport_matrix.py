import sys
import os
import json
import logging
from typing import List, Dict, Any, Union

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from sqlalchemy import text
from arbitrage.polymarket.engine import polymarket_engine

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_matrix(matrix_data: Union[str, Dict, List]) -> List[List[bool]]:
    """
    解析 matrix 字段，处理两种格式：
    1. [ [true, false], [false, true] ]
    2. { "valid_combinations": [ [true, false], [false, true] ] }
    """
    if isinstance(matrix_data, str):
        try:
            matrix_data = json.loads(matrix_data)
        except Exception as e:
            logger.error(f"Failed to parse matrix JSON string: {e}")
            return []

    if isinstance(matrix_data, dict):
        if "valid_combinations" in matrix_data:
            return matrix_data["valid_combinations"]
        elif "error" in matrix_data:
            # logger.warning(f"Matrix data contains error: {matrix_data['error']}")
            return []
    
    if isinstance(matrix_data, list):
        return matrix_data

    return []

def check_combination_rules(combinations: List[List[bool]]) -> bool:
    """
    检查逻辑组合是否符合要求：
    1. 第一维度数组长度是四个 (len(combinations) == 4)
    2. 其中一个组合只有一个 true (sum(true) == 1)
    3. 其余三个组合必须是两个 true 和两个 false (sum(true) == 2, sum(false) == 2)
    """
    # 规则 1: 第一个维度数组长度是四个
    if len(combinations) != 4:
        return False
    
    # 统计每个组合中 true 的个数
    true_counts = []
    for combo in combinations:
        true_counts.append(sum(1 for val in combo if val is True))
    
    # 规则 2: 其中一个组合只有一个 true
    if true_counts.count(1) != 1:
        return False
        
    # 规则 3: 其余三个组合必须是两个 true (假设第二维长度是 4)
    # 用户说“两个 true 和两个 false”，意味着第二维长度必须是 4
    # 如果第二维长度不是 4，比如是 2 或 3，就不可能同时满足 2 个 true 和 2 个 false
    # 我们先检查所有组合的长度是否一致
    row_lengths = [len(combo) for combo in combinations]
    if any(length != 4 for length in row_lengths):
        return False

    # 检查除了那个 count=1 的，剩下的是否都是 count=2
    # 既然已经确定有一个是 1 了，我们只需要检查 true_counts 排序后是否为 [1, 2, 2, 2]
    if sorted(true_counts) != [1, 2, 2, 2]:
        return False
            
    return True

def fetch_and_analyze():
    """从数据库拿取数据并进行分析"""
    query = text("SELECT market_a_id, market_b_id, market_a_question, market_b_question, matrix FROM polymarket_sport_matrix")
    
    count_total = 0
    count_matched = 0
    
    try:
        with polymarket_engine.connect() as conn:
            result = conn.execute(query)
            for row in result:
                count_total += 1
                m_a_id, m_b_id, q_a, q_b, matrix_raw = row
                
                combinations = parse_matrix(matrix_raw)
                if not combinations:
                    continue
                
                if check_combination_rules(combinations):
                    count_matched += 1
                    print(f"--- Match Found ({count_matched}) ---")
                    print(f"Market A: {m_a_id} | {q_a}")
                    print(f"Market B: {m_b_id} | {q_b}")
                    # print(f"Matrix: {json.dumps(combinations)}")
                    print("-" * 30)

    except Exception as e:
        logger.error(f"Error fetching data from database: {e}")

    logger.info(f"Analysis complete. Total records: {count_total}, Matched: {count_matched}")

if __name__ == "__main__":
    fetch_and_analyze()
