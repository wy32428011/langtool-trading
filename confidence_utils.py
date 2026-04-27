"""共享的 confidence 规范化与规则校准工具。"""

from __future__ import annotations

import math
from typing import Any


LOW_CONFIDENCE_FLOOR = 0.03
LOW_CONFIDENCE_CEILING = 0.20
TRUE_LIKE_VALUES = {"true", "1", "yes", "y", "on"}
FALSE_LIKE_VALUES = {"false", "0", "no", "n", "off", ""}


def _safe_float(value: Any, default: float = 0.0) -> float:
    """将输入尽量转换为浮点数，失败或异常值时返回默认值。"""
    try:
        if value is None:
            return float(default)
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    if math.isnan(number):
        return float(default)
    if math.isinf(number):
        return number
    return number


def _clamp(value: Any, minimum: float = 0.0, maximum: float = 1.0) -> float:
    """将数值压缩到给定区间。"""
    number = _safe_float(value, minimum)
    if math.isnan(number):
        return minimum
    if number < minimum:
        return minimum
    if number > maximum:
        return maximum
    return number


def _parse_bool(flag: Any) -> bool | None:
    """将常见布尔输入解析为真/假/未知。"""
    if flag is None:
        return None
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, (int, float)) and not isinstance(flag, bool):
        number = _safe_float(flag, default=float("nan"))
        if math.isnan(number):
            return None
        if number == 1:
            return True
        if number == 0:
            return False
        return None
    if isinstance(flag, str):
        normalized_flag = flag.strip().lower()
        if normalized_flag in TRUE_LIKE_VALUES:
            return True
        if normalized_flag in FALSE_LIKE_VALUES:
            return False
        return None
    return None


def _score_from_bool(flag: Any, positive: float, negative: float) -> float:
    """将布尔型信号映射为固定分值，未知值走中性。"""
    parsed_flag = _parse_bool(flag)
    if parsed_flag is True:
        return positive
    if parsed_flag is False:
        return negative
    return 0.0


def _score_from_price_vs_ma(current_price: float, moving_average: float, positive: float, negative: float) -> float:
    """根据价格是否站上均线给出分值。"""
    if moving_average <= 0:
        return 0.0
    return positive if current_price >= moving_average else negative


def _score_from_volume_ratio(volume_ratio: float) -> float:
    """根据量比强弱给出轻量分值。"""
    if volume_ratio >= 1.8:
        return 0.14
    if volume_ratio >= 1.2:
        return 0.08
    if volume_ratio >= 0.9:
        return 0.0
    if volume_ratio >= 0.7:
        return -0.06
    return -0.12


def _score_from_macd_hist(macd_hist: float) -> float:
    """根据 MACD 柱体方向给出分值。"""
    if macd_hist >= 0.6:
        return 0.12
    if macd_hist > 0:
        return 0.06
    if macd_hist <= -0.6:
        return -0.12
    if macd_hist < 0:
        return -0.06
    return 0.0


def _score_from_rsi(rsi: float) -> float:
    """根据 RSI 所处区间给出分值。"""
    if 45 <= rsi <= 65:
        return 0.10
    if 35 <= rsi < 45 or 65 < rsi <= 72:
        return 0.03
    if rsi < 25:
        return -0.04
    if rsi > 78:
        return -0.12
    return -0.03


def _score_from_factor_158(factor_158: float) -> float:
    """根据 158 因子强弱给出分值。"""
    return (factor_158 - 0.5) * 0.24


def _score_from_trend_label(trend_value: Any) -> float:
    """根据中文趋势枚举给出分值。"""
    trend_label = str(trend_value or "").strip()
    if trend_label == "向上":
        return 0.10
    if trend_label == "向下":
        return -0.10
    if trend_label == "走平":
        return 0.02
    return 0.0


def normalize_confidence(value: Any, default: float = 0.0) -> float:
    """将 confidence 规范化到 [0, 1] 区间。"""
    if value is None:
        return _clamp(default)
    return _clamp(_safe_float(value, default))


def calibrate_confidence(raw_confidence: Any, evidence_score: Any) -> float:
    """使用规则证据对原始置信度做轻量校准。"""
    base_confidence = normalize_confidence(raw_confidence)
    normalized_evidence = normalize_confidence(evidence_score, default=0.5)
    adjustment = (normalized_evidence - 0.5) * 0.45
    calibrated_confidence = base_confidence + adjustment
    return normalize_confidence(calibrated_confidence)


def compute_main_evidence_score(indicators: dict | None, factor_158: Any, current_data: dict | None) -> float:
    """计算主链路规则证据分。"""
    indicators = indicators or {}
    current_data = current_data or {}
    current_price = _safe_float(current_data.get("current_price"))
    ma5 = _safe_float(indicators.get("ma5"))
    ma20 = _safe_float(indicators.get("ma20"))
    ma60 = _safe_float(indicators.get("ma60"))
    macd_hist = _safe_float(indicators.get("macd_hist"))
    rsi = _safe_float(indicators.get("rsi"), 50.0)
    volume_ratio = _safe_float(indicators.get("volume_ratio"), 1.0)
    factor_score = normalize_confidence(factor_158, default=0.5)

    score = 0.5
    score += _score_from_bool(indicators.get("is_above_ma5"), 0.08, -0.08)
    score += _score_from_bool(indicators.get("is_above_ma60"), 0.12, -0.12)
    score += _score_from_price_vs_ma(current_price, ma5, 0.04, -0.04)
    score += _score_from_price_vs_ma(current_price, ma60, 0.06, -0.06)
    score += 0.08 if ma5 >= ma20 > 0 else -0.08
    score += 0.10 if ma20 >= ma60 > 0 else -0.10
    score += _score_from_macd_hist(macd_hist)
    score += _score_from_rsi(rsi)
    score += _score_from_volume_ratio(volume_ratio)
    score += _score_from_factor_158(factor_score)
    return normalize_confidence(score)


def compute_2560_evidence_score(indicators: dict | None, current_data: dict | None) -> float:
    """计算 2560 策略链路规则证据分。"""
    indicators = indicators or {}
    current_data = current_data or {}
    current_price = _safe_float(current_data.get("current_price"))
    ma25 = _safe_float(indicators.get("ma25"))
    ma60 = _safe_float(indicators.get("ma60"))
    ma25_trend = indicators.get("ma25_trend")
    ma60_trend = indicators.get("ma60_trend")
    volume_ratio = _safe_float(indicators.get("volume_ratio"), 1.0)

    score = 0.5
    score += _score_from_bool(indicators.get("is_above_ma25"), 0.12, -0.12)
    score += _score_from_bool(indicators.get("is_above_ma60"), 0.14, -0.14)
    score += _score_from_price_vs_ma(current_price, ma25, 0.05, -0.05)
    score += _score_from_price_vs_ma(current_price, ma60, 0.07, -0.07)
    score += 0.08 if ma25 >= ma60 > 0 else -0.08
    score += _score_from_trend_label(ma25_trend)
    score += _score_from_trend_label(ma60_trend)
    score += _score_from_volume_ratio(volume_ratio)
    return normalize_confidence(score)


def build_low_confidence_from_prescreen(
    indicators: dict | None,
    factor_158: Any = None,
    current_data: dict | None = None,
    failure_reasons: list[str] | tuple[str, ...] | None = None,
) -> float:
    """根据预筛失败强度构造低分区间内的置信度。"""
    evidence_score = compute_main_evidence_score(indicators, factor_158, current_data)
    reasons = failure_reasons or []
    penalty = 0.14
    penalty += min(len(reasons), 4) * 0.04
    penalty += (1.0 - evidence_score) * 0.18

    indicators = indicators or {}
    current_data = current_data or {}
    current_price = _safe_float(current_data.get("current_price"))
    ma60 = _safe_float(indicators.get("ma60"))
    macd_hist = _safe_float(indicators.get("macd_hist"))
    volume_ratio = _safe_float(indicators.get("volume_ratio"), 1.0)
    factor_score = normalize_confidence(factor_158, default=0.5)

    if _parse_bool(indicators.get("is_above_ma5")) is False:
        penalty += 0.04
    if _parse_bool(indicators.get("is_above_ma60")) is False:
        penalty += 0.05
    if ma60 > 0 and current_price < ma60:
        penalty += 0.04
    if macd_hist < 0:
        penalty += min(abs(macd_hist) * 0.05, 0.05)
    if volume_ratio < 0.8:
        penalty += 0.03
    if factor_score < 0.3:
        penalty += 0.04

    low_confidence = LOW_CONFIDENCE_CEILING - penalty * 0.5
    return _clamp(low_confidence, LOW_CONFIDENCE_FLOOR, LOW_CONFIDENCE_CEILING)
