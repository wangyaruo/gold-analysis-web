# Gold Analysis Web

生产级黄金市场实时分析页面，包含实时价格、图表、止损点、结构化买入推荐、新闻情绪和盈亏计算。页面默认按国内常用口径显示人民币/克，并保留原始 XAU/USD 报价。行情默认优先读取 Yahoo Finance `GC=F`，访问失败时回退到 2026-06-26 更新的参考价。

## 技术栈

- Frontend: Vue 3, Vite, JavaScript, Playwright
- Backend: Python, FastAPI, httpx, PyYAML
- Config: root-level `config.yaml`
- Deployment docs: Dockerfile + docker-compose example

## 目录结构

```text
.
├── config.yaml
├── backend/
│   ├── app/
│   │   ├── api.py
│   │   ├── main.py
│   │   ├── core/
│   │   └── services/
│   ├── requirements.txt
│   └── tests/
├── frontend/
│   ├── src/
│   ├── tests/e2e/
│   └── package.json
├── docs/
└── docker-compose.yml
```

## 本地运行

### 快速启动

适合第一次试跑，直接使用当前 Python 用户环境。

后端：

```bash
cd /Users/wangyaruo/Desktop/卡卡/gold-analysis-web
python3 -m pip install -r backend/requirements.txt
python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8318
```

前端另开一个终端：

```bash
cd /Users/wangyaruo/Desktop/卡卡/gold-analysis-web/frontend
npm install
npm run dev -- --port 5178
```

打开页面：

- Frontend: `http://127.0.0.1:5178/`
- Backend API docs: `http://127.0.0.1:8318/docs`

停止服务：

```bash
lsof -ti tcp:8318 | xargs kill
lsof -ti tcp:5178 | xargs kill
```

### 规范启动

适合长期开发，把 Python 依赖安装到项目自己的 `.venv` 中。

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8318
```

```bash
cd frontend
npm install
npm run dev
```

默认开发 token 为 `change-me-local-token`，仅用于本地。生产环境必须设置 `API_AUTH_TOKEN`。

## 验证

```bash
python3 -m unittest backend.tests.test_market_logic -v
cd frontend && npm run build
cd frontend && npm run test:e2e
```

更多说明见 `docs/`。
