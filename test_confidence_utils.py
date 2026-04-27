import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from confidence_utils import (
    build_low_confidence_from_prescreen,
    calibrate_confidence,
    compute_2560_evidence_score,
    compute_main_evidence_score,
    normalize_confidence,
)


class NormalizeConfidenceTestCase(unittest.TestCase):
    """验证基础置信度规范化行为。"""

    def test_normalize_confidence_handles_none(self):
        """空值应回落到默认值。"""
        self.assertEqual(normalize_confidence(None), 0.0)

    def test_normalize_confidence_parses_string_number(self):
        """字符串数字应被转换为浮点数。"""
        self.assertEqual(normalize_confidence("0.8"), 0.8)

    def test_normalize_confidence_clamps_upper_bound(self):
        """大于 1 的值应被压到上限。"""
        self.assertEqual(normalize_confidence(1.5), 1.0)

    def test_normalize_confidence_clamps_lower_bound(self):
        """小于 0 的值应被压到下限。"""
        self.assertEqual(normalize_confidence(-0.2), 0.0)

    def test_normalize_confidence_handles_nan_and_inf_safely(self):
        """异常浮点值应安全回退或钳制。"""
        self.assertEqual(normalize_confidence(float("nan"), default=0.4), 0.4)
        self.assertEqual(normalize_confidence(float("inf")), 1.0)
        self.assertEqual(normalize_confidence(float("-inf")), 0.0)


class CalibrateConfidenceTestCase(unittest.TestCase):
    """验证规则证据对原始置信度的校准方向。"""

    def test_calibrate_confidence_increases_with_strong_evidence(self):
        """强规则证据应抬升置信度。"""
        self.assertGreater(calibrate_confidence(0.55, 0.85), 0.55)

    def test_calibrate_confidence_decreases_with_weak_evidence(self):
        """弱规则证据应压低置信度。"""
        self.assertLess(calibrate_confidence(0.85, 0.30), 0.85)


class EvidenceAndPrescreenTestCase(unittest.TestCase):
    """验证证据分与预筛低置信度构造。"""

    def test_main_evidence_score_stays_in_range_and_reflects_inputs(self):
        """主链路证据分应位于区间内且不是固定值。"""
        strong_score = compute_main_evidence_score(
            indicators={
                "ma5": 10.0,
                "ma20": 9.5,
                "ma60": 9.0,
                "macd_hist": 0.8,
                "rsi": 58.0,
                "volume_ratio": 1.8,
                "is_above_ma5": True,
                "is_above_ma60": True,
            },
            factor_158=0.9,
            current_data={"current_price": 10.2},
        )
        weak_score = compute_main_evidence_score(
            indicators={
                "ma5": 9.0,
                "ma20": 9.4,
                "ma60": 10.0,
                "macd_hist": -0.6,
                "rsi": 78.0,
                "volume_ratio": 0.7,
                "is_above_ma5": False,
                "is_above_ma60": False,
            },
            factor_158=0.1,
            current_data={"current_price": 8.9},
        )
        self.assertGreaterEqual(strong_score, 0.0)
        self.assertLessEqual(strong_score, 1.0)
        self.assertGreaterEqual(weak_score, 0.0)
        self.assertLessEqual(weak_score, 1.0)
        self.assertGreater(strong_score, weak_score)

    def test_string_booleans_do_not_get_misclassified(self):
        """字符串布尔应按语义解析，不应被 bool("False") 误判。"""
        bullish_score = compute_main_evidence_score(
            indicators={
                "ma5": 10.0,
                "ma20": 9.8,
                "ma60": 9.6,
                "macd_hist": 0.2,
                "rsi": 55.0,
                "volume_ratio": 1.1,
                "is_above_ma5": "true",
                "is_above_ma60": "1",
            },
            factor_158=0.6,
            current_data={"current_price": 10.1},
        )
        bearish_score = compute_main_evidence_score(
            indicators={
                "ma5": 10.0,
                "ma20": 9.8,
                "ma60": 9.6,
                "macd_hist": 0.2,
                "rsi": 55.0,
                "volume_ratio": 1.1,
                "is_above_ma5": "False",
                "is_above_ma60": "0",
            },
            factor_158=0.6,
            current_data={"current_price": 10.1},
        )
        self.assertGreater(bullish_score, bearish_score)

    def test_missing_bool_fields_stay_neutral_in_evidence_and_prescreen(self):
        """缺失布尔字段时不应被强制判为空头。"""
        base_indicators = {
            "ma5": 10.0,
            "ma20": 9.9,
            "ma60": 9.8,
            "macd_hist": 0.05,
            "rsi": 50.0,
            "volume_ratio": 0.95,
        }
        neutral_score = compute_main_evidence_score(
            indicators=dict(base_indicators),
            factor_158=0.55,
            current_data={"current_price": 10.0},
        )
        bearish_score = compute_main_evidence_score(
            indicators={**base_indicators, "is_above_ma5": False, "is_above_ma60": False},
            factor_158=0.55,
            current_data={"current_price": 10.0},
        )
        neutral_low_confidence = build_low_confidence_from_prescreen(
            indicators=dict(base_indicators),
            factor_158=0.55,
            current_data={"current_price": 10.0},
            failure_reasons=["量比略不足"],
        )
        explicit_bearish_low_confidence = build_low_confidence_from_prescreen(
            indicators={**base_indicators, "is_above_ma5": False, "is_above_ma60": False},
            factor_158=0.55,
            current_data={"current_price": 10.0},
            failure_reasons=["量比略不足"],
        )
        self.assertGreater(neutral_score, bearish_score)
        self.assertGreater(neutral_low_confidence, explicit_bearish_low_confidence)

    def test_build_low_confidence_from_prescreen_varies_by_signal_strength(self):
        """预筛失败的低置信度应随空头强弱变化，且不应固定写死。"""
        harsher_confidence = build_low_confidence_from_prescreen(
            indicators={
                "ma5": 9.0,
                "ma20": 9.4,
                "ma60": 10.0,
                "macd_hist": -0.8,
                "rsi": 81.0,
                "volume_ratio": 0.6,
                "is_above_ma5": False,
                "is_above_ma60": False,
            },
            factor_158=0.05,
            current_data={"current_price": 8.8},
            failure_reasons=["跌破均线", "量能不足", "因子偏弱"],
        )
        borderline_confidence = build_low_confidence_from_prescreen(
            indicators={
                "ma5": 10.0,
                "ma20": 9.9,
                "ma60": 9.8,
                "macd_hist": 0.05,
                "rsi": 49.0,
                "volume_ratio": 0.95,
                "is_above_ma5": True,
                "is_above_ma60": True,
            },
            factor_158=0.55,
            current_data={"current_price": 10.0},
            failure_reasons=["量比略不足"],
        )
        self.assertGreaterEqual(harsher_confidence, 0.03)
        self.assertLessEqual(harsher_confidence, 0.20)
        self.assertGreaterEqual(borderline_confidence, 0.03)
        self.assertLessEqual(borderline_confidence, 0.20)
        self.assertLess(harsher_confidence, borderline_confidence)
        self.assertNotEqual(harsher_confidence, 0.1)
        self.assertNotEqual(borderline_confidence, 0.1)

    def test_2560_evidence_score_stays_in_range(self):
        """2560 证据分应位于区间内且具备区分度。"""
        strong_score = compute_2560_evidence_score(
            indicators={
                "ma25": 10.2,
                "ma60": 9.8,
                "ma25_trend": "向上",
                "ma60_trend": "向上",
                "is_above_ma25": True,
                "is_above_ma60": True,
                "volume_ratio": 1.6,
            },
            current_data={"current_price": 10.5},
        )
        weak_score = compute_2560_evidence_score(
            indicators={
                "ma25": 9.8,
                "ma60": 10.0,
                "ma25_trend": "向下",
                "ma60_trend": "向下",
                "is_above_ma25": False,
                "is_above_ma60": False,
                "volume_ratio": 0.7,
            },
            current_data={"current_price": 9.5},
        )
        self.assertGreaterEqual(strong_score, 0.0)
        self.assertLessEqual(strong_score, 1.0)
        self.assertGreaterEqual(weak_score, 0.0)
        self.assertLessEqual(weak_score, 1.0)
        self.assertGreater(strong_score, weak_score)

    def test_2560_unknown_trend_label_is_neutral(self):
        """未知趋势标签应按中性处理，不应误加多空分。"""
        neutral_score = compute_2560_evidence_score(
            indicators={
                "ma25": 10.0,
                "ma60": 9.8,
                "ma25_trend": "未知",
                "ma60_trend": "走平",
                "is_above_ma25": True,
                "is_above_ma60": True,
                "volume_ratio": 1.0,
            },
            current_data={"current_price": 10.1},
        )
        bullish_score = compute_2560_evidence_score(
            indicators={
                "ma25": 10.0,
                "ma60": 9.8,
                "ma25_trend": "向上",
                "ma60_trend": "走平",
                "is_above_ma25": True,
                "is_above_ma60": True,
                "volume_ratio": 1.0,
            },
            current_data={"current_price": 10.1},
        )
        self.assertLess(neutral_score, bullish_score)


if __name__ == "__main__":
    unittest.main()
