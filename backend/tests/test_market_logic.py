import unittest
from datetime import datetime, timedelta, timezone

from backend.app.services.decision import TechnicalSignal, build_recommendation
from backend.app.services.indicators import compute_ema, compute_sma, compute_stop_loss
from backend.app.services.pnl import calculate_pnl
from backend.app.services.sentiment import analyze_news_sentiment
from backend.app.services.validation import PriceTick, validate_price_tick


class IndicatorTests(unittest.TestCase):
    def test_compute_sma_uses_latest_period_prices(self):
        prices = [10, 11, 12, 13, 14, 15]

        result = compute_sma(prices, period=3)

        self.assertEqual(result, 14)

    def test_compute_ema_uses_standard_smoothing_factor(self):
        prices = [10, 11, 12, 13]

        result = compute_ema(prices, period=3)

        self.assertAlmostEqual(result, 12.125, places=3)

    def test_compute_stop_loss_applies_multiplier_below_indicator(self):
        prices = [1980, 1990, 2000, 2010, 2020]

        result = compute_stop_loss(
            prices,
            indicator_type="SMA",
            period=3,
            multiplier=2,
            volatility=8,
        )

        self.assertEqual(result.indicator_value, 2010)
        self.assertEqual(result.stop_loss, 1994)


class SentimentTests(unittest.TestCase):
    def test_analyze_news_sentiment_scores_keywords_and_thresholds(self):
        articles = [
            {"title": "Gold rallies as inflation hedge demand rises", "description": ""},
            {"title": "Central bank buying supports bullion", "description": ""},
            {"title": "Strong dollar caps gains", "description": "rate hike pressure"},
        ]
        rules = {
            "positive_keywords": ["rallies", "inflation hedge", "central bank buying"],
            "negative_keywords": ["strong dollar", "rate hike"],
            "positive_threshold": 2,
            "negative_threshold": -2,
        }

        result = analyze_news_sentiment(articles, rules)

        self.assertEqual(result.label, "positive")
        self.assertEqual(result.score, 2)


class DecisionTests(unittest.TestCase):
    def test_build_recommendation_requires_golden_cross_and_positive_news(self):
        signal = TechnicalSignal(
            ma_cross="golden_cross",
            cross_strength=0.014,
            bollinger_breakout="upper",
            current_price=2055.0,
        )
        thresholds = {
            "min_cross_strength": 0.01,
            "require_bollinger_upper_breakout": True,
            "min_confidence": 0.7,
        }

        result = build_recommendation(signal, "positive", thresholds)

        self.assertEqual(result.action, "buy")
        self.assertGreaterEqual(result.confidence, 0.7)
        self.assertIn("MA golden cross", result.reasons)

    def test_build_recommendation_holds_when_sentiment_is_neutral(self):
        signal = TechnicalSignal(
            ma_cross="golden_cross",
            cross_strength=0.02,
            bollinger_breakout="upper",
            current_price=2055.0,
        )
        thresholds = {
            "min_cross_strength": 0.01,
            "require_bollinger_upper_breakout": True,
            "min_confidence": 0.7,
        }

        result = build_recommendation(signal, "neutral", thresholds)

        self.assertEqual(result.action, "hold")
        self.assertIn("news sentiment is neutral", result.risks)


class PnlTests(unittest.TestCase):
    def test_calculate_pnl_returns_amount_and_percent(self):
        result = calculate_pnl(buy_price=2000, quantity=3, current_price=2050)

        self.assertEqual(result.amount, 150)
        self.assertEqual(result.percent, 2.5)

    def test_calculate_pnl_rejects_zero_quantity(self):
        with self.assertRaises(ValueError) as context:
            calculate_pnl(buy_price=2000, quantity=0, current_price=2050)

        self.assertIn("quantity", str(context.exception))


class ValidationTests(unittest.TestCase):
    def test_validate_price_tick_accepts_reasonable_recent_price(self):
        tick = PriceTick(
            symbol="XAUUSD",
            price=2335.42,
            timestamp=datetime.now(timezone.utc),
            source="fixture",
        )

        result = validate_price_tick(tick, min_price=500, max_price=5000, max_delay_seconds=5)

        self.assertEqual(result.price, 2335.42)

    def test_validate_price_tick_rejects_stale_timestamp(self):
        tick = PriceTick(
            symbol="XAUUSD",
            price=2335.42,
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=9),
            source="fixture",
        )

        with self.assertRaises(ValueError) as context:
            validate_price_tick(tick, min_price=500, max_price=5000, max_delay_seconds=5)

        self.assertIn("stale", str(context.exception))


if __name__ == "__main__":
    unittest.main()
