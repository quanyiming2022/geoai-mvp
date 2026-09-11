# P9B 实际模型验收与后续顺序

用户于 2026-09-11 调整优先级；此顺序覆盖此前先做辅助样例的安排。

1. AOI / Visual Prompt 名称与描述编辑：清单更多菜单，owner/editor，保留几何、文件与任务关联。
2. SkySense++ 真实 GPU 单 Tile 推理。
3. 四组模型能力验收：same-image、same-class cross-image、unrelated-query、wrong-prompt。
4. 归档概率分布、前景比例、耗时、显存、身份、可视化。
5. P9B 通过后验收 Language Draft → User Confirm → Real SkySense++ Job → Result。
6. Assisted Visual Prompt。
7. P11 AOI tiling/stitching。

## 当前阻塞

用户确认 GPU 服务器与权重仍未就绪。没有真实模型结果、VRAM 或性能数据可报告；不使用 synthetic / Mock 替代，不标记 P9B 完成。已有本地 Qwen → 确认 → Mock 端到端验收仅作为回归基础，不满足第 5 项。

## 四组 fixture

所有支持 RGB、支持 binary mask、query RGB 均为 512×512；query 必须为 source-resolution window。保留项目、影像、窗口坐标、prompt、输入摘要与标注来源。

| 场景 | 对照目的 |
| --- | --- |
| same-image | 支持与查询为同一图块，验证预处理、掩膜语义及 query-half 映射 |
| same-class cross-image | 不同影像中的同类目标，验证跨影像转移 |
| unrelated-query | 支持目标不出现在查询中，检查误报 |
| wrong-prompt | 保持 query 不变，换成错误类别的真实 support/mask，与正确 prompt 成对对照，检查是否真正依赖样例 |

每组需要人工确认语义与参考区域；不能只用 RGB 合成颜色或随机掩膜宣称模型有效。固定 seed 重跑检查稳定性。不预设所有遥感类别通用的准确率承诺。

## 必须保存的证据

- probability GeoTIFF、binary mask、有效像素 mask、PostGIS/GeoJSON 结果。
- probability_mean/std/min/max、分位数或直方图、foreground_ratio、mask_area、threshold。
- runtime_ms、gpu_memory_peak（记录单位；不可获取时明确 null）、seed、slot_id。
- endpoint_id、model_release_id、模型名称/版本、checkpoint_digest、模型源码 commit、runtime/CUDA/GPU 身份。
- support RGB/mask、query RGB、概率热图、mask 叠加、MapLibre 结果截图。
- 对比解释：是否复现支持目标、跨影像是否转移、无关 query 是否误报、错误 prompt 是否改变语义输出。

恒定概率或各组近乎相同输出不能判为成功。接近 0% / 100% 前景必须单独检查，不能凭 HTTP 200 通过；unrelated-query 的空前景可能符合真实负例，但仅此不能证明模型能力，仍必须通过正例与错误提示对照。

## 部署入口

管理员在 `/control/models` 配置实际模型版本、checkpoint 与局域网节点。服务器未准备好时不启用空节点。远端启动与依赖限制见 `services/model-worker/README.md`。保留 research_only，不用于默认商业生产模型。
