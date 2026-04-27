import unittest

from agent import Agent
from langchain_core.messages import HumanMessage


class FakeChunk:
    def __init__(self, text):
        self.text = text


class FakeStreamingModel:
    def __init__(self, chunks):
        self.chunks = chunks
        self.seen_messages = None

    def stream(self, messages):
        self.seen_messages = messages
        return iter(self.chunks)


class TestLangChainLlmParams(unittest.TestCase):
    def test_agent_stream_messages_text_aggregates_stream_chunks(self):
        agent = Agent()
        fake_model = FakeStreamingModel([
            FakeChunk('你'),
            FakeChunk('好'),
        ])
        agent.model = fake_model

        content = agent.stream_messages_text([
            HumanMessage(content='测试流式聚合')
        ])

        self.assertEqual(content, '你好')
        self.assertEqual(fake_model.seen_messages[0].content, '测试流式聚合')

    def test_agent_stream_messages_text_returns_non_empty_content(self):
        agent = Agent()

        content = agent.stream_messages_text([
            HumanMessage(content='只返回字符串 OK，不要解释。')
        ])

        self.assertIsInstance(content, str)
        self.assertTrue(content.strip(), f'LLM 返回空内容: {content!r}')


if __name__ == '__main__':
    unittest.main()
