# Gold Analysis Web

生产级黄金市场实时分析页面，包含实时价格、图表、止损点、结构化买入推荐、新闻情绪和盈亏计算。页面默认按国内常用口径显示人民币/克，并保留原始 XAU/USD 报价。行情默认优先读取 Yahoo Finance `GC=F`，也支持在前端切换 Yahoo 现货、东方财富 AU9999、GoldAPI 和 demo 参考源；访问失败时回退到 2026-06-26 更新的参考价。

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

## 服务器运行

当前服务器用于自动部署和公网访问。密码、API Key、Token 等敏感信息不要写入仓库，应通过服务器环境变量或部署平台 secret 管理。

### 访问地址

- Frontend: `http://154.219.120.25:5178/`
- Backend API docs: `http://154.219.120.25:8318/docs`
- Backend health: `http://154.219.120.25:8318/api/health`

### SSH 登录

```bash
ssh root@154.219.120.25
cd /root/gold-analysis-web
```

### 自动部署

服务器侧自动部署脚本位于 `/root/gold-analysis-web/deploy.sh`。推送到远程 `main` 后，服务器 webhook 会拉取最新代码、重新构建前端，并重启服务。

手动触发一次部署：

```bash
ssh root@154.219.120.25
cd /root/gold-analysis-web
./deploy.sh
```

当前服务器端口约定：

- 前端静态服务：`5178`
- 后端 FastAPI 服务：`8318`
- 旧前端端口 `5173` 已停用，不应再作为访问入口。

### 服务器排查命令

查看端口监听：

```bash
ss -ltnp | grep -E ':5178|:8318'
```

查看服务进程：

```bash
ps -ww -fp "$(cat backend.pid)" "$(cat frontend.pid)"
pgrep -af "uvicorn backend.app.main:app|http.server 5178"
```

查看部署和运行日志：

```bash
tail -f deploy.log
tail -f backend.log
tail -f frontend.log
tail -f webhook.log
```

本机验证服务：

```bash
curl -sS http://127.0.0.1:5178/
curl -sS http://127.0.0.1:8318/api/health
```

验证需要认证的 API 时，使用服务器环境中的真实 Token：

```bash
curl -sS \
  -H "Authorization: Bearer $API_AUTH_TOKEN" \
  http://127.0.0.1:8318/api/market/snapshot
```

## 验证

```bash
python3 -m unittest backend.tests.test_market_logic -v
cd frontend && npm run build
cd frontend && npm run test:e2e
```

### 运维速查
```bash
#查看部署日志
ssh root@154.219.120.25 "tail -30 /root/gold-analysis-web/deploy.log"

#查看 webhook 日志
ssh root@154.219.120.25 "tail -30 /root/gold-analysis-web/webhook.log"

#手动触发部署
ssh root@154.219.120.25 "bash /root/gold-analysis-web/deploy.sh"

#重启 webhook 服务
ssh root@154.219.120.25 "systemctl restart gold-webhook"

#查看服务状态
ssh root@154.219.120.25 "systemctl status gold-webhook"
```

更多说明见 `docs/`。
