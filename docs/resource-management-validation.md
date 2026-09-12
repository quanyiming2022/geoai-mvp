# 资源管理与 Workspace 助手续接验收

验收日期：2026-09-12。基于 `6921606`，分支 `feat/p9-real-model-worker`。
本轮原始验收后保持未提交；现按用户授权归档为 `v0.2.0-p9c.1`，后续工作流修复及重新验收见 [版本记录](release-v0.2.0-p9c.1.md)。未进入 P10 / P11。

## 交付范围

### 影像资产

- `/control/rasters` 提供影像库 Master–Detail、名称搜索、状态/CRS/上传日期/引用情况筛选，以及真实影像元数据。
- `raster_assets` 保留原始存储身份，`project_assets` 建立项目引用及项目别名。添加已有影像不复制 TIFF、COG 或缩略图，不重复处理。
- 可访问的同 checksum 影像在上传阶段提示复用，避免重复写入和处理；不向无权用户泄露其他资产存在性。
- 项目 editor/owner 可维护项目引用与别名；正式名称/全局删除由资产 owner 或平台管理员管理，API/SQL 检查有效。
- 移除项目引用与删除资产分开。仍有项目引用时阻止全局删除，显示真实引用数量。
- 资产删除采用软删除，历史执行所需原始文件、COG 与身份信息保留；本轮不实现物理清理策略。
- 当前列表有 200 条上限，并明确显示上限；未实现无限滚动。

### 结果资源

- 结果名称/描述、详情、几何编辑、单结果导出与软删除。
- 顶点拖动、补充/删除顶点；保存才持久化，取消不写数据库。未新增 split/merge。
- `geometry` 保留原始 Prediction，`current_geometry` 保存成果编辑；`result_revisions` 追加 before/after、操作人、时间、操作类型。
- 乐观 revision 冲突检测；viewer 不可修改/删除。原有 review_actions 审计继续保留。
- 删除选中成果会移除地图几何、清除选择与过期属性。Job、snapshot、预测证据和审核历史不删除。
- 单结果导出使用当前名称、当前几何，并包含 source_job_id、model_name、model_version、checkpoint_digest 等来源信息。

### 本轮菜单与助手修正

- 影像行：显示/隐藏、创建视觉样例、`…` 在同一行；影像名称负责定位。四类资源菜单删除重复“定位到地图”。
- 助手 Enter 发送、Shift+Enter 换行，兼容中文输入法；历史用户消息可编辑重发。
- 语言请求支持停止和迟到响应隔离；已提交的 durable Job 使用现有确认取消流程。
- 新建对话将当前会话归档到本机历史，可恢复；收起不清空会话。保留一个“收起助手”控件。
- 手动提取流程继承所选影像/AOI/样例。小 AOI 由 source-pixel coverage 检查自动生成窗口；大 AOI 完整扫描仍受能力限制；明确局部测试才要求地图选点。
- 地图选点定位目标影像与 AOI 的交集，AOI 外点击显示错误，成功后恢复原对话。输入窗口与有效 AOI 分别显示。
- 缺 AOI 提供“在地图上绘制 AOI”。AOI/样例创建改为前端原地保存，继续使用原有后端 API；不再通过重定向重建工作区。保存后返回新对象，继续原 pending intent。
- 真实 Worker 允许样例与目标影像来自不同资产；样例选择器标明来源。P8 Mock 同源限制保留。

## 验证结果

所有运行均在本机 macOS arm64；真实模型请求从本地平台调用已有 LAN GPU Worker。

| 检查 | 结果 | 本地证据 |
|---|---|---|
| Backend tests | PASS，140 | `artifacts/navigation-final-backend.log` |
| Frontend tests | PASS，6 | `artifacts/navigation-final-frontend.log` |
| Typecheck / lint | PASS | `artifacts/navigation-final-typecheck.log` / `navigation-final-lint.log` |
| Next.js / Docker web build | PASS | `artifacts/navigation-final-build.log` |
| P8 全流程 | PASS | `artifacts/resource-p8.log` |
| 共享资产与结果管理 E2E | PASS | `artifacts/resource-management-e2e.log` |
| P9 HTTP synthetic Worker | PASS | `artifacts/resource-p9-tile.log` |
| AOI/Prompt CRUD、回滚、运行中 snapshot | PASS | `artifacts/resource-spatial.log` |
| P9C 本地 LLM → 确认 → Mock / 权限 | PASS | `artifacts/resource-p9c.log` |
| 语言请求取消 HTTP | PASS | `artifacts/assistant-stop-http.log` |
| 小/整窗/超限/边缘 AOI、真实 smoke | PASS | `artifacts/small-aoi-acceptance.json` |
| 不同资产的真实 SkySense++ 任务 | PASS | `artifacts/cross-asset-real-proof.json` |
| 迁移前 14 个 Job snapshot | 完全一致 | `artifacts/resource-final-evidence.json` |

资源 E2E 包括第二项目复用相同 COG、原项目 unlink 后第二项目仍可运行、引用阻止删除、无引用软删除、viewer 拒绝、历史 Job 可读、结果 metadata/geometry/delete revision、原始 prediction 未变、当前几何及来源导出。

真实跨资产验证：support 为原 SPOT6；query 为同一原数据以原分辨率读取的独立 512×512 GeoTIFF（正确地理变换，非 resize）。资产及文件不同，真实任务成功，AOI 外 PostGIS 结果数为 0。这是工程跨资产验证，不是第二景跨场景泛化验收。SkySense++ 建筑能力仍未判定通过。

## 浏览器验证

实际使用隔离普通 owner 账号，在 1440×900 与 1920×1080 验证：

- 新建对话 → 历史恢复；编辑旧消息 → Enter 重发 → 停止。
- 选中 AOI → 手动流程自动带入 → 小范围自动窗口 → 下一步可用。
- 明确局部测试 → 点击 AOI 内地图 → 窗口回传、流程可继续。
- 无 AOI → 助手提供绘制 → 原地保存 → 自动恢复同一目标的确认卡。
- 助手地图选择时缩小，选完自动恢复；地图/对象面板仍可操作。
- 结果几何取消不写入、保存追加 revision；删除选中结果后列表/地图/属性同步。

本地截图：

- [小 AOI 自动覆盖（1440）](../artifacts/manual-aoi-auto-1440.png)
- [历史对话恢复（1440）](../artifacts/assistant-history-1440.png)
- [历史对话恢复（1920）](../artifacts/assistant-history-1920.png)
- [手动地图选点成功（1920）](../artifacts/manual-map-selected-1920.png)
- [创建 AOI 后续接（1920）](../artifacts/assistant-aoi-resumed-1920.png)
- [助手选点后续接（1440）](../artifacts/assistant-map-resumed-1440.png)
- [影像库（1440）](../artifacts/resource-library-1440.png)
- [影像库（1920）](../artifacts/resource-library-1920.png)
- [结果删除后（1440）](../artifacts/result-deleted-1440.png)
- [结果删除后（1920）](../artifacts/result-deleted-1920.png)

截图/运行输出位于 git-ignored 的本地 artifacts。源码、迁移、测试和文档按用户最新授权提交，运行 artifacts 继续本地保留。

## 数据与模型保护

应用迁移 140/150/160；未改写旧 Job snapshot。清理仅限已授权隔离账号、项目和测试对象；迁移后用户新增的 6 个任务未触碰。
SkySense++ adapter、RGB/mask preprocessing、slot、query-half、Worker contract、生产阈值及四组 benchmark 均未修改。本轮没有实现大 AOI tiling/stitching、额外模型或 P10 试验。
