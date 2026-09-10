# GeoAI Platform
唯一仓库：https://github.com/quanyiming2022/geoai-mvp
本地目录：`/Users/quanyiming/Projects/geoai-mvp`。GitHub 仅托管代码；所有运行及验收在 Mac 本地完成。
P0 基础设施、P1 Auth / Projects 和 P2 地图工作空间已实现。验收记录见 `docs/p0-validation.md` 和 `docs/p1-validation.md`。后续阶段仅在前一阶段验证并推送后开始。

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
.venv/bin/python scripts/migrate.py
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
.venv/bin/python scripts/acceptance_p1.py
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

## 账号与项目
打开 `/login` 注册本地账号或登录。当前开发配置自动确认邮箱，不发送外部邮件。
在 `/projects` 创建项目；项目所有者使用对方的账号 UUID 添加查看者或编辑者。
账号 UUID 显示在项目列表页。所有者管理成员，编辑者修改内容，查看者只读。
客户端不接收 Supabase service key；业务访问经 FastAPI 和用户作用域 Repository，数据库 RLS 独立限制权限。
会话使用 HttpOnly Cookie，在访问令牌过期前续期；退出撤销刷新会话并清除 Cookie。
Supabase 已签发的访问 JWT 按其原到期时间失效，项目成员撤销由数据库立即生效。
HTTPS 私有化部署设置 `GEOAI_COOKIE_SECURE=true`；本机 HTTP 默认 false。

迁移文件由 `pnpm dlx supabase@2.81.3 migration new <name>` 创建。
`scripts/migrate.py` 只连接现有 Supabase 数据库，使用事务、锁和 SHA256 记录；已执行迁移不可改写。
不用 `supabase start`，避免启动第二套数据库。私有权限函数仅用于避免递归 RLS，不暴露为 Data API RPC。

## 地图工作空间
项目列表中的项目卡片进入 `/projects/<id>/workspace`，项目信息与成员通过右上角链接管理。
默认地图是离线 WGS84 经纬参考网，不请求外部地图服务；支持拖动、缩放、坐标显示和重置。
MapLibre GL 6.9.0 的 worker 与共享模块由构建脚本从锁定依赖复制到 public/maplibre，Docker 同步携带这些文件；生成文件不提交 Git。
MapLibre 的 BSD 3-Clause 许可证保留在 docs/licenses/maplibre-gl-6.9.0.txt。工作空间权限回归：`.venv/bin/python scripts/acceptance_p2.py`。
