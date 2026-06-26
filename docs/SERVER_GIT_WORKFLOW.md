# 服务器改动与 GitHub 同步流程

## 推荐协作方式

优先在本地开发、提交并推送到 GitHub，然后由服务器 webhook 自动部署：

```bash
cd /Users/wangyaruo/Desktop/卡卡/gold-analysis-web
git status
git add <changed-files>
git commit -m "说明这次修改"
git push origin main
```

服务器会收到 GitHub push 事件，并执行：

```bash
/root/gold-analysis-web/deploy.sh
```

线上访问地址：

- Frontend: `http://154.219.120.25:5178/`
- Backend: `http://154.219.120.25:8318`

## 如果必须在服务器上改代码

登录服务器：

```bash
ssh root@154.219.120.25
cd /root/gold-analysis-web
```

先确认服务器代码状态：

```bash
git status
git rev-parse HEAD origin/main
```

如果 GitHub 可能比服务器新，先同步远程：

```bash
git pull --rebase origin main
```

修改代码后，只添加真正需要同步的文件：

```bash
git status
git add config.yaml docs/CONFIGURATION.md backend/app/api.py
git commit -m "说明这次服务器侧修改"
git push origin main
```

不要无脑执行 `git add .`。服务器目录里有日志、PID 和部署辅助脚本，通常不应该提交进 GitHub。

## 通常不要提交的服务器文件

以下文件多为服务器运行时文件或运维脚本，默认不要提交：

```text
backend.log
backend.pid
frontend.log
frontend.pid
deploy.log
webhook.log
webhook-stdout.log
deploy.sh
deploy.sh.bak-5173-to-5178
webhook-server.py
main.py
```

如果确实要版本化部署脚本，应先在本地仓库设计清楚目录位置和脱敏策略，再提交。

## 服务器部署故障排查

查看 webhook 是否收到 push：

```bash
tail -f /root/gold-analysis-web/webhook.log
```

查看部署过程：

```bash
tail -f /root/gold-analysis-web/deploy.log
```

查看服务端口：

```bash
ss -ltnp | grep -E ':5178|:8318'
```

检查接口：

```bash
curl -sS http://127.0.0.1:8318/api/health
curl -sS -H "Authorization: Bearer $API_AUTH_TOKEN" \
  "http://127.0.0.1:8318/api/market/snapshot?source=eastmoney_au9999"
```

## Git dubious ownership 问题

如果部署日志出现：

```text
fatal: detected dubious ownership in repository at '/root/gold-analysis-web'
```

执行：

```bash
chown -R root:root /root/gold-analysis-web
git config --global --add safe.directory /root/gold-analysis-web
```

部署脚本中应保留：

```bash
export HOME=/root
git config --global --add safe.directory /root/gold-analysis-web >/dev/null 2>&1 || true
```

这样 webhook 环境缺少 `HOME` 时也能正常拉取最新代码。
