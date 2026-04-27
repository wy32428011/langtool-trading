import unittest
from unittest.mock import patch

from langchain_core.messages import HumanMessage, AIMessage

from analysis import Analysis
from analysisflow import AnalysisFlow
from tail_analysis import TailAnalysis


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
                'high': 10.5 + index * 0.1,
                'low': 9.5 + index * 0.1,
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

    def get_factor_158(self, stock_codes):
        return {code: 0.8 for code in stock_codes}


class TrulyEmptyAgent:
    def invoke(self, payload):
        return {
            'messages': [
                HumanMessage(content='prompt'),
                AIMessage(content=''),
            ]
        }


class EmptyAgentFactory:
    def get_agent(self):
        raise AssertionError('旧的 get_agent().invoke() 路径不应再被调用')

    def stream_agent_text(self, payload):
        return ''


class EmptyModel:
    def invoke(self, messages):
        raise AssertionError('旧的 model.invoke() 路径不应再被调用')


class EmptyFlowAgentFactory:
    @property
    def model(self):
        return EmptyModel()

    def stream_messages_text(self, messages):
        return ''


class InvalidJsonFlowAgentFactory:
    @property
    def model(self):
        return EmptyModel()

    def stream_messages_text(self, messages):
        return 'this is not valid json'


class FlowLowConfidenceAgentFactory:
    @property
    def model(self):
        return EmptyModel()

    def stream_messages_text(self, messages):
        return '''{
            "stock_code": "601096",
            "stock_name": "测试股票",
            "current_price": 25.0,
            "thought_process": "综合研判后偏强",
            "self_rebuttal": "若量能不足则可能走弱",
            "analysis": "基本面与技术面共振偏多",
            "trend": "上涨",
            "weekly_outlook": "未来一周震荡上行",
            "support": 24.2,
            "resistance": 27.5,
            "recommendation": "买入",
            "hold_suggestion": "继续持有",
            "empty_suggestion": "回踩分批介入",
            "predicted_price": 27.5,
            "predicted_buy_price": 24.8,
            "predicted_sell_price": 23.9,
            "confidence": 0.2,
            "risk_warning": "注意冲高回落风险"
        }'''


class FlowPreciseDecimalsAgentFactory:
    @property
    def model(self):
        return EmptyModel()

    def stream_messages_text(self, messages):
        return '''{
            "stock_code": "601096",
            "stock_name": "测试股票",
            "current_price": 25.0,
            "thought_process": "综合研判后偏强",
            "self_rebuttal": "若量能不足则可能走弱",
            "analysis": "基本面与技术面共振偏多",
            "trend": "上涨",
            "weekly_outlook": "未来一周震荡上行",
            "support": 24.2,
            "resistance": 27.5,
            "recommendation": "买入",
            "hold_suggestion": "继续持有",
            "empty_suggestion": "回踩分批介入",
            "predicted_price": 27.598,
            "predicted_buy_price": 24.876,
            "predicted_sell_price": 23.936,
            "confidence": 0.23456,
            "risk_warning": "注意冲高回落风险"
        }'''


class QuickAnalysisLowConfidenceAgentFactory:
    def stream_agent_text(self, payload):
        return '''{
            "recommendation": "买入",
            "trend": "放量走强",
            "action": "买入",
            "target_price": 26.8,
            "hold_suggestion": "可继续持有",
            "empty_suggestion": "可考虑分批买入",
            "thought_process": "均线多头，量价配合，动量较强",
            "confidence": 0.2
        }'''


class QuickAnalysisPreciseConfidenceAgentFactory:
    def stream_agent_text(self, payload):
        return '''{
            "recommendation": "买入",
            "trend": "放量走强",
            "action": "买入",
            "target_price": 26.876,
            "hold_suggestion": "可继续持有",
            "empty_suggestion": "可考虑分批买入",
            "thought_process": "均线多头，量价配合，动量较强",
            "confidence": 0.23456
        }'''


class AnalysisStockLowConfidenceAgentFactory:
    def stream_agent_text(self, payload):
        return '''{
            "stock_code": "601096",
            "stock_name": "测试股票",
            "thought_process": "趋势转强，均线多头，量价共振",
            "self_rebuttal": "短线若放量不持续则可能回落",
            "analysis": "当前处于偏强上行结构",
            "trend": "上涨",
            "weekly_outlook": "未来一周大概率震荡上行",
            "support": 24.2,
            "resistance": 27.5,
            "recommendation": "买入",
            "hold_suggestion": "继续持有，跌破支撑减仓",
            "empty_suggestion": "回踩支撑可分批介入",
            "predicted_price": 27.5,
            "predicted_buy_price": 24.8,
            "predicted_sell_price": 23.9,
            "confidence": 0.2,
            "risk_warning": "注意冲高回落风险"
        }'''


class AnalysisStockPreciseDecimalsAgentFactory:
    def stream_agent_text(self, payload):
        return '''{
            "stock_code": "601096",
            "stock_name": "测试股票",
            "thought_process": "趋势转强，均线多头，量价共振",
            "self_rebuttal": "短线若放量不持续则可能回落",
            "analysis": "当前处于偏强上行结构",
            "trend": "上涨",
            "weekly_outlook": "未来一周大概率震荡上行",
            "support": 24.2,
            "resistance": 27.5,
            "recommendation": "买入",
            "hold_suggestion": "继续持有，跌破支撑减仓",
            "empty_suggestion": "回踩支撑可分批介入",
            "predicted_price": 27.598,
            "predicted_buy_price": 24.876,
            "predicted_sell_price": 23.936,
            "confidence": 0.23456,
            "risk_warning": "注意冲高回落风险"
        }'''


class InvalidJsonAgentFactory:
    def stream_agent_text(self, payload):
        return 'this is not valid json'


class TestLlmEmptyResponsePaths(unittest.TestCase):
    @patch('analysis.Database', return_value=FakeDatabase())
    @patch('analysis.Agent', return_value=EmptyAgentFactory())
    @patch('builtins.print')
    def test_analysis_stock_reports_empty_llm_response_clearly(self, mock_print, mock_agent, mock_database):
        analyzer = Analysis()

        result = analyzer.analysis_stock('601096', save_to_file=False)

        self.assertIsNone(result)
        printed = '\n'.join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
        self.assertIn('LLM 服务返回空响应', printed)

    @patch('analysis.Database', return_value=FakeDatabase())
    @patch('analysis.Agent', return_value=AnalysisStockLowConfidenceAgentFactory())
    @patch.object(Analysis, '_calculate_indicators', return_value={
        'ma5': 24.0,
        'ma20': 23.0,
        'ma60': 21.0,
        'macd_hist': 0.8,
        'rsi': 58.0,
        'volume_ratio': 1.9,
        'is_above_ma5': True,
        'is_above_ma60': True,
    })
    @patch.object(Analysis, '_is_promising', return_value=True)
    def test_analysis_stock_calibrates_confidence_above_raw_value_when_evidence_is_strong(self, mock_is_promising, mock_indicators, mock_agent, mock_database):
        analyzer = Analysis()

        result = analyzer.analysis_stock('601096', save_to_file=False)

        self.assertGreater(result['confidence'], 0.2)

    @patch('analysis.Agent', return_value=EmptyAgentFactory())
    def test_quick_analysis_returns_fallback_with_empty_llm_response_reason(self, mock_agent):
        analyzer = Analysis()

        result = analyzer.quick_analysis(
            stock_code='601096',
            stock_name='测试股票',
            current_data={'current_price': 25.0, 'change_percent': 1.2},
            indicators={'ma5': 24.5, 'ma20': 23.8, 'rsi': 55.0, 'macd_hist': 0.2, 'volume_ratio': 1.1},
            factor_158=0.8,
            holding_quantity=100,
        )

        self.assertEqual(result['recommendation'], '错误')
        self.assertIn('LLM 服务返回空响应', result['thought_process'])
        self.assertEqual(result['confidence'], 0.0)

    @patch('analysis.Agent', return_value=QuickAnalysisLowConfidenceAgentFactory())
    def test_quick_analysis_calibrates_confidence_above_raw_value_when_evidence_is_strong(self, mock_agent):
        analyzer = Analysis()

        result = analyzer.quick_analysis(
            stock_code='601096',
            stock_name='测试股票',
            current_data={'current_price': 25.0, 'change_percent': 3.2},
            indicators={
                'ma5': 24.0,
                'ma20': 23.0,
                'ma60': 21.0,
                'rsi': 58.0,
                'macd_hist': 0.8,
                'volume_ratio': 1.9,
                'is_above_ma5': True,
                'is_above_ma60': True,
            },
            factor_158=0.85,
            holding_quantity=0,
        )

        self.assertGreater(result['confidence'], 0.2)

    @patch('analysis.Agent', return_value=QuickAnalysisPreciseConfidenceAgentFactory())
    def test_quick_analysis_rounds_target_price_and_confidence_to_two_decimals(self, mock_agent):
        analyzer = Analysis()

        result = analyzer.quick_analysis(
            stock_code='601096',
            stock_name='测试股票',
            current_data={'current_price': 25.0, 'change_percent': 3.2},
            indicators={
                'ma5': 24.0,
                'ma20': 23.0,
                'ma60': 21.0,
                'rsi': 58.0,
                'macd_hist': 0.8,
                'volume_ratio': 1.9,
                'is_above_ma5': True,
                'is_above_ma60': True,
            },
            factor_158=0.85,
            holding_quantity=0,
        )

        self.assertEqual(result['target_price'], 26.88)
        self.assertEqual(result['confidence'], round(result['confidence'], 2))

    @patch('analysis.Agent', return_value=InvalidJsonAgentFactory())
    def test_quick_analysis_returns_fallback_with_zero_confidence_for_invalid_json(self, mock_agent):
        analyzer = Analysis()

        result = analyzer.quick_analysis(
            stock_code='601096',
            stock_name='测试股票',
            current_data={'current_price': 25.0, 'change_percent': 1.2},
            indicators={'ma5': 24.5, 'ma20': 23.8, 'rsi': 55.0, 'macd_hist': 0.2, 'volume_ratio': 1.1},
            factor_158=0.8,
            holding_quantity=100,
        )

        self.assertEqual(result['recommendation'], '错误')
        self.assertEqual(result['confidence'], 0.0)

    @patch('analysis.Database', return_value=FakeDatabase())
    @patch('analysis.Agent', return_value=AnalysisStockPreciseDecimalsAgentFactory())
    @patch.object(Analysis, '_calculate_indicators', return_value={
        'ma5': 24.0,
        'ma20': 23.0,
        'ma60': 21.0,
        'macd_hist': 0.8,
        'rsi': 58.0,
        'volume_ratio': 1.9,
        'is_above_ma5': True,
        'is_above_ma60': True,
    })
    @patch.object(Analysis, '_is_promising', return_value=True)
    def test_analysis_stock_rounds_predicted_prices_and_confidence_to_two_decimals(self, mock_is_promising, mock_indicators, mock_agent, mock_database):
        analyzer = Analysis()

        result = analyzer.analysis_stock('601096', save_to_file=False)

        self.assertEqual(result['predicted_buy_price'], 24.88)
        self.assertEqual(result['predicted_sell_price'], 23.94)
        self.assertEqual(result['confidence'], round(result['confidence'], 2))

    @patch('analysis.Database', return_value=FakeDatabase())
    @patch('analysis.Agent', return_value=AnalysisStockPreciseDecimalsAgentFactory())
    @patch.object(Analysis, '_calculate_indicators', return_value={
        'ma5': 24.0,
        'ma20': 23.0,
        'ma60': 21.0,
        'macd_hist': 0.8,
        'rsi': 58.0,
        'volume_ratio': 1.9,
        'is_above_ma5': True,
        'is_above_ma60': True,
    })
    @patch.object(Analysis, '_is_promising', return_value=True)
    @patch.object(Analysis, '_save_to_excel')
    @patch('builtins.print')
    def test_analysis_stock_prints_summary_with_two_decimal_prices_and_confidence(self, mock_print, mock_save, mock_is_promising, mock_indicators, mock_agent, mock_database):
        analyzer = Analysis()

        analyzer.analysis_stock('601096', save_to_file=True)

        printed = '\n'.join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
        self.assertIn('建议买入价格: 24.88', printed)
        self.assertIn('建议卖出价格: 23.94', printed)
        self.assertRegex(printed, r'信心值: \d+\.\d{2}')

    @patch('analysis.Database', return_value=FakeDatabase())
    @patch('analysis.Agent', return_value=EmptyAgentFactory())
    @patch.object(Analysis, '_calculate_indicators', return_value={
        'ma5': 9.8,
        'ma20': 10.5,
        'ma60': 12.0,
        'macd_hist': -0.7,
        'rsi': 28.0,
        'volume_ratio': 0.6,
        'is_above_ma5': False,
        'is_above_ma60': False,
    })
    @patch.object(Analysis, '_is_promising', return_value=False)
    def test_analysis_stock_prescreen_failure_builds_low_confidence_range(self, mock_is_promising, mock_indicators, mock_agent, mock_database):
        analyzer = Analysis()

        result = analyzer.analysis_stock('601096', save_to_file=False)

        self.assertNotEqual(result['confidence'], 0.1)
        self.assertGreaterEqual(result['confidence'], 0.03)
        self.assertLessEqual(result['confidence'], 0.20)

    def test_tail_analysis_parse_llm_json_result_falls_back_with_empty_response_reason(self):
        analyzer = TailAnalysis()
        item = {
            'stock_code': '601096',
            'stock_name': '测试股票',
            'current_price': 25.0,
        }

        result = analyzer._parse_llm_json_result(item, '')

        self.assertEqual(result['recommendation'], '观望')
        self.assertIn('LLM 空响应', result['risk_warning'])

    @patch('analysisflow.Agent', return_value=EmptyFlowAgentFactory())
    @patch('analysisflow.Database', return_value=FakeDatabase())
    @patch('builtins.print')
    def test_analysisflow_trader_node_marks_empty_llm_response(self, mock_print, mock_database, mock_agent):
        flow = AnalysisFlow()
        state = {
            'stock_code': '601096',
            'stock_info': {'name': '测试股票'},
            'real_time_data': {'current_price': 25.0, 'change_percent': 1.5},
            'alpha158': 0.8,
            'fundamental_analysis': '基本面良好',
            'technical_analysis': '技术面偏强',
        }

        result = flow.trader_node(state)

        self.assertEqual(result['final_result']['error'], 'LLM 空响应')
        self.assertEqual(result['final_result']['confidence'], 0.0)
        printed = '\n'.join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
        self.assertIn('LLM 空响应', printed)

    @patch('analysisflow.Agent', return_value=InvalidJsonFlowAgentFactory())
    @patch('analysisflow.Database', return_value=FakeDatabase())
    def test_analysisflow_trader_node_sets_zero_confidence_on_invalid_json(self, mock_database, mock_agent):
        flow = AnalysisFlow()
        state = {
            'stock_code': '601096',
            'stock_info': {'name': '测试股票'},
            'real_time_data': {'current_price': 25.0, 'change_percent': 1.5},
            'alpha158': 0.8,
            'fundamental_analysis': '基本面良好',
            'technical_analysis': '技术面偏强',
        }

        result = flow.trader_node(state)

        self.assertEqual(result['final_result']['error'], '解析失败')
        self.assertEqual(result['final_result']['confidence'], 0.0)

    @patch('analysisflow.Agent', return_value=FlowLowConfidenceAgentFactory())
    @patch('analysisflow.Database', return_value=FakeDatabase())
    @patch.object(AnalysisFlow, '_calculate_indicators', return_value={
        'ma5': 24.0,
        'ma10': 23.5,
        'ma20': 23.0,
        'ma60': 21.0,
        'macd_hist': 0.8,
        'volume_ratio': 1.9,
        'current_price': 25.0,
    })
    def test_analysisflow_trader_node_calibrates_confidence_above_raw_value_when_evidence_is_strong(self, mock_indicators, mock_database, mock_agent):
        flow = AnalysisFlow()
        state = {
            'stock_code': '601096',
            'stock_info': {'name': '测试股票'},
            'history_data': FakeDatabase().get_stock_history('601096', 120),
            'real_time_data': {'current_price': 25.0, 'change_percent': 1.5},
            'alpha158': 0.8,
            'fundamental_analysis': '基本面良好',
            'technical_analysis': '技术面偏强',
        }

        result = flow.trader_node(state)

        self.assertGreater(result['final_result']['confidence'], 0.2)

    @patch('analysisflow.Agent', return_value=FlowPreciseDecimalsAgentFactory())
    @patch('analysisflow.Database', return_value=FakeDatabase())
    @patch.object(AnalysisFlow, '_calculate_indicators', return_value={
        'ma5': 24.0,
        'ma10': 23.5,
        'ma20': 23.0,
        'ma60': 21.0,
        'macd_hist': 0.8,
        'volume_ratio': 1.9,
        'current_price': 25.0,
    })
    def test_analysisflow_trader_node_rounds_prices_and_confidence_to_two_decimals(self, mock_indicators, mock_database, mock_agent):
        flow = AnalysisFlow()
        state = {
            'stock_code': '601096',
            'stock_info': {'name': '测试股票'},
            'history_data': FakeDatabase().get_stock_history('601096', 120),
            'real_time_data': {'current_price': 25.0, 'change_percent': 1.5},
            'alpha158': 0.8,
            'fundamental_analysis': '基本面良好',
            'technical_analysis': '技术面偏强',
        }

        result = flow.trader_node(state)

        self.assertEqual(result['final_result']['predicted_buy_price'], 24.88)
        self.assertEqual(result['final_result']['predicted_sell_price'], 23.94)
        self.assertEqual(result['final_result']['confidence'], round(result['final_result']['confidence'], 2))

    @patch('analysisflow.Database', return_value=FakeDatabase())
    @patch.object(AnalysisFlow, '_calculate_indicators', return_value={
        'ma5': 10.0,
        'ma10': 10.8,
        'ma20': 11.5,
        'ma60': 13.0,
        'macd_hist': -0.9,
        'volume_ratio': 0.5,
        'current_price': 9.5,
        'is_above_ma5': False,
        'is_above_ma60': False,
    })
    @patch.object(AnalysisFlow, '_is_promising', return_value=False)
    @patch.object(AnalysisFlow, '_save')
    def test_analysisflow_run_prescreen_failure_builds_low_confidence_range(self, mock_save, mock_is_promising, mock_indicators, mock_database):
        flow = AnalysisFlow()

        result = flow.run('601096')

        self.assertNotEqual(result['confidence'], 0.1)
        self.assertGreaterEqual(result['confidence'], 0.03)
        self.assertLessEqual(result['confidence'], 0.20)


if __name__ == '__main__':
    unittest.main()
