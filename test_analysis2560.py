import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import HumanMessage, AIMessage

from analysis2560 import Analysis2560


class FakeDatabase:
    def get_stock_info(self, stock_code):
        return {
            'code': stock_code,
            'name': '测试股票',
            'full_code': f'sh{stock_code}',
            'sector': '测试行业',
        }

    def get_stock_history(self, stock_code, days):
        history = []
        for index in range(120):
            history.append({
                'date': f'2026-01-{(index % 28) + 1:02d}',
                'close': 10 + index * 0.1,
                'volume': 1000 + index * 10,
                'pctChg': 1.0,
            })
        return list(reversed(history))

    def get_real_time_data(self, full_code):
        return {
            'current_price': 25.0,
            'change_percent': 2.5,
            'pe_ratio': 15.0,
        }


class FakeAgentFactory:
    def get_agent(self):
        raise AssertionError('旧的 get_agent().invoke() 路径不应再被调用')

    def stream_agent_text(self, payload):
        return json.dumps({
            'stock_code': '601096',
            'stock_name': '测试股票',
            'current_price': 25.0,
            'thought_process': '测试推理',
            'self_rebuttal': '测试反驳',
            'strategy_analysis': '测试分析',
            'ma_trend': '均线向上',
            'weekly_outlook': '震荡向上',
            'support': '24.5',
            'resistance': '26.0',
            'suggested_buy_price': 24.8,
            'suggested_sell_price': 23.9,
            'recommendation': '买入',
            'hold_suggestion': '继续持有',
            'empty_suggestion': '等待回踩后分批买入',
            'confidence': 0.78,
            'risk_warning': '注意波动风险',
        })


class TrulyEmptyAgentFactory:
    def get_agent(self):
        raise AssertionError('旧的 get_agent().invoke() 路径不应再被调用')

    def stream_agent_text(self, payload):
        return ''


class LowConfidenceAgentFactory:
    def get_agent(self):
        raise AssertionError('旧的 get_agent().invoke() 路径不应再被调用')

    def stream_agent_text(self, payload):
        return json.dumps({
            'stock_code': '601096',
            'stock_name': '测试股票',
            'current_price': 25.0,
            'thought_process': '测试推理',
            'self_rebuttal': '测试反驳',
            'strategy_analysis': '测试分析',
            'ma_trend': '均线向上',
            'weekly_outlook': '震荡向上',
            'support': '24.5',
            'resistance': '26.0',
            'suggested_buy_price': 24.8,
            'suggested_sell_price': 23.9,
            'recommendation': '买入',
            'hold_suggestion': '继续持有',
            'empty_suggestion': '等待回踩后分批买入',
            'confidence': 0.2,
            'risk_warning': '注意波动风险',
        })


class PreciseDecimalsAgentFactory:
    def get_agent(self):
        raise AssertionError('旧的 get_agent().invoke() 路径不应再被调用')

    def stream_agent_text(self, payload):
        return json.dumps({
            'stock_code': '601096',
            'stock_name': '测试股票',
            'current_price': 25.0,
            'thought_process': '测试推理',
            'self_rebuttal': '测试反驳',
            'strategy_analysis': '测试分析',
            'ma_trend': '均线向上',
            'weekly_outlook': '震荡向上',
            'support': '24.5',
            'resistance': '26.0',
            'suggested_buy_price': 24.876,
            'suggested_sell_price': 23.936,
            'recommendation': '买入',
            'hold_suggestion': '继续持有',
            'empty_suggestion': '等待回踩后分批买入',
            'confidence': 0.23456,
            'risk_warning': '注意波动风险',
        })


class TestAnalysis2560(unittest.TestCase):
    def test_build_summary_lines_formats_prices_and_confidence_with_two_decimals(self):
        analyzer = Analysis2560()

        summary = analyzer._build_summary_lines({
            'stock_code': '601096',
            'stock_name': '测试股票',
            'recommendation': '观望',
            'suggested_buy_price': 5.7,
            'suggested_sell_price': 5.5,
            'confidence': 0.2,
            'hold_suggestion': '继续观察',
            'empty_suggestion': '等待站稳后再考虑',
        })

        self.assertIn('建议买入价格: 5.70', summary)
        self.assertIn('建议卖出价格: 5.50', summary)
        self.assertIn('信心值: 0.20', summary)

    @patch('analysis2560.Database', return_value=FakeDatabase())
    @patch('analysis2560.Agent', return_value=FakeAgentFactory())
    def test_run_reads_text_from_message_additional_kwargs_when_content_is_empty(self, mock_agent, mock_database):
        analyzer = Analysis2560()

        result = analyzer.run('601096', save_to_file=False)

        self.assertIsNotNone(result)
        self.assertEqual(result['stock_code'], '601096')
        self.assertEqual(result['recommendation'], '买入')
        self.assertGreaterEqual(result['confidence'], 0.78)
        self.assertLessEqual(result['confidence'], 1.0)

    def test_extract_response_text_does_not_fallback_to_human_message(self):
        analyzer = Analysis2560()

        response = {
            'messages': [
                HumanMessage(content='user prompt'),
                AIMessage(content=''),
            ]
        }

        result = analyzer._extract_response_text(response)

        self.assertEqual(result, '')

    @patch('analysis2560.Database', return_value=FakeDatabase())
    @patch('analysis2560.Agent', return_value=TrulyEmptyAgentFactory())
    @patch('builtins.print')
    def test_run_reports_empty_llm_response_clearly(self, mock_print, mock_agent, mock_database):
        analyzer = Analysis2560()

        result = analyzer.run('601096', save_to_file=False)

        self.assertIsNone(result)
        printed = '\n'.join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
        self.assertIn('LLM 服务返回空响应', printed)

    @patch('analysis2560.Database', return_value=FakeDatabase())
    @patch('analysis2560.Agent', return_value=LowConfidenceAgentFactory())
    @patch.object(Analysis2560, '_calculate_indicators', return_value={
        'ma25': 24.0,
        'ma60': 21.0,
        'ma25_trend': '向上',
        'ma60_trend': '向上',
        'is_above_ma25': True,
        'is_above_ma60': True,
        'volume_ratio': 1.9,
        'current_price': 25.0,
    })
    @patch.object(Analysis2560, '_is_promising', return_value=True)
    def test_run_calibrates_confidence_above_raw_value_when_2560_evidence_is_strong(self, mock_is_promising, mock_indicators, mock_agent, mock_database):
        analyzer = Analysis2560()

        result = analyzer.run('601096', save_to_file=False)

        self.assertGreater(result['confidence'], 0.2)

    @patch('analysis2560.Database', return_value=FakeDatabase())
    @patch.object(Analysis2560, '_calculate_indicators', return_value={
        'ma25': 10.0,
        'ma60': 12.0,
        'ma25_trend': '向下',
        'ma60_trend': '向下',
        'is_above_ma25': False,
        'is_above_ma60': False,
        'volume_ratio': 0.6,
        'current_price': 9.5,
    })
    @patch.object(Analysis2560, '_is_promising', return_value=False)
    def test_run_prescreen_failure_builds_shared_low_confidence_range(self, mock_is_promising, mock_indicators, mock_database):
        analyzer = Analysis2560()

        result = analyzer.run('601096', save_to_file=False)

        self.assertNotEqual(result['confidence'], 0.1)
        self.assertGreaterEqual(result['confidence'], 0.03)
        self.assertLessEqual(result['confidence'], 0.20)

    @patch('analysis2560.Database', return_value=FakeDatabase())
    @patch('analysis2560.Agent', return_value=PreciseDecimalsAgentFactory())
    @patch.object(Analysis2560, '_calculate_indicators', return_value={
        'ma25': 24.0,
        'ma60': 21.0,
        'ma25_trend': '向上',
        'ma60_trend': '向上',
        'is_above_ma25': True,
        'is_above_ma60': True,
        'volume_ratio': 1.9,
        'current_price': 25.0,
    })
    @patch.object(Analysis2560, '_is_promising', return_value=True)
    def test_run_rounds_suggested_prices_and_confidence_to_two_decimals(self, mock_is_promising, mock_indicators, mock_agent, mock_database):
        analyzer = Analysis2560()

        result = analyzer.run('601096', save_to_file=False)

        self.assertEqual(result['suggested_buy_price'], 24.88)
        self.assertEqual(result['suggested_sell_price'], 23.94)
        self.assertEqual(result['confidence'], round(result['confidence'], 2))


if __name__ == '__main__':
    unittest.main()
