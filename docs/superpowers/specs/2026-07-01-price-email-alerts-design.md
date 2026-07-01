# 价格邮件提醒功能设计

## 范围

为现有黄金行情分析面板新增一个单用户邮件提醒功能。用户可以在实时展示价格达到自定义阈值，或触达/突破系统预估的日内高点、低点时收到邮件通知。该功能基于现有 FastAPI 后端、Vue 仪表盘、根目录 `config.yaml` 业务配置，以及现有实时行情轮询流程实现。

本设计不引入多用户登录、账号归属、短信、移动推送或交易下单能力。

## 目标

- 用户可以在仪表盘里配置一个或多个邮件提醒规则。
- 当前展示价格达到用户自定义高价或低价时发送邮件。
- 当前展示价格第一次触达系统预估高点或低点时发送邮件。
- 首次触达后，如果价格继续朝同一方向每突破 `2 CNY/g`，继续发送一次邮件。
- 提醒判断放在后端执行，浏览器关闭后仍可正常提醒。
- 仪表盘展示和邮件提醒共用同一套预估区间计算结果，避免页面和邮件判断不一致。

## 架构

后端负责提醒判断。新增提醒服务定时获取当前启用的行情源，计算展示价格和系统预估日内区间，评估已启用的提醒规则，并在规则触发时通过 SMTP 发送邮件。

当前前端 `frontend/src/utils/dayRange.js` 中的预估高低点计算逻辑应迁移到后端服务，并通过 `/api/market/snapshot` 返回 `predicted_range`。前端改为直接渲染后端返回的预估区间，不再单独计算一套结果。这样可以保证页面展示和邮件引擎使用同一个判断依据。

建议新增的后端模块：

- `backend/app/services/predicted_range.py`：根据 K 线、当前价和行情源提供的日内区间，计算今日区间和系统预估日内区间。
- `backend/app/services/alerts.py`：保存提醒规则和提醒状态，评估触发条件，并生成通知事件。
- `backend/app/services/email_sender.py`：根据 SMTP 配置发送邮件，并记录发送失败日志。
- `backend/app/alert_worker.py` 或 FastAPI lifespan 任务：按配置间隔运行提醒检查。

## 配置

在 `config.yaml` 中新增 `alerts` 配置：

```yaml
alerts:
  enabled: false
  check_interval_seconds: 15
  predicted_breakout_step_cny_g: 2
  storage_path: "data/price_alerts.sqlite"
  default_source: "icbc"
  email:
    smtp_host_env: "ALERT_SMTP_HOST"
    smtp_port_env: "ALERT_SMTP_PORT"
    smtp_username_env: "ALERT_SMTP_USERNAME"
    smtp_password_env: "ALERT_SMTP_PASSWORD"
    from_email_env: "ALERT_FROM_EMAIL"
    use_tls_env: "ALERT_SMTP_USE_TLS"
```

SMTP 密钥和邮箱密码只放在环境变量里，并在 Docker 环境变量中透传，不写入 `config.yaml`。

## 提醒规则模型

规则和状态保存到 SQLite，路径使用 `alerts.storage_path`。这与项目现有 K 线 SQLite 存储方式保持一致，适合当前单用户场景。

规则字段：

- `id`
- `enabled`
- `source`
- `recipient_email`
- `target_high_price`
- `target_low_price`
- `notify_on_custom_high`
- `notify_on_custom_low`
- `notify_on_predicted_high`
- `notify_on_predicted_low`
- `created_at`
- `updated_at`

状态字段：

- `rule_id`
- `source`
- `alert_date`
- `last_custom_high_alert_price`
- `last_custom_low_alert_price`
- `last_predicted_high_alert_price`
- `last_predicted_low_alert_price`
- `last_predicted_high_value`
- `last_predicted_low_value`
- `last_alerted_at`

`last_predicted_high_value` 和 `last_predicted_low_value` 记录最近一次评估时关联的系统预估边界；`last_predicted_*_alert_price` 记录最近一次真正触发邮件的价格。预估边界提醒状态按行情源和 Asia/Shanghai 日期隔离。换行情源或进入新的一天时，重新开始首次触达判断。

## 触发规则

所有比较都使用展示价格 `CNY/g`，因为仪表盘展示和用户理解的单位都是元/克。

### 自定义目标价提醒

如果启用 `notify_on_custom_high`，且 `current_price >= target_high_price`，则发送一次自定义高价提醒邮件。用户修改目标高价后，重置对应的自定义高价提醒状态。

如果启用 `notify_on_custom_low`，且 `current_price <= target_low_price`，则发送一次自定义低价提醒邮件。用户修改目标低价后，重置对应的自定义低价提醒状态。

### 预估高点提醒

如果启用 `notify_on_predicted_high`，且 `current_price >= predicted_range.high`：

1. 如果 `last_predicted_high_alert_price` 为空，说明这是当日/当前行情源第一次触达预估高点，立即发送邮件。
2. 如果已经发送过高点提醒，则只有在 `current_price >= last_predicted_high_alert_price + predicted_breakout_step_cny_g` 时再次发送邮件。
3. 发送后，将 `last_predicted_high_alert_price` 更新为当前价格，并保存当前 `predicted_range.high`。

示例：系统预估高点为 `890 CNY/g`，突破阶梯为 `2 CNY/g`。

- `890`：第一次触达，发送邮件。
- `891`：不发送。
- `892`：相比上次提醒价再涨 `2 CNY/g`，发送邮件。
- `893`：不发送。
- `894`：再次达到新阶梯，发送邮件。

### 预估低点提醒

如果启用 `notify_on_predicted_low`，且 `current_price <= predicted_range.low`：

1. 如果 `last_predicted_low_alert_price` 为空，说明这是当日/当前行情源第一次触达预估低点，立即发送邮件。
2. 如果已经发送过低点提醒，则只有在 `current_price <= last_predicted_low_alert_price - predicted_breakout_step_cny_g` 时再次发送邮件。
3. 发送后，将 `last_predicted_low_alert_price` 更新为当前价格，并保存当前 `predicted_range.low`。

示例：系统预估低点为 `880 CNY/g`，突破阶梯为 `2 CNY/g`。

- `880`：第一次触达，发送邮件。
- `879`：不发送。
- `878`：相比上次提醒价再跌 `2 CNY/g`，发送邮件。
- `877`：不发送。
- `876`：再次达到新阶梯，发送邮件。

预估边界提醒不设置时间冷却。去重只依赖 `2 CNY/g` 的价格阶梯。

不再设计单独的“预估区间更新邮件”。系统预估高点或低点变化本身不直接发邮件，只有当前价格触达最新预估边界，或在上次提醒价基础上继续突破 `2 CNY/g` 时才发邮件。

## API 设计

在现有 bearer token 保护下新增接口：

- `GET /api/alerts/rules`：列出提醒规则和当前状态摘要。
- `POST /api/alerts/rules`：创建提醒规则。
- `PUT /api/alerts/rules/{id}`：更新提醒规则；阈值变化时重置对应状态。
- `DELETE /api/alerts/rules/{id}`：删除提醒规则。
- `POST /api/alerts/test-email`：使用当前 SMTP 配置发送测试邮件。

扩展 `GET /api/market/snapshot` 返回：

```json
{
  "predicted_range": {
    "low": 878.12,
    "high": 895.68,
    "range_percent": 0.02,
    "unit": "CNY/g"
  }
}
```

## 前端设计

在现有仪表盘中新增一个紧凑的提醒设置面板，不单独做营销式页面。面板支持：

- 收件邮箱输入。
- 行情源选择，复用现有公开行情源选项。
- 自定义高价、低价输入。
- 自定义高价、自定义低价、预估高点、预估低点四个开关。
- 保存、停用、删除、发送测试邮件操作。
- 小型状态提示，展示 SMTP 是否已配置，以及最近一次提醒发送时间。

现有价格卡片继续展示预估高点和低点，但在后端接管计算后，应读取 `snapshot.predicted_range`。

## 邮件内容

每封提醒邮件包含：

- 提醒类型，例如自定义高价、自定义低价、预估高点首次触达、预估高点继续突破、预估低点首次触达、预估低点继续突破。
- 当前展示价格和单位。
- 行情源名称。
- 可用时展示系统预估高点和低点。
- 自定义提醒触发时展示目标价。
- Asia/Shanghai 时间。
- 简短风险提示：数据仅供参考，不构成投资建议。

## 错误处理

- SMTP 未配置时，仍允许保存提醒规则，但测试邮件接口和运行时发送应返回或记录明确的配置错误。
- 提醒 worker 某次价格获取失败时，记录日志，并在下一轮检查时重试。
- 某一条规则邮件发送失败时，继续评估其他已启用规则。
- 如果无法计算预估区间，则该轮跳过预估边界提醒，但仍继续评估自定义目标价提醒。

## 测试

后端测试覆盖：

- 预估区间计算与现有前端示例保持一致。
- 自定义高价和低价触发行为。
- 第一次触达预估高点/低点时立即发送。
- 预估高点只在相比上次高点提醒价每再涨 `2 CNY/g` 时继续发送。
- 预估低点只在相比上次低点提醒价每再跌 `2 CNY/g` 时继续发送。
- 预估边界提醒不使用时间冷却。
- SMTP 发送使用 mock，发送失败不导致 worker 崩溃。

前端测试覆盖：

- 提醒设置面板渲染。
- 通过 API 保存提醒规则。
- 页面展示后端返回的 `predicted_range`。
- 测试邮件操作能展示成功或失败状态。

## 实施顺序

1. 将预估区间计算迁移到后端，并在 snapshot 中返回。
2. 新增提醒规则/状态存储，以及纯触发逻辑测试。
3. 新增 SMTP 邮件发送器和测试邮件接口。
4. 新增后台提醒 worker。
5. 新增前端提醒设置面板。
6. 更新文档、Docker 环境变量示例和测试。
