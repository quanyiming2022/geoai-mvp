# GeoExtract 产品与接口演进约束

GeoExtract：**Sample-defined Remote Sensing Extraction System / 基于样例定义的遥感任意目标智能提取系统**。

产品价值是一个或少量样例定义新目标、跨影像复用、形成可审核的 GIS 斑块及客户自己的数据资产。SkySense++ 仅是 research_only Adapter，不能作为商业能力承诺或默认生产模型。

## 阶段边界

| 能力层 | 方向 | P9 状态 |
| --- | --- | --- |
| Level 1 | Visual Prompt Segmentation | 单 support + 单 source-resolution 512×512 query tile |
| Level 2 | Few-shot / Multi-shot Task Definition | 仅预留集合和版本协商，不执行多样例 |
| Level 3 | Visual + Language Semantic Binding | 未启用，未来必须由 experimental feature flag 隔离 |
| Level 4 | Time-series Monitoring + Prompt Reuse | 仅保留关系扩展方向，不实现调度或告警 |

P9 不实现大 AOI tiling/stitching、multi-shot、language binding、time-series 或 active learning。GPU / 权重尚未就绪，不将 fake-real HTTP 验证当作真实模型验收。

## Task Definition 与 Prompt Library

Visual Prompt 是持久化目标定义，不能作为一次性检索 query。界面统一使用 Visual Prompt、样例定义目标或样例引导提取，不使用 image search / 以图搜图。

现有 `visual_prompts` 已持久化 name、description、class_label、样例源影像、geometry、support image/mask、project、creator、created_at；已有 jobs.prompt_id 提供使用历史。源影像是样例证据的来源，不是未来目标影像的约束。

后续版本化 Task Definition 采用以下独立概念：

- `prompt_id` + `version`：不可变版本引用；编辑生成新版本，旧 Job 永远指向执行时快照。
- `support_examples[]`：每项包含 source raster、image/mask 对象与 digest、prompt kind、geometry/坐标系。P9 adapter 能力为恰好一个 polygon/mask。
- `negative_examples[]`：预留，P9 只接受空集合。
- `semantic_description`、`positive_text`、`negative_text`：未来字段；当前不发送给模型、不展示成已可用能力，非空执行请求应明确拒绝。
- `prompt_kind`：可演进为 polygon、box、point、coarse_mask、refined_mask。未支持类型必须拒绝，不能静默伪装成精确 mask。
- owner/project 与版本权限沿用项目 RLS；跨项目复用需要明确授权，不能根据对象 key 绕过权限。

当前 P8 Job 的同源影像复合外键是旧 Mock 工作流约束，不能复制到新的单 tile 路径。P9 新 Job 路径须分别验证 support source 与 query raster 的项目权限，让同一 Prompt 可用于不同 query raster；P8 原路径保持兼容。此项在新 Job 路径完成并测试前不得宣称跨影像运行已支持。

## Worker/API 扩展规则

当前 `request_schema_version=1` 的 HTTP contract 保留用户要求的 support_image/support_mask/query_image，且严格拒绝未知字段。版本 1 只有单样例，不通过随意增加 JSON 字段假装模型支持其他能力。

未来新增版本采用 `support_examples[]` 和 `negative_examples[]`，经 endpoint.request_schema_version 与 Adapter capability 协商；旧版本使用显式转换器读取唯一 support。任务对象和网络 wire contract 分层，避免把远端某个模型的内部输入布局固化为平台业务定义。

ComputeProvider 负责端点、鉴权、网络、超时、重试、取消；ModelAdapter 负责模型预处理、推理和输出映射。SkySense++ 的 vocabulary/slot/composite/normalization/query-half extraction 仅存在远端 Adapter。未来 GeoExtractPrototype、TerraMind、Clay、Prithvi 或专有模型使用同一平台 contract，替换模型不重写 UI。

## GIS 与反馈数据

生产结果目标包含 probability raster、binary mask、polygon、area、perimeter、confidence、source raster、模型版本/checkpoint、prompt/version、review status。必须保留原始预测与审核后几何的区别，不覆盖模型原始结果。

P8 已有持久化原始 polygon、面积、置信度、来源 metadata 与触发器生成的 reviewer/action/timestamp 审核历史；目前只支持 Accept/Reject，**尚不支持 Edit**。未来编辑使用独立 reviewed_geometry / review revision，并保存 original_prediction、prompt_id、model_release_id 和置信度快照。不能将现有 UI 状态误称为完整训练数据闭环。

新 Job 结果应记录输入/模型不可变身份、概率与二值掩膜的存储引用、源像素 window/affine/CRS、阈值、质量统计、取消尝试 token；远端迟到响应不得写入已取消或被重试替代的执行。后续 monitoring_series_id 可关联多日期 Job，但不改变 Prompt 的样例来源。

## 私有化与产品验收

数据库、对象存储、栅格数据、HTTP GPU Worker 与 Web/API 均可置于客户内网，核心功能不依赖公有云。界面优先显示目标数量、总面积、空间分布和待审核/已审核状态；模型技术指标置于详情。

新增功能优先评估：减少重新训练、减少人工标注、提高跨影像复用、直接形成 GIS 成果、积累客户数据资产。未提升任何一项的展示性 AI 功能降低优先级。
