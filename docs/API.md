# API 文档

默认服务地址：`http://127.0.0.1:8000`

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
- `indicator_defaults`: 指标默认参数。
- `decision_rule_defaults`: 推荐规则阈值。

## GET /api/market/snapshot

返回市场快照。

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
    "source": "demo"
  },
  "history": [{"index": 1, "price": 2320.1}],
  "indicators": {
    "stop_loss": {
      "indicator_type": "SMA",
      "period": 20,
      "multiplier": 2,
      "indicator_value": 2335.2,
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
