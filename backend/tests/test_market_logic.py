import unittest
import ssl
import asyncio
import logging
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend.app.core import logging as app_logging
from backend.app.core.config import load_config
from backend.app.services.decision import TechnicalSignal, build_recommendation
from backend.app.services.display_price import convert_usd_oz_to_cny_g
from backend.app.services.indicators import compute_ema, compute_sma, compute_stop_loss
from backend.app.services.pnl import calculate_pnl
from backend.app.services.sentiment import analyze_news_sentiment
from backend.app.services.validation import PriceTick, validate_price_tick
from backend.app.api import (
    _capture_kline_tick_for_source,
    _convert_price_for_display,
    _history_kline_source_keys,
    _max_data_delay_seconds,
    _public_data_sources,
    market_monthly_review,
    market_monthly_reviews,
)
from backend.app.services import klines as klines_service
from backend.app.services.data_provider import MarketDataError, PriceProvider, _httpx_verify_option, _parse_response_payload
from backend.app.services.klines import get_klines
from backend.app.services.kline_store import KlineStore


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


class ConfigTests(unittest.TestCase):
    def test_hongyun_gold_reference_source_is_publicly_available(self):
        config = load_config()

        source_config = config["data_sources"]["price"]["hongyun_gold_reference"]
        public_options = {
            option["key"]: option
            for option in _public_data_sources(config)["options"]
        }

        self.assertEqual(source_config["label"], "民生银行积存金")
        self.assertEqual(source_config["name"], "民生银行积存金")
        self.assertEqual(source_config["endpoint"], "https://api.jdjygold.com/gw/generic/hj/h5/m/latestPrice")
        self.assertEqual(source_config["response_format"], "jdjygold_latest")
        self.assertEqual(source_config["day_range_endpoint"], "https://api.jdjygold.com/gw/generic/hj/h5/m/todayPrices")
        self.assertEqual(source_config["kline_mode"], "intraday")
        self.assertIn("京东金融民生银行积存金公开源", source_config["description"])
        self.assertIn("hongyun_gold_reference", public_options)
        self.assertFalse(public_options["hongyun_gold_reference"]["requires_api_key"])

    def test_zheshang_source_configures_week_history_backfill(self):
        config = load_config()

        source_config = config["data_sources"]["price"]["jdjygold_zheshang"]

        self.assertEqual(source_config["history_endpoint"], "https://api.jdjygold.com/gw/generic/hj/h5/m/historyPrices")
        self.assertEqual(source_config["history_response_format"], "jdjygold_history_prices")
        self.assertEqual(source_config["history_params"], {"period": "w"})

    def test_three_commodity_monthly_reviews_are_configured(self):
        config = load_config()
        commodities = config["market_review"]["commodities"]

        self.assertEqual(list(commodities), ["gold", "silver", "platinum"])
        self.assertEqual(commodities["gold"]["label"], "黄金30日行情")
        self.assertEqual(commodities["gold"]["seed_file"], "黄金30日行情.md")
        self.assertEqual(commodities["silver"]["label"], "白银30日行情")
        self.assertEqual(commodities["silver"]["seed_file"], "白银30日行情.md")
        self.assertEqual(commodities["silver"]["unit"], "kg")
        self.assertEqual(commodities["platinum"]["label"], "铂金30日行情")
        self.assertEqual(commodities["platinum"]["seed_file"], "铂金30日行情.md")


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

    def test_parse_jdjygold_today_prices_payload_extracts_day_range(self):
        payload = _parse_response_payload(
            '{"resultData":{"datas":[{"name":"2026-06-30 00:00:00","value":["2026-06-30 00:00:00","880.00"]},{"name":"2026-06-30 09:00:00","value":["2026-06-30 09:00:00","863.05"]},{"name":"2026-06-30 17:00:00","value":["2026-06-30 17:00:00","876.84"]}],"status":"SUCCESS"},"success":true,"resultCode":0,"resultMsg":"成功","channelEncrypt":0}',
            "jdjygold_today_prices",
        )

        self.assertEqual(payload["latest"]["low_price"], 863.05)
        self.assertEqual(payload["latest"]["high_price"], 880.0)
        self.assertEqual(payload["latest"]["candles"][0], {
            "time": "2026-06-30T00:00:00",
            "open": 880.0,
            "high": 880.0,
            "low": 880.0,
            "close": 880.0,
        })
        self.assertEqual(payload["latest"]["candles"][-1]["time"], "2026-06-30T17:00:00")

    def test_parse_jdjygold_history_prices_payload_extracts_week_points(self):
        payload = _parse_response_payload(
            '{"resultData":{"datas":[{"demode":false,"price":"890.5200","time":"1782230400000"},{"demode":false,"price":"867.1100","time":"1782835200000"}],"status":"SUCCESS"},"success":true,"resultCode":0,"resultMsg":"成功"}',
            "jdjygold_history_prices",
        )

        self.assertEqual(payload["latest"]["candles"], [
            {
                "time": "2026-06-24T00:00:00",
                "open": 890.52,
                "high": 890.52,
                "low": 890.52,
                "close": 890.52,
            },
            {
                "time": "2026-07-01T00:00:00",
                "open": 867.11,
                "high": 867.11,
                "low": 867.11,
                "close": 867.11,
            },
        ])

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

    def test_today_range_can_require_source_reported_day_high_and_low(self):
        provider = PriceProvider(self._provider_config())
        now = datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc)

        provider._append_price("demo", 866.64, now, include_observed_range=False)

        self.assertIsNone(provider.today_range("demo"))

        provider._append_price(
            "demo",
            866.64,
            now,
            day_low=865.39,
            day_high=881.56,
            include_observed_range=False,
        )

        self.assertEqual(provider.today_range("demo")["low"], 865.39)
        self.assertEqual(provider.today_range("demo")["high"], 881.56)

    def test_http_fetch_reads_configured_day_range_before_client_closes(self):
        class Response:
            def __init__(self, text: str) -> None:
                self.text = text

            def raise_for_status(self) -> None:
                return None

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs) -> None:
                self.closed = False

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args) -> None:
                self.closed = True

            async def get(self, *args, **kwargs):
                return Response(
                    '{"resultData":{"datas":{"price":"876.56","time":"1782717342000"},"status":"SUCCESS"},"success":true}'
                )

            async def request(self, *args, **kwargs):
                if self.closed:
                    raise RuntimeError("client closed")
                return Response(
                    '{"resultData":{"datas":[{"value":["2026-06-30 09:00:00","863.05"]},{"value":["2026-06-30 17:00:00","880.83"]}],"status":"SUCCESS"},"success":true}'
                )

        provider = PriceProvider(self._provider_config())
        source_config = {
            "type": "http",
            "endpoint": "https://example.test/latest",
            "response_format": "jdjygold_latest",
            "json_paths": {"price": "latest.price", "timestamp": "latest.timestamp"},
            "day_range_endpoint": "https://example.test/today",
            "day_range_method": "post",
            "day_range_response_format": "jdjygold_today_prices",
        }

        with patch("backend.app.services.data_provider.httpx.AsyncClient", FakeAsyncClient):
            tick = asyncio.run(provider._fetch_http(source_config))

        self.assertEqual(tick.day_low, 863.05)
        self.assertEqual(tick.day_high, 880.83)

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

    def test_source_history_klines_use_selected_native_cny_source_from_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = KlineStore(Path(tmp) / "klines.sqlite")
            store.upsert_bar(
                "jdjygold_zheshang",
                "1min",
                "2026-06-30T09:10:00",
                886.25,
                886.43,
                886.25,
                886.43,
            )
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

            payload = asyncio.run(get_klines("1min", source="jdjygold_zheshang", provider=provider, store=store))

        self.assertEqual(payload["source"], "jdjygold_zheshang")
        self.assertEqual(payload["display_unit"], "CNY/g")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["session_open"], "2026-06-30T09:10:00")
        self.assertEqual(payload["session_close"], "2026-06-30T09:10:00")
        self.assertAlmostEqual(payload["candles"][-1]["close"], 886.43, places=2)

    def test_source_intraday_klines_use_configured_today_prices_endpoint(self):
        class Response:
            text = '{"resultData":{"datas":[{"value":["2026-06-30 09:10:00","863.05"]},{"value":["2026-06-30 13:00:00","875.18"]},{"value":["2026-06-30 17:00:00","880.83"]}],"status":"SUCCESS"},"success":true}'

            def raise_for_status(self) -> None:
                return None

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs) -> None:
                return None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args) -> None:
                return None

            async def request(self, method, endpoint, **kwargs):
                self.method = method
                self.endpoint = endpoint
                self.kwargs = kwargs
                return Response()

        with tempfile.TemporaryDirectory() as tmp:
            store = KlineStore(Path(tmp) / "klines.sqlite")
            provider = PriceProvider(
                {
                    "data_sources": {
                        "active": "jdjygold_zheshang",
                        "price": {
                            "jdjygold_zheshang": {
                                "type": "http",
                                "name": "浙商银行积存金",
                                "currency": "CNY",
                                "unit": "g",
                                "kline_mode": "intraday",
                                "day_range_endpoint": "https://example.test/today",
                                "day_range_method": "post",
                                "day_range_params": {"productSku": "1961543816"},
                                "day_range_response_format": "jdjygold_today_prices",
                            },
                        },
                    },
                    "retry": {"max_attempts": 1},
                }
            )
            klines_service._cache.clear()

            with patch("backend.app.services.klines.httpx.AsyncClient", FakeAsyncClient):
                payload = asyncio.run(get_klines("1min", source="jdjygold_zheshang", provider=provider, store=store))

        self.assertEqual(payload["source"], "jdjygold_zheshang")
        self.assertEqual(payload["display_unit"], "CNY/g")
        self.assertEqual(payload["count"], 3)
        self.assertEqual([candle["time"] for candle in payload["candles"]], [
            "2026-06-30T09:10:00",
            "2026-06-30T13:00:00",
            "2026-06-30T17:00:00",
        ])
        self.assertEqual(payload["candles"][-1]["close"], 880.83)

    def test_source_intraday_klines_backfill_zheshang_week_history(self):
        class Response:
            def __init__(self, text: str) -> None:
                self.text = text

            def raise_for_status(self) -> None:
                return None

        class FakeAsyncClient:
            requests = []

            def __init__(self, *args, **kwargs) -> None:
                return None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args) -> None:
                return None

            async def request(self, method, endpoint, **kwargs):
                self.requests.append((method, endpoint, kwargs))
                if endpoint.endswith("/historyPrices"):
                    return Response(
                        '{"resultData":{"datas":[{"price":"890.52","time":"1782230400000"},{"price":"867.11","time":"1782835200000"}],"status":"SUCCESS"},"success":true}'
                    )
                return Response(
                    '{"resultData":{"datas":[{"value":["2026-07-01 00:00:00","879.77"]},{"value":["2026-07-01 09:00:00","870.39"]},{"value":["2026-07-01 10:55:00","869.70"]}],"status":"SUCCESS"},"success":true}'
                )

        with tempfile.TemporaryDirectory() as tmp:
            store = KlineStore(Path(tmp) / "klines.sqlite")
            store.upsert_bar("jdjygold_zheshang", "1min", "2026-06-24T00:00:00", 891.0, 891.0, 891.0, 891.0)
            provider = PriceProvider(
                {
                    "data_sources": {
                        "active": "jdjygold_zheshang",
                        "price": {
                            "jdjygold_zheshang": {
                                "type": "http",
                                "name": "浙商银行积存金",
                                "currency": "CNY",
                                "unit": "g",
                                "kline_mode": "intraday",
                                "day_range_endpoint": "https://example.test/today",
                                "day_range_method": "post",
                                "day_range_response_format": "jdjygold_today_prices",
                                "history_endpoint": "https://example.test/historyPrices",
                                "history_method": "post",
                                "history_params": {"period": "w"},
                                "history_response_format": "jdjygold_history_prices",
                            },
                        },
                    },
                    "retry": {"max_attempts": 1},
                }
            )
            klines_service._cache.clear()
            FakeAsyncClient.requests = []

            with patch("backend.app.services.klines.httpx.AsyncClient", FakeAsyncClient):
                payload = asyncio.run(get_klines("1min", source="jdjygold_zheshang", provider=provider, store=store))

        self.assertEqual([endpoint for _, endpoint, _ in FakeAsyncClient.requests], [
            "https://example.test/historyPrices",
            "https://example.test/today",
        ])
        self.assertEqual(payload["source"], "jdjygold_zheshang")
        self.assertEqual(payload["count"], 4)
        self.assertEqual([candle["time"] for candle in payload["candles"]], [
            "2026-06-24T00:00:00",
            "2026-07-01T00:00:00",
            "2026-07-01T09:00:00",
            "2026-07-01T10:55:00",
        ])
        self.assertEqual(payload["candles"][0]["close"], 891.0)
        self.assertEqual(payload["candles"][1]["close"], 879.77)

    def test_source_daily_klines_use_local_db_for_intraday_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = KlineStore(Path(tmp) / "klines.sqlite")
            store.upsert_bar("jdjygold_zheshang", "1day", "2026-06-30T00:00:00", 866, 880, 860, 878)
            provider = PriceProvider(
                {
                    "data_sources": {
                        "active": "jdjygold_zheshang",
                        "price": {
                            "jdjygold_zheshang": {
                                "type": "http",
                                "name": "浙商银行积存金",
                                "currency": "CNY",
                                "unit": "g",
                                "kline_mode": "intraday",
                                "day_range_endpoint": "https://example.test/today",
                            },
                        },
                    },
                    "retry": {"max_attempts": 1},
                }
            )

            payload = asyncio.run(get_klines("1day", source="jdjygold_zheshang", provider=provider, store=store))

        self.assertEqual(payload["source"], "jdjygold_zheshang")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["candles"][0]["change"], 12)

    def test_source_history_klines_do_not_generate_fake_history_without_db_rows(self):
        provider = PriceProvider(
            {
                "data_sources": {
                    "active": "icbc",
                    "price": {
                        "icbc": {
                            "type": "demo",
                            "name": "工商银行积存金",
                            "symbol": "080020000521",
                            "base_price": 879.15,
                            "volatility": 0,
                            "currency": "CNY",
                            "unit": "g",
                            "kline_mode": "history",
                        },
                    },
                },
                "retry": {"max_attempts": 1},
                "storage": {"kline_db_path": ":memory:"},
            }
        )

        payload = asyncio.run(get_klines("1min", source="icbc", provider=provider))

        self.assertEqual(payload["source"], "icbc")
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["candles"], [])

    def test_history_kline_source_keys_pick_passive_realtime_sources(self):
        config = {
            "data_sources": {
                "price": {
                    "icbc": {"kline_mode": "history"},
                    "jdjygold_zheshang": {"kline_mode": "intraday"},
                    "demo": {"kline_mode": "history"},
                }
            }
        }

        self.assertEqual(_history_kline_source_keys(config, selected_key="jdjygold_zheshang"), ["icbc", "demo"])
        self.assertEqual(_history_kline_source_keys(config, selected_key="icbc"), ["demo"])

    def test_capture_kline_tick_for_source_records_display_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = KlineStore(Path(tmp) / "klines.sqlite")
            config = {
                "data_sources": {
                    "active": "icbc",
                    "price": {
                        "icbc": {
                            "type": "demo",
                            "name": "工商银行积存金",
                            "symbol": "080020000521",
                            "base_price": 878.0,
                            "volatility": 0,
                            "currency": "CNY",
                            "unit": "g",
                            "kline_mode": "history",
                            "min_price": 200,
                            "max_price": 1500,
                        },
                    },
                },
                "display": {"currency": "CNY", "unit": "g"},
                "realtime": {"max_data_delay_seconds": 43200},
                "retry": {"max_attempts": 1},
            }
            provider = PriceProvider(config)

            asyncio.run(_capture_kline_tick_for_source(provider, store, config, "icbc"))

            candles = store.get_candles("icbc", "1min")
            self.assertEqual(len(candles), 1)
            self.assertAlmostEqual(candles[0]["close"], 878.18, places=2)


class KlineStoreTests(unittest.TestCase):
    def test_record_price_upserts_minute_day_and_month_bars_with_open_based_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = KlineStore(Path(tmp) / "klines.sqlite")
            first = datetime(2026, 6, 30, 9, 0, 20)
            second = datetime(2026, 6, 30, 9, 0, 55)

            store.record_price("icbc", 880.0, first)
            store.record_price("icbc", 881.0, second)

            minute = store.get_candles("icbc", "1min")
            day = store.get_candles("icbc", "1day")
            month = store.get_candles("icbc", "1month")

        self.assertEqual(len(minute), 1)
        self.assertEqual(minute[0]["time"], "2026-06-30T09:00:00")
        self.assertEqual(minute[0]["open"], 880.0)
        self.assertEqual(minute[0]["high"], 881.0)
        self.assertEqual(minute[0]["low"], 880.0)
        self.assertEqual(minute[0]["close"], 881.0)
        self.assertEqual(minute[0]["change"], 1.0)
        self.assertAlmostEqual(minute[0]["change_percent"], 1 / 880, places=6)
        self.assertEqual(day[0]["time"], "2026-06-30T00:00:00")
        self.assertEqual(month[0]["time"], "2026-06-01T00:00:00")

    def test_prune_applies_period_specific_retention_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = KlineStore(Path(tmp) / "klines.sqlite")
            now = datetime(2026, 6, 30, 12, 0, 0)
            store.upsert_bar("icbc", "1min", "2026-05-30T12:00:00", 870, 870, 870, 870)
            store.upsert_bar("icbc", "1min", "2026-06-01T12:00:00", 871, 871, 871, 871)
            store.upsert_bar("icbc", "1day", "2026-05-29T00:00:00", 872, 872, 872, 872)
            store.upsert_bar("icbc", "1day", "2026-06-01T00:00:00", 873, 873, 873, 873)
            store.upsert_bar("icbc", "1month", "2023-05-01T00:00:00", 874, 874, 874, 874)
            store.upsert_bar("icbc", "1month", "2023-07-01T00:00:00", 875, 875, 875, 875)

            store.prune(now)

            minute_times = [item["time"] for item in store.get_candles("icbc", "1min")]
            day_times = [item["time"] for item in store.get_candles("icbc", "1day")]
            month_times = [item["time"] for item in store.get_candles("icbc", "1month")]

        self.assertEqual(minute_times, ["2026-06-01T12:00:00"])
        self.assertEqual(day_times, ["2026-06-01T00:00:00"])
        self.assertEqual(month_times, ["2023-07-01T00:00:00"])


class MonthlyReviewTests(unittest.TestCase):
    def test_parse_markdown_seed_extracts_gold_june_review_rows(self):
        from backend.app.services.monthly_review import parse_seed_file

        rows = parse_seed_file(Path("黄金30日行情.md"))
        valid_rows = [row for row in rows if row["has_data"]]
        up_rows = [row for row in valid_rows if row["change_percent"] > 0]
        down_rows = [row for row in valid_rows if row["change_percent"] < 0]
        flat_rows = [row for row in valid_rows if row["change_percent"] == 0]

        self.assertEqual(len(rows), 30)
        self.assertEqual(len(valid_rows), 30)
        self.assertEqual(len(up_rows), 7)
        self.assertEqual(len(down_rows), 15)
        self.assertEqual(len(flat_rows), 8)
        self.assertEqual(rows[0]["date"], "2026-06-01")
        best = max(valid_rows, key=lambda row: row["change_percent"])
        worst = min(valid_rows, key=lambda row: row["change_percent"])
        self.assertEqual(best["date"], "2026-06-30")
        self.assertAlmostEqual(best["change_percent"], 0.0220)
        self.assertEqual(worst["date"], "2026-06-10")
        self.assertAlmostEqual(worst["change_percent"], -0.0369)

    def test_parse_silver_and_platinum_seed_files_extract_exchange_rows(self):
        from backend.app.services.monthly_review import parse_seed_file

        silver_rows = parse_seed_file(Path("白银30日行情.md"))
        platinum_rows = parse_seed_file(Path("铂金30日行情.md"))
        silver_valid = [row for row in silver_rows if row["has_data"]]
        platinum_valid = [row for row in platinum_rows if row["has_data"]]

        self.assertEqual(len(silver_rows), 30)
        self.assertEqual(len(platinum_rows), 30)
        self.assertEqual(len(silver_valid), 21)
        self.assertEqual(len(platinum_valid), 21)
        self.assertFalse(silver_rows[5]["has_data"])
        self.assertFalse(platinum_rows[18]["has_data"])

        silver_june_30 = silver_rows[-1]
        self.assertEqual(silver_june_30["date"], "2026-06-30")
        self.assertAlmostEqual(silver_june_30["open"], 14157.0)
        self.assertAlmostEqual(silver_june_30["high"], 14489.0)
        self.assertAlmostEqual(silver_june_30["low"], 13710.0)
        self.assertAlmostEqual(silver_june_30["close"], 14343.0)
        self.assertAlmostEqual(silver_june_30["change_percent"], (14343.0 - 14157.0) / 14157.0, places=4)
        self.assertAlmostEqual(silver_june_30["intraday_range_percent"], (14489.0 - 13710.0) / 13710.0, places=4)

        platinum_june_30 = platinum_rows[-1]
        self.assertEqual(platinum_june_30["date"], "2026-06-30")
        self.assertAlmostEqual(platinum_june_30["open"], 393.80)
        self.assertAlmostEqual(platinum_june_30["high"], 394.50)
        self.assertAlmostEqual(platinum_june_30["low"], 393.80)
        self.assertAlmostEqual(platinum_june_30["close"], 394.40)
        self.assertAlmostEqual(platinum_june_30["change_percent"], (394.40 - 393.80) / 393.80, places=4)
        self.assertAlmostEqual(platinum_june_30["intraday_range_percent"], (394.50 - 393.80) / 393.80, places=4)

    def test_monthly_review_prefers_real_daily_bars_over_seed_rows(self):
        from backend.app.services.monthly_review import build_monthly_review

        with tempfile.TemporaryDirectory() as tmp:
            seed_path = Path(tmp) / "黄金30日行情.md"
            seed_path.write_text(Path("黄金30日行情.md").read_text(), encoding="utf-8")
            store = KlineStore(Path(tmp) / "klines.sqlite")
            store.upsert_bar("gold", "1day", "2026-07-01T00:00:00", 878.0, 890.0, 870.0, 888.0)
            store.upsert_bar("gold", "1day", "2026-06-30T00:00:00", 879.0, 891.0, 875.0, 889.0)

            payload = build_monthly_review(
                "gold",
                {
                    "market_review": {
                        "commodities": {
                            "gold": {
                                "label": "黄金30日行情",
                                "seed_file": str(seed_path),
                                "currency": "CNY",
                                "unit": "g",
                                "theme": "#c89a2b",
                            }
                        },
                    },
                },
                store,
                days=30,
                now=datetime(2026, 7, 1, 12, 0, 0),
            )

        self.assertEqual(payload["key"], "gold")
        self.assertEqual(payload["source"], "gold")
        self.assertEqual(payload["label"], "黄金30日行情")
        self.assertEqual(payload["unit"], "CNY/g")
        self.assertEqual(payload["theme"], "#c89a2b")
        self.assertTrue(payload["has_seed"])
        self.assertEqual(len(payload["items"]), 30)
        self.assertEqual(payload["items"][0]["date"], "2026-06-01")
        self.assertEqual(payload["items"][-1]["date"], "2026-06-30")
        june_30 = next(item for item in payload["items"] if item["date"] == "2026-06-30")
        self.assertEqual(june_30["source"], "realtime")
        self.assertAlmostEqual(june_30["open"], 879.0)
        self.assertAlmostEqual(june_30["change_percent"], 10 / 879)
        self.assertGreaterEqual(len(payload["weekly"]), 5)

    def test_monthly_review_uses_seed_date_window_instead_of_current_day_window(self):
        from backend.app.services.monthly_review import build_monthly_review

        with tempfile.TemporaryDirectory() as tmp:
            seed_path = Path(tmp) / "黄金30日行情.md"
            seed_path.write_text(Path("黄金30日行情.md").read_text(), encoding="utf-8")
            store = KlineStore(Path(tmp) / "klines.sqlite")

            payload = build_monthly_review(
                "gold",
                {
                    "market_review": {
                        "commodities": {
                            "gold": {
                                "label": "黄金30日行情",
                                "seed_file": str(seed_path),
                                "currency": "CNY",
                                "unit": "g",
                            }
                        },
                    },
                },
                store,
                days=30,
                now=datetime(2026, 7, 1, 9, 30, 0),
            )

        self.assertEqual(payload["items"][0]["date"], "2026-06-01")
        self.assertEqual(payload["items"][-1]["date"], "2026-06-30")
        self.assertTrue(payload["items"][-1]["has_data"])

    def test_monthly_review_returns_blank_rows_without_seed_or_daily_bars(self):
        from backend.app.services.monthly_review import build_monthly_review

        with tempfile.TemporaryDirectory() as tmp:
            store = KlineStore(Path(tmp) / "klines.sqlite")
            payload = build_monthly_review(
                "gold",
                {
                    "market_review": {
                        "commodities": {
                            "gold": {
                                "label": "黄金30日行情",
                                "currency": "CNY",
                                "unit": "g",
                            }
                        }
                    },
                },
                store,
                days=30,
                now=datetime(2026, 7, 1, 9, 30, 0),
            )

        self.assertFalse(payload["has_seed"])
        self.assertEqual(len(payload["items"]), 30)
        self.assertTrue(all(not item["has_data"] for item in payload["items"]))
        self.assertEqual(payload["summary"]["trading_days"], 0)
        self.assertEqual(payload["summary"]["missing_days"], 30)
        self.assertIsNone(payload["summary"]["best_day"])
        self.assertIsNone(payload["summary"]["worst_day"])
        self.assertIsNone(payload["summary"]["cumulative_change_percent"])

    def test_build_monthly_reviews_returns_three_commodities_in_display_order(self):
        from backend.app.services.monthly_review import build_monthly_reviews

        store = KlineStore(":memory:")
        payload = build_monthly_reviews(
            {
                "market_review": {
                    "commodities": {
                        "gold": {
                            "label": "黄金30日行情",
                            "seed_file": "黄金30日行情.md",
                            "currency": "CNY",
                            "unit": "g",
                            "theme": "#c89a2b",
                        },
                        "silver": {
                            "label": "白银30日行情",
                            "seed_file": "白银30日行情.md",
                            "currency": "CNY",
                            "unit": "kg",
                            "theme": "#7d8da1",
                        },
                        "platinum": {
                            "label": "铂金30日行情",
                            "seed_file": "铂金30日行情.md",
                            "currency": "CNY",
                            "unit": "g",
                            "theme": "#7f6bb2",
                        },
                    }
                }
            },
            store,
            days=30,
            now=datetime(2026, 7, 1, 9, 30, 0),
        )

        self.assertEqual(payload["days"], 30)
        self.assertEqual([item["key"] for item in payload["items"]], ["gold", "silver", "platinum"])
        self.assertEqual([item["label"] for item in payload["items"]], ["黄金30日行情", "白银30日行情", "铂金30日行情"])
        self.assertEqual(payload["items"][1]["unit"], "CNY/kg")
        self.assertEqual(payload["items"][2]["theme"], "#7f6bb2")

    def test_monthly_reviews_api_returns_three_commodity_reviews(self):
        payload = asyncio.run(market_monthly_reviews(days=30))

        self.assertEqual(payload["days"], 30)
        self.assertEqual([item["key"] for item in payload["items"]], ["gold", "silver", "platinum"])
        self.assertEqual([item["label"] for item in payload["items"]], ["黄金30日行情", "白银30日行情", "铂金30日行情"])

    def test_legacy_monthly_review_api_maps_icbc_to_gold(self):
        payload = asyncio.run(market_monthly_review(source="icbc", days=30))

        self.assertEqual(payload["key"], "gold")
        self.assertEqual(payload["label"], "黄金30日行情")
        self.assertEqual(payload["items"][0]["date"], "2026-06-01")
        self.assertEqual(payload["items"][-1]["date"], "2026-06-30")


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
