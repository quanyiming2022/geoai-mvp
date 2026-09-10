# GeoAI Platform · P0
唯一仓库：https://github.com/quanyiming2022/geoai-mvp
本地目录：`/Users/quanyiming/Projects/geoai-mvp`。GitHub 仅托管代码；所有运行及验收在 Mac 本地完成。
当前只做基础设施，无登录、业务地图或 GeoExtract 页面。P0 本机验收已通过，见 `docs/p0-validation.md`。

## 本地准备
使用 Node 24.21.0（`.nvmrc`）、pnpm 12.3.4（Corepack）、Python 3.12、Docker Compose。
不使用 WSL 或 sudo npm。首次安装需要网络，镜像/依赖缓存后基础运行不依赖云账号。

```sh
cd /Users/quanyiming/Projects/geoai-mvp
nvm use
corepack enable
pnpm install --frozen-lockfile
python3.12 -m venv .venv
.venv/bin/python -m pip install -r services/api/requirements-dev.txt
.venv/bin/python scripts/init_env.py
sh scripts/compose.sh config --quiet
sh scripts/compose.sh up -d --build
sh scripts/compose.sh exec -T db psql -U postgres -d postgres -c 'SELECT version(); SELECT PostGIS_Version();'
```

`init_env.py` 生成本地随机密钥，拒绝覆盖已有 .env；不要直接使用上游示例密码。
真实密钥只放忽略的 `.env` / `.env.local`，不能粘贴到日志、PR 或浏览器配置。
Web 仅接收服务器内部 API 地址。完整 Compose 配置会展开密钥，应使用 `config --quiet`。

## 检查
```sh
pnpm build
pnpm typecheck
pnpm lint
pnpm test
.venv/bin/python -m pytest -c services/api/pyproject.toml services/api/tests
.venv/bin/ruff check services/api scripts
.venv/bin/python scripts/check_upstream.py
.venv/bin/python scripts/acceptance.py
```
最后一条执行真实服务检查及持久化重启；服务不可用会失败，不会伪装成通过。
打开本地 Web（端口见 `.env.example`）验证页面及 `/api/health`。
查看 `docs/p0-validation.md` 获取本次实际结果。CI 只做静态检查，不能代替本地验收。

架构：Next.js → FastAPI → Repository / ObjectStorageProvider / ComputeProvider → ModelAdapter。
Supabase 提供唯一 PostgreSQL + PostGIS、Auth、PostgREST、Realtime、Storage、Studio。
Redis 协调后台工作，Raster Worker 在 P0 仅验证 GDAL/COG 能力并发送心跳。
详细上游来源、许可证和持久化设计见 `docs/infrastructure.md`。

## 本机兼容性说明
macOS shell 已通过官方 nvm 用户级安装 Node；Homebrew nvm bottle 在本机失败，因此未依赖它。
若旧版 Docker BuildKit 拉取 token 超时，先执行 `docker pull python:3.12.12-slim-bookworm`
和 `docker pull node:24.21.0-bookworm-slim`，再重试构建。
Linux arm64 的 Rasterio 1.4.3 需要源码构建；API/Worker 镜像包含 GDAL 开发库。
首次编译较慢，后续由 Docker 缓存复用。
仅检查官方基础设施可运行 `scripts/acceptance.py --infrastructure-only`，这不是完整 P0 验收。
