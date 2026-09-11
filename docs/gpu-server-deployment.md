# GPU 服务器环境安装归档

本页归档 P9B 部署期间已经执行的主机安装与离线传输步骤。GeoAI 主平台仍在 Mac 本地运行；Linux 只承载研究模型 Worker。服务器地址、账号、凭据、权重和镜像归档不提交 Git。以下命令中的 `GPU_HOST` 由部署者在本地填写。

## 状态与边界

| 项目 | 已验证结果 |
| --- | --- |
| 主机 | Ubuntu 24.04.2 LTS / x86_64，双 RTX 4090 |
| 驱动 | 580.95.05；nvidia-smi 中 CUDA 13.0 是驱动能力，不是模型运行时版本 |
| Docker Engine | 29.8.0 |
| Docker Compose | v5.5.1 |
| NVIDIA Container Toolkit CLI | 1.20.0，commit `5505e2f94d9aaa08561490db974ba3cd676af209` |
| 容器 GPU | 官方 Ubuntu amd64 镜像离线加载后，指定物理 GPU 1 的 nvidia-smi 成功 |
| 官方源码 | `cb0c6b774471ad3314354041c8fa6aae7d49a9bb`，远端 git fsck 与工作树检查通过 |
| HTTP bridge | 六个源码文件已传输，Python 语法检查通过 |
| 真实模型环境 | 尚未完成：CUDA/PyTorch/MMCV 与 HTTP bridge 依赖兼容性待验证 |
| 权重及推理 | 用户正在上传；尚未核验路径、摘要、模型加载及四组真实推理 |

容器能看到 GPU **不代表 P9B 通过**。当前尚无真实模型概率、运行时间或 VRAM 验收结果。不要登记为可用模型，不要用随机权重或 Mock 代替验收。

## 1. 主机检查与安装

已执行原件：[install-gpu-host.sh](../scripts/gpu/install-gpu-host.sh)。原件 SHA256：

```text
1161e63906c7d6f786eb116fdf5bf245e0130875bd17a1a1ef157212bed193d6
```

脚本使用 Docker/NVIDIA 官方 apt 源，安装 Docker CE、Compose、Buildx 与 NVIDIA Container Toolkit，配置容器 runtime；不安装或替换显卡驱动。版本表记录实际安装结果，脚本的 apt 包并未 exact pin，不保证将来安装相同版本。

脚本需要人工 sudo，会重启 Docker，并将执行用户加入 docker 组（具有主机管理员等效权限）。仅适用于经检查的新部署主机；不是通用升级脚本。原件最后固定测试 GPU 1，其他主机必须先检查 GPU 占用，选择空闲设备；不要影响已有训练作业。

在 Mac 仓库根目录：

```bash
export GPU_HOST='your-user@your-server'
ssh "$GPU_HOST" 'uname -s; uname -m; cat /etc/os-release; nvidia-smi; df -h "$HOME"; command -v docker'
ssh "$GPU_HOST" 'mkdir -p "$HOME/geoai-worker"'
scp scripts/gpu/install-gpu-host.sh "$GPU_HOST:geoai-worker/install-gpu-host.sh"
ssh -t "$GPU_HOST"
```

在服务器终端检查并手工执行：

```bash
less ~/geoai-worker/install-gpu-host.sh
# less 是阅读器，按 q 退出，不需要等待。
sudo bash ~/geoai-worker/install-gpu-host.sh
# 安装后退出 SSH 并重新连接，刷新 docker 组权限。
```

本次安装最后拉取 Ubuntu 镜像时 Docker Hub 超时，之前的安装已成功。不要因此重复安装，按下一节完成镜像离线加载。现有用户 Conda 无法执行，未改动该环境。

## 2. Docker Hub 不可达：官方镜像离线传输

服务器访问 Docker Hub/GitHub 超时，而 Mac 可访问；不修改 DNS、代理或使用未经核验的镜像源。`ubuntu:24.04` 是 Docker 镜像名称，不是磁盘文件路径。

在 Mac：

```bash
docker pull --platform linux/amd64 ubuntu:24.04
docker image inspect ubuntu:24.04 --format '{{.Os}}/{{.Architecture}} {{.Id}}'
docker save -o /tmp/geoai-ubuntu-24.04-amd64.tar ubuntu:24.04
shasum -a 256 /tmp/geoai-ubuntu-24.04-amd64.tar
scp /tmp/geoai-ubuntu-24.04-amd64.tar "$GPU_HOST:geoai-worker/ubuntu-24.04-amd64.tar"
ssh "$GPU_HOST" 'sha256sum "$HOME/geoai-worker/ubuntu-24.04-amd64.tar"'
```

确认两端 SHA256 一致后再加载：

```bash
ssh "$GPU_HOST" 'docker load -i "$HOME/geoai-worker/ubuntu-24.04-amd64.tar"'
scp scripts/gpu/verify-gpu-container.sh "$GPU_HOST:geoai-worker/verify-gpu-container.sh"
# 先检查 GPU 空闲情况；本次选择物理 GPU 1。
ssh "$GPU_HOST" 'bash "$HOME/geoai-worker/verify-gpu-container.sh" 1'
```

本次实际传输证据：

- 官方 manifest digest：`sha256:224a1869083a311ef3f13648a154ba79832fbef6364d31493642ca03082da254`
- amd64 image ID：`sha256:b2b7ea366714195a1e1c5b2b578ece85c0b3920381a8654d038d9684f009613c`
- 两端 tar SHA256：`bead1def5a1d4cf1f9779c9ba355ba8786b0251ce789b0c63894b0a8c547888b`

新下载的可变 tag 与新生成归档摘要可能不同，每次都应重新记录、核对。容器内 GPU 0 可能对应主机选中的 GPU 1。

## 3. 固定官方源码与最小 bridge

官方仓库：[SkySensePlusPlus](https://github.com/kang-wu/SkySensePlusPlus)。在 Mac 获取并核验后，通过 SSH 传输，避免服务器 GitHub 网络阻塞。

```bash
git clone https://github.com/kang-wu/SkySensePlusPlus.git /tmp/geoai-skysense-source
git -C /tmp/geoai-skysense-source checkout --detach cb0c6b774471ad3314354041c8fa6aae7d49a9bb
git -C /tmp/geoai-skysense-source diff --exit-code HEAD
COPYFILE_DISABLE=1 tar --no-xattrs -czf /tmp/geoai-skysense-source.tar.gz -C /tmp/geoai-skysense-source .
shasum -a 256 /tmp/geoai-skysense-source.tar.gz
scp /tmp/geoai-skysense-source.tar.gz "$GPU_HOST:geoai-worker/skysense-source.tar.gz"
ssh "$GPU_HOST" 'sha256sum "$HOME/geoai-worker/skysense-source.tar.gz"'
# 核对摘要；仅向新的源码目录解包，不覆盖已有部署。
ssh "$GPU_HOST" 'mkdir "$HOME/geoai-worker/SkySensePlusPlus" && tar -xzf "$HOME/geoai-worker/skysense-source.tar.gz" -C "$HOME/geoai-worker/SkySensePlusPlus"'
ssh "$GPU_HOST" 'git -C "$HOME/geoai-worker/SkySensePlusPlus" rev-parse HEAD; git -C "$HOME/geoai-worker/SkySensePlusPlus" fsck --no-reflogs --no-dangling; git -C "$HOME/geoai-worker/SkySensePlusPlus" diff --exit-code HEAD'
```

首次传输出现 Mac AppleDouble `._*` 元数据，已在本次新源码目录中识别清理并通过 git fsck；以上命令禁用扩展属性，避免重复产生。不要对已有服务器目录运行通配删除。

在 GeoAI 仓库根目录打包 bridge：

```bash
bash scripts/gpu/pack-worker-bridge.sh /tmp/geoai-worker-bridge.tar.gz
scp /tmp/geoai-worker-bridge.tar.gz "$GPU_HOST:geoai-worker/worker-bridge.tar.gz"
ssh "$GPU_HOST" 'sha256sum "$HOME/geoai-worker/worker-bridge.tar.gz"'
# 摘要一致后，仅解包到新目录。
ssh "$GPU_HOST" 'mkdir "$HOME/geoai-worker/bridge" && tar -xzf "$HOME/geoai-worker/worker-bridge.tar.gz" -C "$HOME/geoai-worker/bridge"'
```

打包脚本仅允许六个 bridge/contract 文件，不包含平台 `.env`、数据库凭据、权重或整个工作区。首次传输执行的是同等文件清单；归档 helper 增加输出路径保护。重新部署时使用新的版本目录，不覆盖运行中的服务。

## 4. 未完成部分与后续步骤

正在准备的候选镜像为 `pytorch/pytorch:1.13.1-cuda11.6-cudnn8-runtime`；不能把下载镜像视为完成模型环境安装。官方 Ant-Multi-Modal-Framework 依赖仍需固定兼容版本。原始研究环境 Python 3.8/Torch 1.13.1 与当前 bridge Python 3.10+/Pydantic 2 的兼容性尚未验证。

后续完成后应继续归档实际 Dockerfile、依赖锁定及启动配置，而不是现在提供未经验证的“一键部署”。

1. 获取上传完成的权重路径，核对来源、许可和 SHA256，保留在服务器本地。
2. 验证并锁定实际 CUDA/PyTorch/MMCV/HTTP 环境；选择空闲 GPU，不干扰现有作业。
3. 按 [Worker README](../services/model-worker/README.md) 配置并启动单进程 HTTP Worker。
4. `/health`、`/model-info` 返回真实模型身份和 `research_only`；Mac 注册真实地址并测试连接。
5. 完成 same-image、same-class cross-image、unrelated-query、wrong-prompt 四组单 Tile 验收，记录概率 mean/std、foreground ratio、面积、runtime、峰值 VRAM、seed、模型/权重身份和可视化。
6. 按 [P9B 验收门槛](p9b-acceptance-gates.md) 判定；P9B 通过后才验收 P9C 到真实模型的联动，不提前做 AOI tiling/stitching。

## 归档验证范围

本次归档检查脚本 Bash 语法、安装原件摘要、bridge 打包白名单和 Git diff。未重复执行 apt 安装、Docker 重启或模型推理；不将历史验证冒充本次完整 P8/P9 regression。

参考：[Docker Ubuntu 安装](https://docs.docker.com/engine/install/ubuntu/)、[NVIDIA Container Toolkit 安装](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)。
