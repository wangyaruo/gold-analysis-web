# Gold Analysis Web

生产级黄金市场实时分析页面，包含实时价格、图表、止损点、结构化买入推荐、新闻情绪和盈亏计算。

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

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
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
