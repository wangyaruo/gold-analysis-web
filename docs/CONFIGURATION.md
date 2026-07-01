# 配置说明

根目录 `config.yaml` 管理全部业务配置。敏感值只写环境变量名，不写真实密钥。

## 数据源

```yaml
data_sources:
  active: "yahoo_finance"
  fallback: "demo"
```

- `icbc`: 工商银行积存金实时主动积存价格，原生人民币/克 `CNY/g` 报价。
- `jdjygold_zheshang`: 京东金融浙商银行积存金实时价格，原生人民币/克 `CNY/g` 报价。
- `hongyun_gold_reference`: 民生银行积存金，底层使用京东金融民生银行积存金公开源，原生人民币/克 `CNY/g` 报价。
- `yahoo_finance`: Yahoo Finance 黄金期货 `GC=F`。
- `yahoo_finance_spot`: Yahoo Finance 现货黄金兑美元 `XAUUSD=X`，用于和期货报价交叉参考。
- `eastmoney_au9999`: 东方财富黄金9999 `AU9999` 页面底层接口，原生人民币/克 `CNY/g` 报价。
- `goldpriceapi`: GoldAPI XAU/USD，需要通过 `GOLD_API_KEY` 读取认证密钥。
- `demo`: 离线参考数据源，也是外部源失败时的 fallback。

前端会读取 `/api/config/public` 返回的 `data_sources.active` 作为实时行情和 K 线默认源，并在 K 线图区域保留行情源选择器。切换行情源只刷新实时快照和 K 线，不再影响底部黄金/白银/铂金 30 日行情；请求会携带 `source` 查询参数，例如：

```text
GET /api/market/snapshot?source=eastmoney_au9999
```

如果指定源请求失败，系统会按 `fallback` 配置回退到 `demo`，但响应中的 `price.requested_source` 仍保留用户选择的源，`price.source` 表示实际返回数据的源。

## 30天行情 Seed

`market_review.commodities` 用于给 `/api/market/monthly-reviews` 提供只读历史行情数据。当前三类行情为：

- `gold`: `黄金30日行情.md`，单位 `CNY/g`，来源为工商银行积存金历史聚合。
- `silver`: `白银30日行情.md`，单位 `CNY/kg`，来源为上海黄金交易所 `Ag(T+D)`。
- `platinum`: `铂金30日行情.md`，单位 `CNY/g`，来源为上海黄金交易所 `Pt99.95`。

这些 seed 只参与 30 天行情展示，不会写入本地 `kline_bars` 真实 K 线库；同日期已有真实 `1day` K 线时，真实数据优先覆盖 seed。旧接口 `/api/market/monthly-review` 仍保留兼容，默认返回 `gold`。

每个 HTTP 数据源支持：

- `endpoint`: API 地址。
- `api_key_env`: API key 的环境变量名。
- `auth_header`: key 注入的 header 名称。
- `response_format`: 支持 `json`、`jsonp`、`icbc_accrual`、`jdjygold_latest` 等格式。`jsonp` 用于东方财富等 callback 包裹响应，系统会剥离 callback 后解析 JSON；`jdjygold_latest` 用于京东金融积存金公开接口。
- `json_paths`: 从响应 JSON 中读取价格和时间戳的路径。
- `timeout_seconds`: 单次请求超时。
- `min_price` / `max_price`: 合理价格区间校验。
- `label` / `description`: 前端展示用名称和说明，不包含敏感信息。
- `currency` / `unit`: 数据源原始单位。未设置时默认按 `display.source_currency/source_unit` 处理；如 `eastmoney_au9999` 设置为 `CNY/g`，前端展示不会再次换算。
- `max_data_delay_seconds`: 可选的数据源级延迟阈值覆盖。`eastmoney_au9999` 在国内交易时段之外可能停留在最后报价，因此作为参考源允许日内宽限；默认实时源仍使用全局 5 秒阈值。

## 实时性

```yaml
realtime:
  frontend_refresh_seconds: 2
  max_data_delay_seconds: 5
```

前端每 2 秒刷新一次。后端拒绝超过 5 秒的数据，防止交易视图展示过期价格。

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

不同数据源可能存在口径差异：

- `icbc`、`jdjygold_zheshang` 和 `hongyun_gold_reference` 都是人民币/克口径，更适合国内积存金价格参考。
- `hongyun_gold_reference` 是民生银行积存金公开源，前端展示为“民生银行积存金”。
- `GC=F` 更接近期货合约报价。
- `XAUUSD=X` 更接近现货黄金兑美元报价。
- `AU9999` 是上海黄金交易所相关的人民币/克报价，适合和国内金价口径交叉参考。
- 认证源如 `goldpriceapi` 适合生产环境接入稳定授权数据。
- `demo` 只用于开发、离线、fallback，不应用于真实交易判断。

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
