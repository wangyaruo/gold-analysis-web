# API 文档

默认服务地址：`http://127.0.0.1:8318`

所有业务接口需要：

```http
Authorization: Bearer change-me-local-token
```

邮件提醒规则接口还需要邮箱验证会话：

```http
X-Alert-Session: <session_token>
```

会话通过 `/api/alerts/session/request-code` 和 `/api/alerts/session/verify` 获取。提醒规则按已验证邮箱隔离，接口返回的邮箱为脱敏值。

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
- `alerts`: 前端可读取的提醒配置摘要，包含是否启用 worker、预估突破阶梯、默认行情源和 SMTP 是否已配置。

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
  },
  "predicted_range": {
    "low": 878.12,
    "high": 895.68,
    "range_percent": 0.02,
    "unit": "CNY/g"
  }
}
```

`predicted_range` 是后端统一计算的系统预估日内区间。前端展示和邮件提醒判断都使用该字段。

## GET /api/market/factors

返回黄金影响因子榜。该接口只用于解释行情驱动，不参与 `/api/market/snapshot` 的结构化买入建议。

可选查询参数：

- `source`: 指定银行积存金行情源，例如 `icbc`、`jdjygold_zheshang`、`hongyun_gold_reference`。

示例：

```http
GET /api/market/factors?source=icbc
Authorization: Bearer change-me-local-token
```

核心响应：

```json
{
  "generated_at": "2026-07-02T10:00:00+08:00",
  "basis": "银行积存金 CNY/g",
  "overall_bias": {"signal": "positive", "score": 1.4},
  "items": [
    {
      "key": "bank_price",
      "label": "银行积存金",
      "value": 894.7,
      "change": 4.7,
      "unit": "CNY/g",
      "signal": "positive",
      "strength": 4.7,
      "source_name": "工商银行积存金",
      "updated_at": "2026-07-02T10:00:00+08:00",
      "explanation": "当前银行对客积存金报价上行偏利好，下行偏利空。",
      "status": "ok"
    }
  ]
}
```

`signal` 使用 `positive`、`negative`、`neutral`；`status` 为 `ok`、`stale` 或 `unavailable`。前端按接口排序全量展示因子，不再额外折叠。

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

## POST /api/alerts/session/request-code

向收件邮箱发送验证码。

请求：

```json
{
  "email": "me@example.com"
}
```

响应：

```json
{
  "sent": true,
  "subscriber": {
    "email": "me***@example.com"
  }
}
```

## POST /api/alerts/session/verify

验证邮箱并返回提醒会话 token。

如果这是该邮箱第一次拥有提醒规则，后端会自动复制一份统一默认规则：启用、默认行情源、清仓价/抄底价/预估高点/预估低点四类提醒开关全部打开；自定义清仓价和抄底价初始为空，用户可在前端保存自己的价格。

请求：

```json
{
  "email": "me@example.com",
  "code": "123456"
}
```

响应：

```json
{
  "session_token": "token",
  "subscriber": {
    "email": "me***@example.com"
  }
}
```

## GET /api/alerts/rules

返回当前已验证邮箱下的邮件提醒规则。

响应：

```json
{
  "rules": [
    {
      "id": 1,
      "enabled": true,
      "source": "icbc",
      "recipient_email": "me***@example.com",
      "target_high_price": 900,
      "target_low_price": 870,
      "notify_on_custom_high": true,
      "notify_on_custom_low": true,
      "notify_on_predicted_high": true,
      "notify_on_predicted_low": true,
      "state": {
        "alert_date": "2026-07-01",
        "last_predicted_high_alert_price": 890
      }
    }
  ],
  "smtp_configured": true
}
```

## POST /api/alerts/rules

创建当前已验证邮箱下的邮件提醒规则。收件邮箱来自 `X-Alert-Session` 对应的已验证邮箱，请求体不需要传 `recipient_email`。

请求：

```json
{
  "enabled": true,
  "source": "icbc",
  "target_high_price": 900,
  "target_low_price": 870,
  "notify_on_custom_high": true,
  "notify_on_custom_low": true,
  "notify_on_predicted_high": true,
  "notify_on_predicted_low": true
}
```

响应：

```json
{
  "rule": {
      "id": 1,
      "enabled": true,
      "source": "icbc",
      "recipient_email": "me***@example.com"
  }
}
```

## PUT /api/alerts/rules/{id}

更新当前已验证邮箱下的邮件提醒规则。修改 `target_high_price` 或 `target_low_price` 时，后端会重置对应自定义目标价的触发状态。

## DELETE /api/alerts/rules/{id}

删除当前已验证邮箱下的邮件提醒规则及其状态。

响应：

```json
{"deleted": true}
```

## POST /api/alerts/test-email

使用当前 SMTP 环境变量向已验证邮箱发送测试邮件。

请求：

```json
{
  "source_label": "工商银行积存金",
  "current_price": 890,
  "display_unit": "CNY/g",
  "predicted_range": {
    "low": 880,
    "high": 890
  }
}
```

响应：

```json
{"sent": true}
```
