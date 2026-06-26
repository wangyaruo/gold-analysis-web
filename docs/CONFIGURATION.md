# 配置说明

根目录 `config.yaml` 管理全部业务配置。敏感值只写环境变量名，不写真实密钥。

## 数据源

```yaml
data_sources:
  active: "demo"
```

- `demo`: 默认数据源，可离线运行。
- `goldpriceapi`: 通过 `GOLD_API_KEY` 读取认证密钥。
- `yahoo_finance`: 使用 Yahoo Finance chart API 示例端点。

每个 HTTP 数据源支持：

- `endpoint`: API 地址。
- `api_key_env`: API key 的环境变量名。
- `auth_header`: key 注入的 header 名称。
- `response_format`: 当前实现为 JSON。
- `json_paths`: 从响应 JSON 中读取价格和时间戳的路径。
- `timeout_seconds`: 单次请求超时。
- `min_price` / `max_price`: 合理价格区间校验。

## 实时性

```yaml
realtime:
  frontend_refresh_seconds: 10
  max_data_delay_seconds: 5
```

前端每 10 秒刷新一次。后端拒绝超过 5 秒的数据，防止交易视图展示过期价格。

## 人民币展示

后端保留数据源原始 `USD/oz` 报价，并额外返回前端展示用的 `CNY/g` 字段。

```yaml
display:
  currency: "CNY"
  unit: "g"
  source_currency: "USD"
  source_unit: "oz"
  usd_cny_rate: 6.808596
  troy_ounce_grams: 31.1034768
```

换算公式：

```text
CNY/g = USD/oz * usd_cny_rate / troy_ounce_grams
```

`usd_cny_rate` 当前是配置值，便于离线和测试环境稳定运行。默认值 `6.808596` 于 2026-06-26 参考公开汇率接口更新。接入生产环境时可扩展为实时汇率数据源。

## 行情数据优先级

默认配置优先使用 Yahoo Finance 黄金期货 `GC=F`：

```yaml
data_sources:
  active: "yahoo_finance"
  fallback: "demo"
```

当服务器无法访问 Yahoo 或解析失败时，系统自动回退到 `demo`。当前 `demo` 不再使用旧的 2335 USD/oz，而是按 2026-06-26 公开行情参考值设置为 `4018.77 USD/oz`，避免无网环境展示明显过期价格。

## 止损公式

默认：

```yaml
indicators:
  stop_loss:
    type: "SMA"
    period: 20
    multiplier: 2
    volatility_window: 20
```

SMA:

```text
SMA(n) = 最近 n 个价格之和 / n
```

EMA:

```text
alpha = 2 / (n + 1)
EMA(today) = price(today) * alpha + EMA(yesterday) * (1 - alpha)
```

止损:

```text
stop_loss = indicator_value - multiplier * volatility
```

交易影响：

- SMA 更平滑，适合过滤噪声，但响应较慢。
- EMA 对近期价格更敏感，适合更快跟随趋势，但可能产生更多假信号。
- `multiplier` 越大，止损越宽，减少噪声止损但增加单笔亏损风险。
- `volatility_window` 越长，波动估计越稳定，但对市场状态切换反应更慢。

## 买入推荐规则

默认阈值：

```yaml
decision_rules:
  min_cross_strength: 0.01
  require_bollinger_upper_breakout: true
  min_confidence: 0.7
  sentiment_required_for_buy: "positive"
```

规则模型：

```text
MA 金叉且交叉幅度 >= min_cross_strength
AND 价格突破布林带上轨
AND 新闻情绪为 positive
AND confidence >= min_confidence
=> buy
```

默认值按保守趋势跟随策略设置：要求均线趋势、价格突破和新闻情绪同时支持，降低单一指标误判风险。实际生产前应使用目标交易品种和周期重新回测。

## 新闻情绪

正负关键词和阈值都在 `news.sentiment` 下配置。默认示例覆盖黄金行业常见驱动：

- 正面：通胀对冲、央行购金、避险需求、美元走弱、降息。
- 负面：美元走强、加息、鹰派美联储、收益率上升、风险偏好回升。

计分规则：

- 每条正面关键词命中加 1。
- 同一篇文章的负面风险按文章去重，命中扣 1。
- 分数达到 `positive_threshold` 标记为 positive。
- 分数低于或等于 `negative_threshold` 标记为 negative。
- 其他情况为 neutral。
