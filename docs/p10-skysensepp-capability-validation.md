# P10 — SkySense++ Model Capability Validation

**状态：P10 诊断完成（180 次正式真实 GPU 推理），STOP。**

**归因分类：MIXED。最终模型判定：RESEARCH_ONLY。**

P9B 工程集成 PASS 保持不变；本轮证据不足以批准稳定的通用建筑提取能力。没有进入 P11，没有修改模型、adapter、normalization、slot、query-half、Worker contract、生产阈值或产品 UI。

## 1. 冻结基线与实验边界

- Checkpoint SHA256：`32a08982baea125f60feb95fe0a04dfe450ec9c12ee846384cbadd8ff6c5661c`。
- 模型源码：`cb0c6b774471ad3314354041c8fa6aae7d49a9bb`；版本 `research-v1`；seed 42；slot 24。
- 冻结清单：`artifacts/p10/baseline-manifest.json`。原 A/B/C/D 和“建筑-基准01”字节未改。P1/P2/P3 是独立离线 WHU 实验样例，不替换平台样例。
- 正式输入及矩阵在第一次成功推理前冻结于 `artifacts/p10/whu-formal-v1/config.json` 和 `input-sha256.json`。
- 统一主阈值 **0.5**。0.3/0.7 仅保存分析产物，未用于挑选模型通过条件。
- 最初本地预检发现预览 mask 是 0/255；传输时无损转换为现有合同要求的 0/1，未发起该次无效请求、未改任何 Worker 实现。

## 2. 几何与 GT 准入

WHU 航片：两个 2,304×2,304 m 区域，EPSG:2193，7680²、0.3 m 地理底图，来自官方 0.075 m 整幅影像的显式 4×金字塔。影像与 GT 的 CRS、affine、尺寸、extent、valid mask 全部一致；从原官方矢量重新栅格化后与底图 GT **逐像素相等**。GT 是人工建筑 footprint，不是模型预测。

正式 query 在每区域设置两个固定中心（相对源中心 ±80m），各派生 1/1.5/2/3/4m、512²窗口。全部在源边界内，不 padding。少量原始 NoData 明确保留并从所有评分中排除；有效像素数随实验保存。相邻中心窗口存在重叠，不能当成独立场景。

WHU Satellite II：4 个原始配对裁片 42、43、1551、3725。经整幅官方标签唯一匹配和矢量栅格化一致性验证，派生坐标 EPSG:3395；原图/标签像素不变。**GSD_METADATA_CONFLICT**：网页约2.7m与文件几何约0.262m不一致。只做跨场景/跨域/Prompt 对照；**不加入绝对 GSD 曲线，FP/FN 面积平方米值为 null，保留像素数量**。未用冲突元数据推导尺度结论。

本轮只使用 WHU 的上述数据；已准备的 SpaceNet2 保留原样，不强行并入本轮尺度研究。详细审计见 `artifacts/p10/whu-formal-v1/geometry-audit.json`、`docs/p10/whu-input-validation.json`。

## 3. 固定 Prompt 与实验矩阵

P1/P2/P3 分别选自官方 GT 的大型建筑（1m约1847像素）、中型住宅建筑（351像素）及密集环境小建筑（161像素）。三者使用相同源影像/中心，只改变单个建筑 mask，并在每档 GSD 重新栅格化同一几何。样例未经预测筛选。P2 是住宅环境建筑，不宣称经过独立的“独栋”标注。

两个航片 wrong prompt 为植被/开阔地过渡区、裸地/开阔田块；所有尺度下与建筑 GT 零重叠。它们是确认非建筑的样例，没有独立土地利用语义 GT。卫星域另固定两个原生建筑 support（42、1551）与两个原生非建筑 control（43、3725），作为域内诊断；不替换 P1–P3。

- 航片 matched-GSD：2区域 × 2中心 × 5 GSD ×（3正确+2错误Prompt）=100次。
- 航片 cross-GSD：固定1m support→其余4档 query，及2m support→1m query，共60次。
- 卫星：4 query ×（2原生正确+2原生错误+航片P1-1m）=20次。
- 总计180次；136组同query correct/wrong配对差异。没有穷举所有模型/尺度组合。

## 4. 指标口径

表中 F1/IoU/Precision/Recall 是对应组 **pooled TP/FP/FN 的 micro 指标**，不是单例分数简单平均。背景错误、漏检面积按航片目标 GSD²换算；跨多次实验累计面积不是唯一土地面积。没有前景且没有预测时，F1/IoU保留undefined/null，不伪造1.0。完整CSV保留每次数据。

同时计算固定 **512m×512m共同地理核心区**：每档概率以固定 bilinear 规则投影到同一个1m评分网格，使用同一官方GT和五档共同有效像素。此步骤仅用于离线评分，不改生产概率链。它控制 query FOV/GT组成，但不能消除 support 分辨率/上下文变化，也不是五组独立标注。

## 5. 主尺度结果：同 GSD 正确 Prompt

每格包含3 Prompt×2中心。urban为同区域，outskirts为urban support→另一区域。

| GSD m | Urban F1 | Urban IoU | Urban共同核心 F1 | Outskirts F1 | Outskirts共同核心 F1 |
|---|---:|---:|---:|---:|---:|
| 1 | 0.1936 | 0.1072 | 0.1936 | 0.0000 | 0.0000 |
| 1.5 | 0.0364 | 0.0185 | 0.0599 | 0.0000 | 0.0000 |
| 2 | 0.0501 | 0.0257 | 0.0974 | 0.0000 | 0.0000 |
| 3 | 0.0145 | 0.0073 | 0.0873 | 0.0889 | 0.0000 |
| 4 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

**在已测1–4m中，1m最好。** Urban完整窗口 F1=0.1936、IoU=0.1072；共同核心同样以1m最高。不能推断1m是全局最优，也不能推断小于1m的结果，因为本轮没有该尺度试验。证据不支持“1m明显太细，调粗即可修复”。

Outskirts在3m完整窗口出现0.0889，但共同核心仍为0：新增物理视野包含更多建筑，不能称为同一任务的尺度精度提升。

### 固定 support 的 cross-GSD 对照

| Urban support→query m | 完整 F1 | 共同核心 F1 |
|---|---:|---:|
| 1>1 | 0.1936 | 0.1936 |
| 1>1.5 | 0.1473 | 0.1387 |
| 1>2 | 0.1022 | 0.1326 |
| 1>3 | 0.0758 | 0.1430 |
| 1>4 | 0.0935 | 0.1672 |
| 2>1 | 0.0599 | 0.0600 |
| 2>2 | 0.0501 | 0.0974 |

固定1m support在4m query共同核心仍有0.1672，而4m support→4m query为0。**仅仅匹配 support/query GSD 并不保证更好**；support变粗、目标mask变小会与语义泛化共同作用。此证据不支持单一 SCALE_DOMINANT 解释。

## 6. 同类 Prompt 稳定性

Urban、1m、两中心：

| Prompt | F1 | IoU | Precision | Recall |
|---|---:|---:|---:|---:|
| P1 | 0.4443 | 0.2856 | 0.9145 | 0.2934 |
| P2 | 0.0404 | 0.0206 | 0.8787 | 0.0207 |
| P3 | 0.0211 | 0.0107 | 1.0000 | 0.0107 |

P1与P3 F1相差约42.32个百分点；P2/P3在≥1.5m的 matched-GSD 组均为0。总体偏向漏检，不能把P1表现代替三个Prompt的稳定性。三样例的建筑大小/形状/场景语义存在混杂，只能判定该样本上的强Prompt敏感性，不能单独归因为模型“完全不使用Prompt”。

## 7. Cross-region / cross-scene / cross-domain

航片1m从urban到outskirts，pooled F1 **0.1936→0**，下降19.36个百分点。两个区域目标密度差异极大、窗口重叠，不能将此描述为无混杂的纯域迁移损失；共同核心的GT稀疏且漏检严重。

| 卫星对照 | 次数 | F1 | IoU | Precision | Recall | FP像素 | FN像素 |
|---|---:|---:|---:|---:|---:|---:|---:|
| same_image | 2 | 0.4204 | 0.2661 | 0.5606 | 0.3363 | 4273 | 10759 |
| cross_scene | 6 | 0.5728 | 0.4014 | 0.5867 | 0.5596 | 17900 | 20002 |
| aerial_to_satellite | 4 | 0.5484 | 0.3778 | 0.6279 | 0.4867 | 8889 | 15815 |

卫星 cross-scene 包括一对相邻裁片和更远裁片；它的0.5728高于same-image的0.4204，**不代表迁移提升精度**，因为query组成不同且样本极小。航片P1→卫星0.5484表明部分跨域响应存在，仍有明显漏检和边界/背景误检。所有卫星结果标记GSD_METADATA_CONFLICT。

## 8. Correct / wrong Prompt 是否改变建筑预测

每次使用完全相同query，保存 `wrong-minus-correct.npy` 与空间二值差异指标。

- 卫星16组对照：建筑GT上平均概率 **0.4451→0.1336**；平均建筑召回 **0.4844→0**；全图平均概率绝对差约0.3108，二值空间差异约36.88%。错误Prompt明显抑制建筑响应，并可能转向田块/背景。
- Urban60组对照：GT上平均概率 **0.04734→0.00487**；正确Prompt本身经常低响应，两者F1差异中位数为0，不能据此宣称语义稳定。
- Outskirts60组对照：全图平均绝对差约0.2359，wrong prompt常产生开阔地前景；这并不等于其“建筑精度高”，也不要求wrong prompt的全图前景必然下降。

因此：**模型确实会受Prompt控制，但正确建筑Prompt的泛化与尺度鲁棒性不足。** 不支持“完全忽略Prompt”，也不能由明显差异直接推出实用精度达标。

## 9. 背景/纹理误检

Outskirts、matched-GSD正确建筑Prompt；面积为每次实验平均，单位m²，p95/p99为每张有效像素分布分位数的组均值。

| GSD | 前景比例 | prob mean | p95 | p99 | 平均FP面积 | 平均FN面积 |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 0.00005 | 0.01309 | 0.07263 | 0.13920 | 12.83 | 142.00 |
| 1.5 | 0.00059 | 0.05889 | 0.17711 | 0.24675 | 346.12 | 212.62 |
| 2 | 0.00000 | 0.01524 | 0.06637 | 0.13331 | 0.00 | 472.00 |
| 3 | 0.00384 | 0.01804 | 0.08840 | 0.17731 | 8454.00 | 3837.00 |
| 4 | 0.00357 | 0.01149 | 0.05343 | 0.17214 | 14960.00 | 31744.00 |

误检没有随GSD单调降低。4m P1的一例FP达46,624m²，目视主要落在水塘而非建筑；与此同时urban的4m响应几乎消失。没有独立土地覆盖GT，不能给出精确“农田FP面积”或证明farmland-specific机制。原SPOT6 C的农田误检仍作为独立历史证据，未被新样本替换。当前不是简单的全域 FOREGROUND_BIAS，而是输入尺度/Prompt/背景结构共同相关的失败。

## 10. 最终七问与决定

1. **最佳已测区间：1m**，不是已证明的全局最优区间；F1/IoU仍低。
2. **1m是否偏离最优：没有此证据**。调粗整体更差，不能据此进行生产尺度适配。
3. **Cross-region下降：1m时19.36个百分点**，同时存在场景组成混杂；卫星另行报告。
4. **三个Prompt稳定：否**，1m F1为0.4443/0.0404/0.0211。
5. **Wrong Prompt抑制建筑：卫星明显，航片受正确Prompt低响应限制**；不能把背景前景数量当作建筑语义指标。
6. **纹理误检随GSD：非单调**，更粗尺度没有稳定修复，部分背景误检增大。
7. **主要归因：MIXED**，有尺度敏感性及Prompt泛化不稳定；域因果作用尚不能单独识别。

**SkySense++ for GeoExtract: RESEARCH_ONLY。** 保留研究比较价值与已经通过的工程接口；不将其认定为稳定的默认通用建筑生产模型。此选择基于量化结果，不是仅重述现有许可证标签。不进入P11，也不自动新增模型。

## 11. 运行、验证与产物

180/180真实推理成功；逐例独立重算TP/FP/FN/F1、检查概率范围与GeoTIFF/NPY一致性、检查0/1 support mask、必需文件齐全。P10离线指标测试8项通过。源数据与冻结P9B/模型文件SHA256未变。

Worker单次推理：中位 244.93ms，p95 248.01ms，范围 241.44–248.87ms；CUDA peak allocated 11501.28MiB（约11.23GiB）。这是Worker计时，不包含上传、完整GIS生产链；wall_ms另存。峰值是PyTorch allocated，不是整卡reserved/其他进程占用。Worker现有代码每请求reset peak，未改。

- 数值：`docs/p10/whu-formal-results.csv`、`whu-formal-analysis.json`、`whu-prompt-comparisons.csv`。
- 配置/审计/全部原始输出：`artifacts/p10/whu-formal-v1/`；每次有support、0/1 mask、query、GT、probability.npy/tif、pred_03/05/07、overlay和metadata。
- Prompt空间差：`artifacts/p10/whu-formal-v1/comparisons/`。
- 图例：绿色TP、红色FP、蓝色FN；`artifacts/p10/whu-formal-v1/review.html`。
- 原先44次SPOT6无GT探查：`docs/p10/preliminary-spot6-report.md`、`preliminary-metrics.csv`。不得混成正式GT精度。
- 可复现脚本：`scripts/p10/whu_formal.py`、`analyze_whu.py`；地址/ModelRelease经环境变量传入。

本次为受控小样本诊断，不是标准WHU测试集成绩。两航片区域、4卫星裁片和重叠窗口限制结论外推；公开训练集可能与模型预训练重叠，未验证。GT是footprint而非精确可见屋顶；量化结论不等于商业验收。全部生产代码、RLS、Job、adapter仍冻结。
