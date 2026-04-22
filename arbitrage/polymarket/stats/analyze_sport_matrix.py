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
    1. 矩阵结构方面，只需过滤出 3x4
    2. 三个一维数组中里面的4个元素前两个只有一个true，后两个也应该只有一个为true
    """
    # 规则: 第一维度数组长度是 3
    if len(combinations) != 3:
        return False
    
    # 规则: 第二维度数组长度必须是 4
    # 且前两个元素只有一个 true，后两个元素只有一个 true
    for combo in combinations:
        if len(combo) != 4:
            return False
        
        # 前两个元素：combo[0], combo[1]
        first_two = combo[0:2]
        if sum(1 for x in first_two if x is True) != 1:
            return False
            
        # 后两个元素：combo[2:4]
        last_two = combo[2:4]
        if sum(1 for x in last_two if x is True) != 1:
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
