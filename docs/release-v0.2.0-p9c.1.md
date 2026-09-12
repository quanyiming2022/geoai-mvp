# v0.2.0-p9c.1 — P9C Workspace / Resource Hardening

日期：2026-09-12。开发分支：`feat/p9-real-model-worker`。

## 版本定位

这是 **P9C 加固预发布版本**，汇总语言助手交互、单窗口 AOI 范围判断、影像资产复用与结果管理。

- P8：已有稳定基线 `v0.1.0-p8`，回归继续通过。
- P9B：真实 SkySense++ 工程集成通过；建筑跨区域泛化与无关场景误检问题仍存在，模型能力未判定通过。
- P9C：本地 LLM 规划 → 用户确认 → 既有任务执行；支持手动工作流并行使用。本次修正对话续接与资源管理。
- P10 / P11：未开始。本版本不含尺度诊断、大范围 tiling/stitching、multi-shot 或语言条件像素分割。

根目录与 Web package 的版本均为 `0.2.0-p9c.1`。本版本不修改 main，不覆盖 P8 tag。

## 本次工作流修复

绘制 AOI 现在是当前提取工作流的临时步骤：隐藏但保留原表单，保存或取消后返回“分析范围”，保留影像、视觉样例、模型和 entire-AOI/local-test 选择。成功创建后只替换 AOI，按当前模式重新计算覆盖/等待地图测试点。

关闭工作流、改变影像/AOI/执行范围时清除临时蓝色模型窗口和选点模式。异步地图响应通过 epoch 校验，旧响应不再重建关闭后的窗口；coverage 请求在失效/卸载时忽略迟到结果。绿色 AOI 与已发布成果保留。

## 本轮重新运行的验证

| 项目 | 结果 | 本地日志 |
|---|---|---|
| Backend | 140 PASS | `artifacts/release-backend.log` |
| Frontend | 6 PASS | `artifacts/release-frontend.log` |
| Typecheck / lint / build | PASS | `artifacts/release-typecheck.log`, `release-lint.log`, `release-build.log` |
| 固定依赖检查 | PASS | `artifacts/release-lockfile.log` |
| P8 + 影像/结果资源 E2E | PASS | `artifacts/release-resources.log` |
| AOI/Prompt CRUD、回滚、snapshot | PASS | `artifacts/release-spatial.log` |
| P9 HTTP 单瓦片 / GIS / 审核导出 | PASS | `artifacts/release-p9-http.log` |
| HTTP Worker deterministic/cancel | PASS（synthetic） | `artifacts/release-worker-contract.log` |
| P9C 本地 LLM 确认执行 | PASS | `artifacts/release-p9c.log` |
| Agent context/权限/确认归属 | PASS | `artifacts/release-agent-api.log` |
| 真实 SkySense++ 小/整窗/边缘 AOI | PASS | `artifacts/release-real-smoke.log` |
| 整范围/局部绘制保存、取消、返回、关窗 | PASS（浏览器） | `artifacts/release-workflow-browser.log` |

浏览器测试脚本：`scripts/acceptance_workflow_browser.py`。依赖 `acceptance_small_aoi.py setup` 生成的隔离普通 owner fixture 和已经登录的 `agent-browser --session small-aoi`，在 1440×900 与 1920×1080 验证；不提交额外模型任务。

- [整个 AOI 绘制后返回](../artifacts/workflow-return-full-1440.png)
- [局部测试绘制后返回](../artifacts/workflow-return-local-1920.png)
- [关闭后清除蓝框](../artifacts/workflow-closed-1920.png)

构建期间曾使浏览器旧页面短暂失效；服务稳定后已重新登录并完整重跑通过。未将那次失败标为通过。

完整资源管理与助手验收见 [resource-management-validation.md](resource-management-validation.md)。测试数据仅使用已授权隔离账号/项目，完成后清理。真实权重、影像、凭据与 artifacts 不进入版本库。
