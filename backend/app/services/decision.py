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
        reasons.append("MA golden cross")
    else:
        risks.append("MA golden cross threshold not met")

    if not require_upper_breakout or signal.bollinger_breakout == "upper":
        score += 0.25
        reasons.append("price broke above Bollinger upper band")
    else:
        risks.append("price has not broken above Bollinger upper band")

    if sentiment_label == "positive":
        score += 0.35
        reasons.append("news sentiment is positive")
    else:
        risks.append(f"news sentiment is {sentiment_label}")

    confidence = round(min(score, 1.0), 3)
    action = "buy" if confidence >= min_confidence and not risks else "hold"
    return Recommendation(action=action, confidence=confidence, reasons=reasons, risks=risks)
