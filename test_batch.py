import sys
import os
from unittest.mock import MagicMock

# 将当前目录加入路径
sys.path.append(os.getcwd())

from analysis import Analysis
from database import Database

def test_batch():
    # 模拟数据库，只返回3只股票
    db = Database()
    db.get_all_stock_codes = MagicMock(return_value=["601096", "603051", "002283"])
    
    analyzer = Analysis()
    # 注入模拟的数据库
    import database
    database.Database = MagicMock(return_value=db)
    
    print("开始测试批量分析逻辑...")
    # 运行批量分析（2个线程）
    analyzer.batch_analysis(max_workers=2)
    print("测试完成。")

if __name__ == "__main__":
    test_batch()
