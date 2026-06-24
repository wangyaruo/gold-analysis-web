# 部署指南

本任务仅提供部署文档和 Docker 文件，不执行实际部署。

## 环境变量

复制 `.env.example` 并设置生产值：

```bash
cp .env.example .env
```

生产必须设置：

```bash
API_AUTH_TOKEN=<strong-random-token>
GOLD_API_KEY=<provider-key>
NEWS_API_KEY=<newsapi-key>
APP_ENV=production
```

同时建议在 `config.yaml` 中设置：

```yaml
security:
  allow_insecure_dev_token: false
```

## Docker Compose

```bash
docker compose up --build
```

服务：

- Backend: `http://127.0.0.1:8318`
- Frontend: `http://127.0.0.1:5173`

## 生产注意事项

- 使用 HTTPS 终止代理。
- 将 `API_AUTH_TOKEN`、`GOLD_API_KEY`、`NEWS_API_KEY` 放入部署平台 secret manager。
- 配置 CORS 只允许正式前端域名。
- 为后端结构化日志接入集中日志系统。
- 对价格 API 设置速率限制和配额告警。
