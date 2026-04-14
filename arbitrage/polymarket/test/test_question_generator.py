import sys
import os

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arbitrage.polymarket.llm.polymarket_agent import PolyMarketAgent
from arbitrage.polymarket.llm.question_generator import MarketQuestionGenerator
from unittest.mock import MagicMock, patch


def test_generation_logic():
    # 1. 模拟 LLM 返回
    agent = PolyMarketAgent()
    agent.model = MagicMock()
    # 模拟返回 JSON 数组
    agent.model.invoke.return_value.content = '["Will Trump win?", "Will Trump lose?"]'
    
    question = "Will Trump win the 2024 election?"
    outcomes = ["Yes", "No"]
    description = "This market will resolve to 'Yes' if Donald Trump wins the 2024 US Presidential election."
    
    generated = agent.generate_questions(question, outcomes, description)
    print(f"Original: {question}")
    print(f"Generated: {generated}")
    assert isinstance(generated, list)
    assert len(generated) == 2
    assert "Trump win" in generated[0]

@patch('arbitrage.polymarket.question_generator.polymarket_engine')
def test_generator_fetching(mock_engine):
    # 2. 模拟数据库查询
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    
    # 模拟从 DB 返回的数据 (question, outcomes, id, description)
    mock_result = [
        ("Will Trump win?", '["Yes", "No"]', "id1", "Description for Trump"),
        ("Who will win the Super Bowl?", '["Chiefs", "Eagles", "Others"]', "id2", "Description for SB")
    ]
    mock_conn.execute.return_value = mock_result
    
    generator = MarketQuestionGenerator()
    # 模拟 agent.generate_questions
    generator.agent.generate_questions = MagicMock(side_effect=lambda q, o, d: [f"Q: {outcome}" for outcome in o])
    
    # 测试 limit 方式
    results = generator.generate_questions(limit=2)
    assert len(results) == 2
    assert results[0]['id'] == "id1"
    assert results[0]['description'] == "Description for Trump"
    assert len(results[0]['generated_questions']) == 2
    assert len(results[1]['generated_questions']) == 3
    
    # 测试 market_ids 方式
    mock_conn.execute.return_value = [("Will Trump win?", '["Yes", "No"]', "id1", "Description for Trump")]
    results_by_id = generator.generate_questions(market_ids=["id1"])
    assert len(results_by_id) == 1
    assert results_by_id[0]['id'] == "id1"
    assert results_by_id[0]['original_question'] == "Will Trump win?"
    assert results_by_id[0]['description'] == "Description for Trump"

    print("\nFetched and Generated results (with multiple questions):")
    for r in results:
        print(f"- ID: {r['id']}, Questions: {r['generated_questions']}")

if __name__ == "__main__":
    test_generation_logic()
    test_generator_fetching()
    print("\nAll tests passed!")
