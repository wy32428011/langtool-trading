import sys
import os
import json

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import Agent

def demo_usage():
    # 1. 获取 PolyMarket Agent
    agent_factory = Agent()
    polymarket_agent = agent_factory.get_polymarket_agent(model_type="v")

    # 2. 模拟 PolyMarket 市场数据 (也可以是一个列表)
    market_data = {
        "question": "Will Jaylon Tyson score over 13.5 points?"
    }

    # 3. 如果有多个互斥或者相关的市场，可以传入列表
    # markets = [
    #     {"question": "Will Trump win the 2024 election?"},
    #     {"question": "Will Biden win the 2024 election?"}
    # ]

    markets = [
        {"question": "在同一场比赛中,A队会赢B队?"},
        {"question": "在同一场比赛中,B队会赢A队?"},
        {"question": "在同一场比赛中,A队会赢B队两球?"},
        {"question": "在同一场比赛中,A队不会赢B队两球?"}
    ]

    print("--- 场景1: 分析单个市场 ---")
    # 虽然单个市场逻辑组合很简单 [true], [false]，但这是调用方式
    result1 = polymarket_agent.analyze_market(market_data)
    print(json.dumps(result1, indent=2))

    print("\n--- 场景2: 分析多个相关市场 ---")
    # 比如分析两个候选人是否可能同时获胜（逻辑上不可能，Agent 应该返回有效的组合）
    result2 = polymarket_agent.analyze_market(markets)
    print(json.dumps(result2, indent=2))

if __name__ == "__main__":
    demo_usage()
