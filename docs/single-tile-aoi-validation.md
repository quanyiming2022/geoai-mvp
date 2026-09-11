# 单瓦片 AOI 有效范围与 Workspace Agent 版本验收

2026-09-12，macOS arm64 本地平台 + 已注册 LAN SkySense++ GPU Worker。分支 `feat/p9-real-model-worker`。本轮只完成 Workspace Agent 与用户随后要求的 AOI/模型窗口约束；未进入 P10/P11。

## 交互与空间语义

- 绿色 AOI 是有效分析范围；蓝色虚线是模型输入窗口。地图选点由服务端验证：所选 AOI 必须属于当前授权项目，点击范围外返回 `请选择 AOI 内的位置`。
- 模型始终读取完整原分辨率 512×512 输入。小 AOI 不报错；在影像覆盖允许时调整窗口覆盖它。窗口超出 AOI 的像素只提供模型上下文。
- 推理后应用冻结 AOI 的像素掩膜，再在写入 PostGIS 前进行精确 polygon intersection。发布的 probability 在范围外为 nodata，binary/valid mask 在范围外为零。面积、审核和导出使用最终相交后的图斑。
- 提交时冻结 `aoi_geometry_snapshot` 与服务端计算的 `query_window_bounds`。输入快照只保存相交规则；执行后产生的 `effective_prediction_geometry` 保存于任务结果和图斑元数据，绝不回写输入快照。
- 现有无 AOI 单瓦片流程保留；SkySense++ adapter、RGB/mask、slot、query-half、阈值 0.5 和原始 P9B 四组 benchmark 未修改。
- 整个 AOI 请求仍被明确拦截，只有用户主动选择地图测试才转换为单区域测试。助手用“目前只能先分析范围内的一小块区域”说明限制，不要求普通用户填写行列号。

对话助手的状态机、权限、非阻塞浮窗、地图联动及真实任务验收见 [Workspace Agent 验收](workspace-agent-v1-validation.md)。

## 真实 GPU 对照

隔离测试项目复制已批准的建筑基准和影像，不修改原项目或四组 benchmark。

| 项目 | 结果 |
|---|---|
| 完整窗口任务 | `0e58fbe4-1895-4061-88e4-5ef964067d4f` |
| AOI 限定任务 | `8ac8fcfc-c840-4ce9-9773-ba3885c84cbc` |
| 模型 | SkySense++ research-v1，research_only |
| Checkpoint | `32a08982baea125f60feb95fe0a04dfe450ec9c12ee846384cbadd8ff6c5661c` |
| 原生窗口 | col 728 / row 714，512×512，seed 42 |
| support / mask / query 输入摘要 | 两次完全一致 |
| AOI 内 probability | 逐像素完全一致（np.array_equal） |
| AOI 外 probability / mask / valid | nodata / 0 / 0 |
| AOI 面积 | 365.365096 m² |
| 最终成果 | 1 个图斑，346.240614 m² |
| 有效像素 | 361 |
| 有效范围概率 mean / std | 0.734261 / 0.060922 |
| 有效范围 foreground ratio | 0.983380（小屋顶 AOI，不代表整图精度） |
| Worker runtime / peak GPU memory | 250.500 ms / 12,059,968,000 bytes |
| 数据库与导出范围检查 | `ST_IsEmpty(ST_Difference(result, frozen_AOI)) = true` |
| 提交后修改并删除 AOI | 任务成功，输入快照完全不变 |

相交几何使用 EWKB 写入，避免中间 GeoJSON 精度损失。AOI 成果的 GeoJSON 使用 17 位精度，原有无 AOI 输出精度保持不变。边界浮点情况下 `ST_CoveredBy` 可能返回 false，即使差集为空；验收采用严格“差集为空”，没有面积容差放宽。

这证明空间约束与工程链路正确，不意味着建筑模型能力通过。跨区域弱响应和农田误检结论保持不变，没有调整阈值来改变能力结论。

## 浏览器与回归

1440×900、1920×1080 实际浏览器验证：范围外点击被拒绝并保留 pending conversation；范围内点击自动恢复原确认卡；蓝色输入窗口与绿色有效范围分别标注；浮窗可最小化，地图和其它面板不被锁定。

| 检查 | 结果 |
|---|---|
| 后端单测 | 119 PASS |
| 前端测试 | 6 PASS |
| typecheck / lint / production build | PASS |
| P8 全链路、RLS、审核、导出 | PASS |
| P9 原生窗口与 synthetic HTTP/cancellation | PASS |
| P9C 本地 Qwen → 确认 → Mock → 审核/导出 | PASS |
| AOI/样例维护、失败回滚、运行中快照、删除历史 | PASS |
| Agent viewer/outsider/跨项目/确认归属权限 | PASS |
| 真实 GPU AOI 对照与导出 | PASS |
| 迁移前历史快照 | 11 个哈希一致，未重写 |

复现脚本：`scripts/acceptance_tile_aoi.py STATE_JSON CREDENTIAL_ENV`、`scripts/acceptance_workspace_agent.py STATE_JSON CREDENTIAL_ENV`。仅使用显式隔离项目；凭据保持本地。

本地证据：`artifacts/aoi-window-real-acceptance.json`、`aoi-window-export.geojson`、`aoi-window-{full,clipped}-{probability,mask,valid}.tif`、`aoi-natural-capability-message.png`、`aoi-outside-rejected.png`、`aoi-window-1440.png`、`aoi-window-1920.png`，以及 `final-*.log`。截图中的既有历史图斑来自先前完整窗口任务，不是本次裁剪成果；空间裁剪以对照任务、导出及差集断言为准。原始遥感数据与密钥不提交 Git。

验收清理已完成：仅删除两个明确的隔离项目、34 个对应存储对象和 1 个临时普通账号；权限脚本另建的临时账号在 finally 清理。原项目、建筑-基准01、四组 benchmark 和本地验收证据保留。检查时 API、Web、Raster Worker 与 synthetic Worker 均健康。
