# AOI 容量判断与助手交互修正

2026-09-12，基于 `ca47b23`，分支 `feat/p9-real-model-worker`。本地 macOS arm64 + 已注册 LAN SkySense++ Worker 验证。

## 修正

旧实现仅依据 `execution_scope=full_aoi` 拒绝请求。现在先读取当前授权 Raster 的 COG geotransform，把 AOI 顶点转换到原始 source-pixel space，再决定执行方式。Agent、旧任务草稿接口和确认接口共用同一规划逻辑。

| 请求与条件 | 行为 |
|---|---|
| 整个 AOI 可由一个可读原生窗口覆盖 | `single_tile_full_aoi`，围绕 AOI bbox 居中，必要时平移到影像边界内，自动生成窗口，直接等待确认 |
| 明确局部测试，没有地图测试位置 | `single_tile_test`，要求地图选点 |
| 整个 AOI 宽或高超过 512 source pixels | `multi_tile_full_aoi`，明确不可用，不静默降级 |

完整 AOI 仍保留 `execution_scope=full_aoi`，并不改成局部测试。模型仍读取原分辨率 512×512；输出继续使用已验证的 `prediction ∩ AOI_snapshot`。自动规划窗口不作为下一次显式局部测试的地图选点。确认前重新核对 AOI revision、源影像和窗口；变化时要求重新规划。

额外边界防护：AOI 超出影像或源影像不足 512 RGB 时，不声称完整覆盖。整数像素窗口还必须能容纳其完整像素区间；只消除小于 1e-7 source pixel 的投影往返噪声，不用缩放或放宽真实边界来伪造覆盖。接近一整窗但跨越额外像素边界的非整数对齐范围可能无法由一个整数原生窗口完整覆盖。

追加迁移只为未来任务快照补充 `query_window_pixel_offset` 和 `effective_analysis_geometry`；保留 `aoi_geometry_snapshot`、`query_window_bounds`。历史快照不重写。没有改动 SkySense++ adapter、preprocessing、slot、query-half、threshold、P9B benchmark 或 Job 执行状态机。

## 助手界面

Enter 默认发送，Shift+Enter 换行；中文输入法 composition/229 保护避免选词时误发送。输入为空、请求中或云端发送未获同意时不发送。自然语言“开始分析”确认当前待执行计划。

保持可拖动、可最小化、非模态浮窗，统一紧凑标题/状态、消息层级、单列计划摘要和输入区。计划展示“整个 AOI · 一次完整分析”，局部测试与大范围分块扫描分别说明。地图、左侧清单、右侧属性和任务栏不被锁定。

## 验收结果

- 后端 129 tests PASS；前端 6 tests PASS；typecheck、lint、Next.js production build、Docker Web/API/Worker build PASS。
- P8 全流程、P9 原生窗口、synthetic HTTP/cancellation、P9C 本地 LLM → 确认 → Mock → 审核/导出、历史 snapshot 回归 PASS。
- 旋转 geotransform、<512、恰好 512、宽超限、高超限、边缘平移、范围超出 Raster、自动窗口与地图测试位置区分、确认时 revision 变化拒绝：PASS。
- 实际浏览器 1440×900 / 1920×1080：Shift+Enter 留下换行且未发送；Enter 发送后直接生成小 AOI 确认卡，无地图点击；输入“开始分析”后真实任务完成，结果列表切换到 1 个裁剪图斑；大 AOI 正确返回分块扫描未开放。

### 真实模型工程证据

| 场景 | AOI bbox / query offset | 任务 | 结果 |
|---|---|---|---|
| 小屋顶 AOI | 18.5×19.75 px / (728,714) | `e2137749-cf39-42a8-b6eb-3fc5a6016797` | 1 图斑；248.63 ms；有效范围 probability mean/std 0.742740 / 0.042344 |
| 精确一窗 AOI | 512×512 px / (730,715) | `8ca8d901-d64b-46a6-b3e4-94b253ad0208` | 3 图斑；249.56 ms；mean/std 0.057454 / 0.089138 |
| 宽超限 | 513×100 px | 不提交 | CAPABILITY_NOT_AVAILABLE |
| 高超限 | 100×513 px | 不提交 | CAPABILITY_NOT_AVAILABLE |
| 影像边缘 | 50×50 px | 只生成草稿 | 窗口平移后完整覆盖 |

以上均为隔离项目。真实任务使用原有 research-only SkySense++，种子 57，checkpoint 不变。SQL 验证每个最终图斑减去冻结 AOI 的差集为空，两个新 snapshot 字段存在。小屋顶范围 foreground ratio=1.0 是该小范围内的统计，不代表整图模型输出恒定；整窗仍非恒定。此次是工程/范围语义验收，不改变 P9B 建筑能力 NOT PASSED 的结论。

复现：`scripts/acceptance_small_aoi.py setup|check|cleanup`。本地证据：`artifacts/small-aoi-acceptance.json`、`small-aoi-*.log`、`assistant-small-aoi-1440.png`、`assistant-small-aoi-1920.png`、`assistant-small-aoi-completed.png`、`assistant-large-aoi-blocked.png`。原影像、凭据与私有 artifacts 不提交。未进入 P10/P11。

验收结束后已清理本轮隔离项目、对应存储对象和临时普通账号，关闭隔离浏览器；保留本地证据。所有本地 Compose 服务健康。原项目、真实管理员及冻结 benchmark 未改变。
