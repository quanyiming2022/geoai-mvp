# GeoAI Platform
唯一仓库：https://github.com/quanyiming2022/geoai-mvp
本地目录：`/Users/quanyiming/Projects/geoai-mvp`。GitHub 仅托管代码；所有运行及验收在 Mac 本地完成。
P0 至 P8 Mock GeoExtract 闭环已实现并通过本机验收。记录见 `docs/p0-validation.md`、`docs/p1-validation.md` 和 `docs/p8-validation.md`。真实模型/GPU 阶段尚未启用。

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

## 影像上传
工作空间支持 owner/editor 上传带 CRS 的 GeoTIFF；viewer 可查看和下载。
浏览器将文件流式发送至同源接口，FastAPI 在磁盘暂存、校验 TIFF/CRS 和 SHA256，再通过 ObjectStorageProvider 写入私有 bucket。
默认上传上限 512 MiB（MAX_UPLOAD_BYTES），同时最多处理两个上传；Storage 上限由 STORAGE_FILE_SIZE_LIMIT 配置。
上传接口绕过 Next proxy 的请求体复制，续期在 route handler 内进行，真实 12 MiB 文件已验证。
原始文件保持不变，COG 转换在 P4 完成。测试文件由 `.venv/bin/python scripts/make_fixture.py` 本地生成，不提交数据。
验收：`.venv/bin/python scripts/acceptance_p3.py`。下载链接按成员权限签发，60 秒有效。
若元数据写入响应中断，API 先按生成的 asset_id 核对；确认成功返回记录，无法确认则返回 registration_uncertain 并保留对象，避免误删已提交文件。此时先刷新影像列表，保留的未登记对象可在恢复后按返回 asset_id 排查，不自动删除不确定数据。

## Raster Worker 与 COG
上传后 Worker 自动处理，状态为等待处理 → 正在处理 → 可用 / 处理失败；失败时 owner/editor 可重试。
原始文件不变。Worker 生成 COG、缩略图并记录尺寸、波段、dtype、nodata、原始 CRS、分辨率、WGS84 bbox/PostGIS footprint。
默认限制 10 亿像素和 300 秒处理时间，通过 MAX_RASTER_PIXELS / RASTER_TIMEOUT_SECONDS 调整。当前地图支持 Web Mercator 有效纬度内、不跨日期变更线的影像；超出范围会明确失败。
任务在独立进程执行，父进程在超时时终止进程并清理暂存目录；Redis 心跳失败不影响超时监管。
地图通过用户权限校验后的 XYZ 接口读取短效内部 COG 签名地址，使用 Range + WarpedVRT 重投影，范围外像素透明。
16-bit / float 显示使用影像缩略样本计算的统一分位数范围，避免每个瓦片单独拉伸产生接缝。支持现有 RGBA / 灰度+alpha。
验收：`.venv/bin/python scripts/acceptance_p4.py`。PNG 瓦片不携带 GeoTIFF 地理元数据，其定位由 XYZ 坐标确定。

## 图层与 AOI
工作空间可切换影像显隐、调整透明度。所有者和编辑者可点击两个对角点绘制矩形，或依次点击至少三个顶点绘制多边形，填写名称后保存。保存后结束绘制；查看者只读。
AOI 存入 PostGIS Polygon，数据库验证闭合、有效性、面积、顶点数量及坐标范围；当前不支持跨日期变更线。API 通过已验证身份设置事务内 authenticated 角色，数据库 RLS 独立生效。
验收：`.venv/bin/python scripts/acceptance_p5.py`。

## Visual Prompt
在可用影像内绘制矩形或多边形样例，选择源影像并填写名称、类别和描述。类别与描述仅保存为元数据。
生成的 support image 与二值 support mask 均为 GeoTIFF，保留源 CRS，使用完全一致的尺寸和 transform；掩膜为 0/1，并排除无效像素。最长边 512 像素，采样窗口最多 400 万源像素，最多 16 波段，同时最多两个裁剪请求。旋转影像按实际像素覆盖范围验证，越界或无有效目标像素会拒绝。
样例产物在私有 Storage 保存，下载按当前项目成员权限签发短效链接。确定失败时清理新对象；数据库结果不确定时保留，避免删除已提交样例。
验收：`.venv/bin/python scripts/acceptance_p6.py`。实现依据 [Rasterio geometry window/mask](https://rasterio.readthedocs.io/en/stable/api/rasterio.features.html) 与 [resampling](https://rasterio.readthedocs.io/en/stable/topics/resampling.html)。

## 任务系统
任务记录保存在 PostgreSQL，Redis 仅提供有界通知；通知丢失时 Worker 仍扫描数据库恢复排队任务。创建使用项目与创建者作用域的幂等键。状态为 queued/running/succeeded/failed/cancelled，数据库拒绝绕过 API 的非法状态迁移。
任务与 Raster 分别在独立进程执行，先检查本地超时，再访问网络；启动失败清理进程句柄与暂存目录。claim token 和状态条件阻止旧尝试覆盖取消或新尝试；Worker 中断后的陈旧任务转为失败，可由编辑者重试。
P7 用 Mock 诊断验证 ComputeProvider。项目页面自动轮询状态，所有者/编辑者可运行、取消或重试，查看者只读。
验收：`.venv/bin/python scripts/acceptance_p7.py`，包括并发幂等、SQL/RLS、取消竞争、Redis 重启和 Worker 恢复。

## Mock GeoExtract 闭环（P8）
在工作空间选择已保存的 Visual Prompt 和源影像内的 AOI，运行 Mock GeoExtract。Worker 读取实际样例影像/掩膜和 AOI 影像窗口，经 ComputeProvider 调用 MockAdapter，将模拟概率与 AOI 有效像素掩膜相交，再按真实像素坐标转换为 WGS84 候选多边形。
地图与任务列表自动更新。点击候选可跳转审核，或在下方接受/排除；原始预测几何不可修改，审核历史由数据库触发器记录。GeoJSON 导出只包含已接受结果，携带源影像、任务、模型版本和生成时间。历史任务可分页浏览，按任务完整查看候选。
当前为 **mock-v1 测试结果**，不代表真实遥感识别。P8 不启用 SkySense++、GPU 或任何付费服务。AOI 仍采用有界窗口（最多 400 万源像素、最长边 512 输出像素），大范围分块推理属于后续阶段。
完整验收：`.venv/bin/python scripts/acceptance_p8.py`；包括新账号、项目、上传、COG、样例、AOI、任务、模型、polygon、审核、Next GeoJSON 下载以及直接 SQL/RLS/审计检查。

## P9 模型服务器配置（进行中）

管理员可在 `/settings/models` 配置模型版本与 LAN HTTP 端点。GPU / 权重未就绪时保持端点禁用，不影响 P8。配置步骤见 [手动配置说明](docs/p9-model-endpoint-setup.md)，长期产品约束见 [GeoExtract 产品方向](docs/geoextract-product-direction.md)。当前 fake-real Worker 只验证真实 HTTP 通道，不代表 SkySense++ 推理接入完成。
