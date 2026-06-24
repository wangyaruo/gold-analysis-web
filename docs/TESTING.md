# 测试说明

## 后端核心业务测试

```bash
python3 -m unittest backend.tests.test_market_logic -v
```

覆盖：

- SMA / EMA。
- 止损点公式。
- 新闻情绪关键词规则。
- 买入推荐规则。
- 盈亏公式。
- 价格范围和时间戳有效性校验。

## 前端端到端测试

```bash
cd frontend
npm install
npm run test:e2e
```

Playwright 用例通过 route mock 固定 API 响应，验证：

- 实时价格、连接状态、推荐和止损点渲染。
- 用户输入买入价和持有数量后重新计算盈亏。

默认 E2E 使用本机 Google Chrome。若机器没有 Chrome，可先运行
`npx playwright install chromium`，并把 `frontend/playwright.config.js`
中的 `channel: 'chrome'` 移除。

## 构建验证

```bash
cd frontend
npm run build
```

后端可用 `uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8318` 启动后访问 `/api/health`。
