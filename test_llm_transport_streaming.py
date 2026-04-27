import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import HumanMessage

from llm_transport_diagnostics import _langchain_call, _openai_sdk_call, _requests_call


class FakeChunk:
    def __init__(self, text):
        self.text = text


class FakeStreamingModel:
    def __init__(self, chunks):
        self.chunks = chunks

    def stream(self, messages):
        return iter(self.chunks)

    def invoke(self, messages):
        raise AssertionError('旧的 invoke 路径不应再被调用')


class FakeOpenAIClient:
    def __init__(self, *args, **kwargs):
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=self.create,
            )
        )
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not kwargs.get('stream'):
            raise AssertionError('OpenAI SDK 必须启用 stream=True')
        return iter([
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='你'))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='好'))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
        ])


class FakeRequestsResponse:
    def __init__(self):
        self.ok = True

    def iter_lines(self):
        chunks = [
            'data: {"choices":[{"delta":{"content":"你"}}]}',
            'data: {"choices":[{"delta":{"content":"好"}}]}',
            'data: [DONE]',
        ]
        for line in chunks:
            yield line.encode('utf-8')


class TestLlmTransportStreaming(unittest.TestCase):
    @patch('llm_transport_diagnostics.requests.post', return_value=FakeRequestsResponse())
    def test_requests_call_aggregates_stream_chunks(self, mock_post):
        result = _requests_call('测试', 'http://example.com/v1', 'gpt-5.4', 'key', 0.1)

        self.assertTrue(result['ok'])
        self.assertEqual(result['content'], '你好')
        self.assertTrue(mock_post.call_args.kwargs['stream'])
    @patch('llm_transport_diagnostics.OpenAI', new=FakeOpenAIClient)
    def test_openai_sdk_call_aggregates_stream_chunks(self):
        result = _openai_sdk_call('测试', 'http://example.com/v1', 'gpt-5.4', 'key', 0.1)

        self.assertTrue(result['ok'])
        self.assertEqual(result['content'], '你好')

    @patch('llm_transport_diagnostics.Agent')
    def test_langchain_call_uses_stream_for_current_config(self, mock_agent_cls):
        mock_agent_cls.return_value.model = FakeStreamingModel([
            FakeChunk('你'),
            FakeChunk('好'),
        ])
        mock_agent_cls.return_value.stream_messages_text.return_value = '你好'

        result = _langchain_call('测试', 'http://172.16.3.27:48317/v1', 'gpt-5.4', 'api-key-2', 0.1)

        self.assertTrue(result['ok'])
        self.assertEqual(result['content'], '你好')
        mock_agent_cls.return_value.stream_messages_text.assert_called_once()

    @patch('llm_transport_diagnostics.ChatOpenAI')
    def test_langchain_call_uses_stream_for_override_config(self, mock_chat_openai):
        fake_model = FakeStreamingModel([
            FakeChunk('你'),
            FakeChunk('好'),
        ])
        mock_chat_openai.return_value = fake_model

        result = _langchain_call('测试', 'http://example.com/v1', 'gpt-5.4', 'key', 0.1)

        self.assertTrue(result['ok'])
        self.assertEqual(result['content'], '你好')
        mock_chat_openai.assert_called_once()


if __name__ == '__main__':
    unittest.main()
