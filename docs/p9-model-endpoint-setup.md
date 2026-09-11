# 局域网模型服务器配置

P8 已冻结为 `v0.1.0-p8`。P9 的真实 GPU / 权重验收尚未完成；本地 fake-real Worker 仅用于验证 HTTP 协议，不代表 SkySense++ 推理。

管理员账号为 `qym57@outlook.com`。在本机平台使用该账号登录，打开 **项目 → Models & Compute**（`/settings/models`）。管理员权限保存在本机数据库，不依赖前端 email 判断。普通用户无法读取或更改服务器配置。

## GPU 和权重未就绪时

1. 进入 **Models → 添加模型版本**，填写显示名称、`SkySense++` 和计划使用的版本，选择 **Research only**。Checkpoint SHA256 可暂空，实际接入前必须填写真实权重文件的 SHA256。
2. 进入 **Compute Endpoints → 添加计算服务器**，选择 **LAN HTTP** 和上述模型版本。服务器 IP 未确定时暂不创建端点；确定后填写实际 Base URL，可配置多个端点指向同一个模型版本。
3. GPU 服务未就绪时保持 **Enabled 未勾选**。离线服务器不会阻止平台启动或 P8 Mock 工作流。

源码没有内置 SkySense++ 服务器地址。服务端只接受已配置的 LAN 地址；DNS 名称须在本地 `.env` 的 `MODEL_ENDPOINT_ALLOWED_HOSTS` 中明确允许，并重建 API/Worker 容器使环境生效。不要将实际凭据写入源码。

## 服务器就绪后

远端 Linux / NVIDIA 服务必须实现仓库中的 `ModelWorkerRequest` / `ModelWorkerResponse`，提供：

- `GET /health`：`status=ok`, `cuda=true`, `model_loaded=true`。
- `GET /model-info`：模型名称、版本、权重 SHA256、Git commit、runtime/CUDA 版本、GPU 名称与总显存、`usage_policy=research_only`。
- `POST /v1/inference/oneshot-segmentation`：512×512 RGB support、0/1 support mask、512×512 RGB query；返回有限且在 [0,1] 范围内的 probability mask。
- `DELETE /v1/jobs/{job_id}/attempts/{attempt_id}`：取消该次执行。

在 Models 中更新实际身份和 checkpoint SHA256，启用端点，然后点击 **Test Connection**。FastAPI 服务端执行健康检查，浏览器不会直接连接 GPU 服务器。Healthy 表示当次健康检查和模型身份匹配，并不代表真实推理验收完成。

当前凭据模式默认 `none`。API 已预留 `bearer` / `api_key` 与服务器环境变量名称 `secret_ref`；实际值必须通过服务器环境提供，不能在 UI 填写或提交 GitHub。配置编辑保留已有凭据引用。

## 恢复或重新部署管理员权限

先通过平台创建并确认账号，再在本机项目目录执行：

```bash
.venv/bin/python scripts/platform_admin.py --email qym57@outlook.com
```

此命令只向既有、已确认账号授予管理员权限，不创建账号、不修改密码，也不修改其他管理员。

## 尚待真实验收

GPU / 权重就绪后仍需完成三类真实 fixture：support=query、同类不同 query、无关 query，并记录概率 mean/std、前景比例、面积、耗时、峰值显存、seed、slot、endpoint/release/checkpoint 身份。常数、全空或全满输出不得判定成功。单次 query 必须读取 source-resolution 512×512 window；不使用 P8 bounded AOI 缩放作为大图推理。AOI tiling/stitching 留到 P11。
