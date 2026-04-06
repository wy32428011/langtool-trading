import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arbitrage.polymarket.polymarket_agent import PolyMarketAgent
from agent import Agent

class TestModelSwitching(unittest.TestCase):
    
    @patch('arbitrage.polymarket.polymarket_agent.ChatOpenAI')
    def test_polymarket_agent_init(self, mock_chat_openai):
        # 测试默认初始化 (zdzn)
        agent_zdzn = PolyMarketAgent()
        mock_chat_openai.assert_called_with(
            base_url="http://192.168.60.172:9090/v1",
            model="ZDZN",
            api_key="test_zdzn",
            temperature=0.1,
            max_retries=3
        )
        
        # 测试 deepseek 初始化
        agent_ds = PolyMarketAgent(model_type="deepseek")
        mock_chat_openai.assert_called_with(
            base_url="https://api.deepseek.com/v1",
            model="deepseek-reasoner",
            api_key="",
            temperature=0.1,
            max_retries=3
        )
        
        # 测试其他初始化 (llm)
        agent_other = PolyMarketAgent(model_type="qwen")
        mock_chat_openai.assert_called_with(
            base_url="http://172.16.3.27:49090/v1",
            model="DeepSeek-V3.2",
            api_key="test_deepseek",
            temperature=0.1,
            max_retries=3
        )

    @patch('arbitrage.polymarket.polymarket_agent.ChatOpenAI')
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
