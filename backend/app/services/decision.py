from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class TechnicalSignal:
    ma_cross: str
    cross_strength: float
    bollinger_breakout: str
    current_price: float


@dataclass(frozen=True)
class Recommendation:
    action: str
    confidence: float
    reasons: list[str]
    risks: list[str]


def build_recommendation(
    signal: TechnicalSignal,
    sentiment_label: str,
    thresholds: Mapping[str, object],
) -> Recommendation:
    min_cross_strength = float(thresholds.get("min_cross_strength", 0.01))
    require_upper_breakout = bool(thresholds.get("require_bollinger_upper_breakout", True))
    min_confidence = float(thresholds.get("min_confidence", 0.7))

    reasons: list[str] = []
    risks: list[str] = []
    score = 0.0

    if signal.ma_cross == "golden_cross" and signal.cross_strength >= min_cross_strength:
        score += 0.4
        reasons.append("均线金叉")
    else:
        risks.append("均线金叉未达阈值")

    if not require_upper_breakout or signal.bollinger_breakout == "upper":
        score += 0.25
        reasons.append("价格突破布林带上轨")
    else:
        risks.append("价格未突破布林带上轨")

    if sentiment_label == "positive":
        score += 0.35
        reasons.append("新闻情绪偏正面")
    else:
        risks.append("新闻情绪未偏正面")

    confidence = round(min(score, 1.0), 3)
    action = "buy" if confidence >= min_confidence and not risks else "hold"
    return Recommendation(action=action, confidence=confidence, reasons=reasons, risks=risks)
