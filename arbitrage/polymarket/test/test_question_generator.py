import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arbitrage.polymarket.llm.polymarket_agent import PolyMarketAgent
from arbitrage.polymarket.llm.question_generator import MarketQuestionGenerator
from arbitrage.polymarket.llm.update_event_topics import TopicUpdater


class FakeChunk:
    def __init__(self, text):
        self.text = text


class TestQuestionGenerator(unittest.TestCase):
    def test_generation_logic_uses_streaming_text(self):
        agent = PolyMarketAgent()
        agent.model = MagicMock()
        agent.model.invoke.side_effect = AssertionError('旧的 invoke 路径不应再被调用')
        agent.model.stream.return_value = iter([
            FakeChunk('["Will Trump win?", '),
            FakeChunk('"Will Trump lose?"]'),
        ])

        question = 'Will Trump win the 2024 election?'
        outcomes = ['Yes', 'No']
        description = "This market will resolve to 'Yes' if Donald Trump wins the 2024 US Presidential election."

        generated = agent.generate_questions(question, outcomes, description)

        self.assertIsInstance(generated, list)
        self.assertEqual(len(generated), 2)
        self.assertIn('Trump win', generated[0])

    def test_topic_updater_uses_stream_text(self):
        updater = TopicUpdater()
        updater.agent.stream_text = MagicMock(return_value='Politics')
        updater.agent.model = MagicMock()
        updater.agent.model.invoke.side_effect = AssertionError('旧的 invoke 路径不应再被调用')

        result = updater.determine_topic_llm('Election', 'Campaign news')

        self.assertEqual(result, 'Politics')
        updater.agent.stream_text.assert_called_once()

    @patch('arbitrage.polymarket.llm.question_generator.polymarket_engine')
    def test_generator_fetching(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        mock_result = [
            ('Will Trump win?', '["Yes", "No"]', 'id1', 'Description for Trump'),
            ('Who will win the Super Bowl?', '["Chiefs", "Eagles", "Others"]', 'id2', 'Description for SB'),
        ]
        mock_conn.execute.return_value = mock_result

        generator = MarketQuestionGenerator()
        generator.agent.generate_questions = MagicMock(side_effect=lambda q, o, d: [f'Q: {outcome}' for outcome in o])

        results = generator.generate_questions(limit=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], 'id1')
        self.assertEqual(results[0]['description'], 'Description for Trump')
        self.assertEqual(len(results[0]['generated_questions']), 2)
        self.assertEqual(len(results[1]['generated_questions']), 3)

        mock_conn.execute.return_value = [('Will Trump win?', '["Yes", "No"]', 'id1', 'Description for Trump')]
        results_by_id = generator.generate_questions(market_ids=['id1'])
        self.assertEqual(len(results_by_id), 1)
        self.assertEqual(results_by_id[0]['id'], 'id1')
        self.assertEqual(results_by_id[0]['original_question'], 'Will Trump win?')
        self.assertEqual(results_by_id[0]['description'], 'Description for Trump')


if __name__ == '__main__':
    unittest.main()
