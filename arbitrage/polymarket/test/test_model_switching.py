import sys
import os
import unittest
from unittest.mock import patch

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arbitrage.polymarket.llm.polymarket_agent import PolyMarketAgent
from agent import Agent
from config import settings

class TestModelSwitching(unittest.TestCase):

    @patch('arbitrage.polymarket.llm.polymarket_agent.ChatOpenAI')
    def test_polymarket_agent_init(self, mock_chat_openai):
        PolyMarketAgent()
        mock_chat_openai.assert_called_with(
            base_url=settings.zdzn_base_url,
            model=settings.zdzn_model,
            api_key=settings.zdzn_api_key,
            temperature=settings.llm_temperature,
            max_retries=3,
            streaming=True,
        )

        PolyMarketAgent(model_type="deepseek")
        mock_chat_openai.assert_called_with(
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            temperature=settings.llm_temperature,
            max_retries=3,
            streaming=True,
        )

        PolyMarketAgent(model_type="qwen")
        mock_chat_openai.assert_called_with(
            base_url=settings.vector_base_url,
            model=settings.vector_model,
            api_key=settings.vector_api_key,
            temperature=settings.llm_temperature,
            max_retries=3,
            streaming=True,
        )

    @patch('arbitrage.polymarket.llm.polymarket_agent.ChatOpenAI')
    def test_agent_factory_switching(self, mock_chat_openai):
        factory = Agent()
        
        # 通过工厂获取 zdzn agent
        polymarket_agent = factory.get_polymarket_agent(model_type="zdzn")
        self.assertIsInstance(polymarket_agent, PolyMarketAgent)
        
        # 通过工厂获取 deepseek agent
        polymarket_agent_ds = factory.get_polymarket_agent(model_type="deepseek")
        self.assertIsInstance(polymarket_agent_ds, PolyMarketAgent)

if __name__ == "__main__":
    unittest.main()
