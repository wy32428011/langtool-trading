import unittest

from langchain.chat_models import init_chat_model
from langchain_openai import ChatOpenAI

from llm_transport_diagnostics import collect_llm_transport_results, collect_multi_config_results


# class TestLlmTransportDiagnostics(unittest.TestCase):
#     def test_collect_results_returns_all_three_transports(self):
#         result = collect_llm_transport_results('只返回字符串 OK，不要解释。')
#
#         self.assertEqual(set(result.keys()), {'requests', 'openai_sdk', 'langchain'})
#         for transport_name, payload in result.items():
#             self.assertIn('ok', payload, transport_name)
#             self.assertIn('content', payload, transport_name)
#             self.assertIn('raw', payload, transport_name)
#
#     def test_collect_multi_config_results_returns_named_configs(self):
#         configs = [
#             {
#                 'name': 'current',
#                 'llm_base_url': 'http://example.com/v1',
#                 'llm_model': 'gpt-5.4',
#                 'llm_api_key': 'api-key-2',
#                 'llm_temperature': 0.1,
#             },
#             {
#                 'name': 'deepseek-legacy',
#                 'llm_base_url': 'http://example.com/v1',
#                 'llm_model': 'DeepSeek-V3.2',
#                 'llm_api_key': 'test_deepseek',
#                 'llm_temperature': 0.1,
#             },
#         ]
#
#         result = collect_multi_config_results('只返回字符串 OK，不要解释。', configs)
#
#         self.assertEqual(set(result.keys()), {'current', 'deepseek-legacy'})
#         for config_name, payload in result.items():
#             self.assertEqual(set(payload.keys()), {'requests', 'openai_sdk', 'langchain'}, config_name)


# model = ChatOpenAI(
#     base_url="http://127.0.0.1:8317/v1",
#     model="gpt-5.4",
#     api_key="your-api-key-2",
#     temperature=0.1,
# )
model = init_chat_model(
    base_url="http://127.0.0.1:8317/v1",
    model="gpt-5.4",
    model_provider="openai",
    api_key="your-api-key-2",
    temperature=0.1,
    streaming=True,
)
result = model.stream("你是什么模型")
for chunk in result:
    print(chunk)

