# API 文档

默认服务地址：`http://127.0.0.1:8318`

所有业务接口需要：

```http
Authorization: Bearer change-me-local-token
```

## GET /api/health

健康检查，无需认证。

响应：

```json
{"status": "ok"}
```

## GET /api/config/public

返回前端可安全读取的配置。

响应字段：

- `realtime`: 刷新频率和延迟阈值。
- `portfolio_defaults`: 默认买入价和持有数量。
- `data_sources`: 前端可切换的数据源列表，包含 `active`、`fallback` 和 `options`。
- `indicator_defaults`: 指标默认参数。
- `decision_rule_defaults`: 推荐规则阈值。

## GET /api/market/snapshot

返回市场快照。

可选查询参数：

- `source`: 指定行情源，例如 `yahoo_finance`、`yahoo_finance_spot`、`eastmoney_au9999`、`goldpriceapi`、`demo`。不传时使用 `config.yaml` 中的 `data_sources.active`。

示例：

```http
GET /api/market/snapshot?source=eastmoney_au9999
Authorization: Bearer change-me-local-token
```

核心响应：

```json
{
  "price": {
    "symbol": "XAUUSD",
    "value": 2338.42,
    "unit": "USD/oz",
    "display_value": 544.95,
    "display_unit": "CNY/g",
    "timestamp": "2026-06-24T03:30:00+00:00",
    "source": "yahoo_finance_xauusd",
    "requested_source": "yahoo_finance_spot"
  },
  "history": [{"index": 1, "price": 2320.1}],
  "indicators": {
    "stop_loss": {
      "indicator_type": "SMA",
      "period": 20,
      "multiplier": 2,
      "indicator_value": 4015.2,
      "volatility": 5.4,
      "stop_loss": 2324.4,
      "display_stop_loss": 541.68,
      "display_unit": "CNY/g"
    },
    "ma_cross": "golden_cross",
    "cross_strength": 0.014,
    "bollinger": {
      "breakout": "upper",
      "upper_band": 2360.2,
      "lower_band": 2310.8
    }
  },
  "sentiment": {
    "label": "positive",
    "score": 2
  },
  "recommendation": {
    "action": "buy",
    "confidence": 1,
    "reasons": [],
    "risks": []
  }
}
```

## GET /api/market/monthly-reviews

返回单面板使用的三类 30 日行情：黄金、白银、铂金。

可选查询参数：

- `days`: 返回天数，默认 `30`。

示例：

```http
GET /api/market/monthly-reviews?days=30
Authorization: Bearer change-me-local-token
```

核心响应：

```json
{
  "days": 30,
  "generated_at": "2026-07-01T09:00:00",
  "items": [
    {
      "key": "gold",
      "source": "gold",
      "label": "黄金30日行情",
      "unit": "CNY/g",
      "theme": "#c89a2b",
      "items": [
        {
          "date": "2026-06-30",
          "open": 866.5,
          "high": 886.88,
          "low": 863.03,
          "close": 885.53,
          "change_percent": 0.022,
          "intraday_range_percent": 0.0276,
          "has_data": true
        }
      ]
    }
  ]
}
```

## GET /api/market/monthly-review

兼容旧接口。默认返回 `gold`；`source=icbc` 会映射到 `gold`。前端新页面不再调用该接口。

## POST /api/portfolio/pnl

请求：

```json
{
  "buy_price": 2300,
  "quantity": 2,
  "current_price": 2360
}
```

公式：

```text
盈亏金额 = (当前价 - 买入价) * 持有数量
盈亏百分比 = (盈亏金额 / (买入价 * 持有数量)) * 100%
```

响应：

```json
{
  "amount": 120,
  "percent": 2.608696
}
```
