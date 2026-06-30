import unittest
import ssl
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from backend.app.core import logging as app_logging
from backend.app.services.decision import TechnicalSignal, build_recommendation
from backend.app.services.display_price import convert_usd_oz_to_cny_g
from backend.app.services.indicators import compute_ema, compute_sma, compute_stop_loss
from backend.app.services.pnl import calculate_pnl
from backend.app.services.sentiment import analyze_news_sentiment
from backend.app.services.validation import PriceTick, validate_price_tick
from backend.app.api import _convert_price_for_display, _max_data_delay_seconds
from backend.app.services.data_provider import MarketDataError, PriceProvider, _httpx_verify_option, _parse_response_payload
from backend.app.services.klines import get_klines


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


class LoggingTests(unittest.TestCase):
    def test_external_http_client_logs_do_not_emit_info_urls(self):
        self.assertIsNotNone(app_logging.logger)
        self.assertGreaterEqual(logging.getLogger("httpx").level, logging.WARNING)
        self.assertGreaterEqual(logging.getLogger("httpcore").level, logging.WARNING)


class DisplayPriceTests(unittest.TestCase):
    def test_convert_usd_oz_to_cny_g_uses_fx_and_troy_ounce(self):
        result = convert_usd_oz_to_cny_g(
            price_usd_oz=2340,
            usd_cny_rate=7.25,
            troy_ounce_grams=31.1034768,
        )

        self.assertAlmostEqual(result, 545.44, places=2)

    def test_convert_current_reference_gold_price_to_cny_g(self):
        result = convert_usd_oz_to_cny_g(
            price_usd_oz=4018.77,
            usd_cny_rate=6.808596,
            troy_ounce_grams=31.1034768,
        )

        self.assertAlmostEqual(result, 879.71, places=2)

    def test_cny_g_source_is_not_converted_again_for_display(self):
        result = _convert_price_for_display(
            price=883.7,
            display_config={"currency": "CNY", "unit": "g"},
            source_config={"currency": "CNY", "unit": "g"},
        )

        self.assertEqual(result, 883.7)

    def test_source_can_override_max_data_delay(self):
        result = _max_data_delay_seconds(
            realtime_config={"max_data_delay_seconds": 5},
            source_config={"max_data_delay_seconds": 900},
        )

        self.assertEqual(result, 900)


class PriceProviderTests(unittest.TestCase):
    def _provider_config(self) -> dict:
        return {
            "data_sources": {
                "active": "demo",
                "price": {
                    "demo": {
                        "type": "demo",
                        "symbol": "XAUUSD",
                        "base_price": 800,
                        "volatility": 0,
                    },
                },
            },
            "retry": {"max_attempts": 1},
        }

    def test_parse_jsonp_market_payload(self):
        payload = _parse_response_payload(
            'callback({"qt":{"dm":"AU9999","p":883.7,"utime":1782459826}})',
            "jsonp",
        )

        self.assertEqual(payload["qt"]["dm"], "AU9999")
        self.assertEqual(payload["qt"]["p"], 883.7)

    def test_parse_icbc_chart_market_payload_extracts_latest_point(self):
        payload = _parse_response_payload(
            '{"datetime":"2026-06-29 14:23:31","prodcode":"130060000043","chartArrayStr":"[[\\"141012\\",887.65],[\\"141840\\",886.64]]"}',
            "icbc_chart",
        )

        self.assertEqual(payload["latest"]["price"], 886.64)
        self.assertEqual(payload["latest"]["timestamp"], "2026-06-29T14:18:40+08:00")

    def test_parse_icbc_accrual_payload_extracts_active_price(self):
        payload = _parse_response_payload(
            '{"sysdate":"2026-06-29 15:10:45","TranErrorCode":"","rf":[{"goldTypeNo":"JC001","RegPrice":"887.50","Active":"0","ProductName":"积存金","proCode":"080020000521","Reg":"1","HighPrice":"890.21","RegDate":"2026-06-29","ActivePrice":"886.25","SellPrice":"886.25","ActiveDate":"2026-06-29","LowPrice":"882.35"}],"TranErrorDisplayMsg":""}',
            "icbc_accrual",
        )

        self.assertEqual(payload["latest"]["price"], 886.25)
        self.assertEqual(payload["latest"]["timestamp"], "2026-06-29T15:10:45+08:00")
        self.assertEqual(payload["latest"]["product_name"], "积存金")
        self.assertEqual(payload["latest"]["sell_price"], 886.25)

    def test_parse_jdjygold_payload_extracts_zheshang_accrual_price(self):
        payload = _parse_response_payload(
            '{"resultData":{"datas":{"upAndDownRate":"-0.37%","productSku":"1961543816","demode":false,"priceNum":"f3bb4265-8a06-4cfa-a0b4-327e57206a1c","price":"886.56","yesterdayPrice":"889.85","upAndDownAmt":"-3.29","time":"1782717342000","id":50220984},"status":"SUCCESS"},"success":true,"resultCode":0,"resultMsg":"成功","channelEncrypt":0}',
            "jdjygold_latest",
        )

        self.assertEqual(payload["latest"]["price"], 886.56)
        self.assertEqual(payload["latest"]["timestamp"], 1782717342000)
        self.assertEqual(payload["latest"]["product_sku"], "1961543816")
        self.assertEqual(payload["latest"]["yesterday_price"], 889.85)

    def test_legacy_tls_source_uses_ssl_context_for_httpx(self):
        verify_option = _httpx_verify_option({"legacy_tls": True})

        self.assertIsInstance(verify_option, ssl.SSLContext)
        self.assertTrue(verify_option.options & getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4))

    def test_regular_source_uses_default_httpx_verification(self):
        verify_option = _httpx_verify_option({})

        self.assertIs(verify_option, True)

    def test_source_config_selects_named_source(self):
        provider = PriceProvider(
            {
                "data_sources": {
                    "active": "yahoo_finance",
                    "fallback": "demo",
                    "price": {
                        "yahoo_finance": {"type": "http", "name": "Yahoo"},
                        "goldpriceapi": {"type": "http", "name": "GoldAPI"},
                        "demo": {"type": "demo"},
                    },
                }
            }
        )

        result = provider.source_config("goldpriceapi")

        self.assertEqual(result["name"], "GoldAPI")

    def test_source_config_rejects_unknown_source(self):
        provider = PriceProvider(
            {
                "data_sources": {
                    "active": "demo",
                    "price": {"demo": {"type": "demo"}},
                }
            }
        )

        with self.assertRaises(MarketDataError) as context:
            provider.source_config("missing_source")

        self.assertIn("unknown price source", str(context.exception))

    def test_price_history_is_kept_per_source(self):
        provider = PriceProvider(
            {
                "data_sources": {
                    "active": "primary_demo",
                    "price": {
                        "primary_demo": {
                            "type": "demo",
                            "symbol": "XAUUSD",
                            "base_price": 4000,
                            "volatility": 0,
                        },
                        "secondary_demo": {
                            "type": "demo",
                            "symbol": "XAUUSD",
                            "base_price": 4100,
                            "volatility": 0,
                        },
                    },
                },
                "retry": {"max_attempts": 1},
            }
        )

        asyncio.run(provider.latest_tick("primary_demo"))
        asyncio.run(provider.latest_tick("secondary_demo"))

        self.assertAlmostEqual(provider.price_history("primary_demo")[0], 4000.18, places=2)
        self.assertAlmostEqual(provider.price_history("secondary_demo")[0], 4100.36, places=2)

    def test_today_range_keeps_extrema_after_rolling_history_drops_old_price(self):
        provider = PriceProvider(self._provider_config())
        morning = datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc)

        provider._append_price("demo", 900.0, morning)
        for index in range(241):
            provider._append_price("demo", 800.0 + (index % 3), morning + timedelta(minutes=index + 1))

        history = provider.price_history("demo")
        self.assertNotIn(900.0, history)
        self.assertEqual(provider.today_range("demo")["high"], 900.0)
        self.assertEqual(provider.today_range("demo")["low"], 800.0)

    def test_today_range_uses_source_reported_day_high_and_low(self):
        provider = PriceProvider(self._provider_config())
        now = datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc)

        provider._append_price("demo", 866.64, now, day_low=865.39, day_high=881.56)

        self.assertEqual(provider.today_range("demo")["low"], 865.39)
        self.assertEqual(provider.today_range("demo")["high"], 881.56)

    def test_active_source_falls_back_to_demo_when_configured(self):
        provider = PriceProvider(
            {
                "data_sources": {
                    "active": "yahoo_finance",
                    "fallback": "demo",
                    "price": {
                        "yahoo_finance": {"type": "http"},
                        "demo": {
                            "type": "demo",
                            "symbol": "XAUUSD",
                            "base_price": 4018.77,
                            "volatility": 0,
                        },
                    },
                }
            }
        )

        result = provider.fallback_source_config()

        self.assertEqual(result["type"], "demo")
        self.assertEqual(result["base_price"], 4018.77)

    def test_source_history_klines_use_selected_native_cny_source(self):
        provider = PriceProvider(
            {
                "data_sources": {
                    "active": "jdjygold_zheshang",
                    "price": {
                        "jdjygold_zheshang": {
                            "type": "demo",
                            "name": "浙商银行积存金",
                            "symbol": "1961543816",
                            "base_price": 886.25,
                            "volatility": 0,
                            "currency": "CNY",
                            "unit": "g",
                            "kline_mode": "history",
                        },
                    },
                },
                "retry": {"max_attempts": 1},
            }
        )

        payload = asyncio.run(get_klines("1min", source="jdjygold_zheshang", provider=provider))

        self.assertEqual(payload["source"], "jdjygold_zheshang")
        self.assertEqual(payload["display_unit"], "CNY/g")
        self.assertGreaterEqual(payload["count"], 25)
        self.assertAlmostEqual(payload["candles"][-1]["close"], 886.43, places=2)


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
        self.assertIn("均线金叉", result.reasons)

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
        self.assertIn("新闻情绪未偏正面", result.risks)


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
