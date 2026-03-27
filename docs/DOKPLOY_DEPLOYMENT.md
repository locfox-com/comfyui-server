# Dokploy 部署指南

本文档介绍如何在 Dokploy 平台上部署 ComfyUI AI Image Server。

## 目录

- [前置要求](#前置要求)
- [GPU 配置](#gpu-配置)
- [部署步骤](#部署步骤)
- [环境变量配置](#环境变量配置)
- [域名和 SSL 配置](#域名和-ssl-配置)
- [监控和维护](#监控和维护)
- [故障排除](#故障排除)

## 前置要求

### 1. Dokploy 服务器要求

- **操作系统**: Ubuntu 20.04+ 或 Debian 11+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **内存**: 至少 16GB RAM
- **存储**: 至少 100GB 可用空间
- **GPU**: NVIDIA GPU with CUDA 11.8+ support (推荐 RTX 3080 或更高)

### 2. 安装 NVIDIA Container Toolkit

在 Dokploy 服务器上安装 NVIDIA Container Toolkit：

```bash
# 添加 NVIDIA 包仓库
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-docker-keyring.gpg
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# 更新并安装
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 配置 Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 验证安装
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### 3. 配置 Docker Daemon

编辑 `/etc/docker/daemon.json`：

```json
{
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  },
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

重启 Docker：

```bash
sudo systemctl restart docker
```

## GPU 配置

### 验证 GPU 可用性

在部署前，确保 GPU 可用：

```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 测试 Docker GPU 访问
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### GPU 资源配置

在 `dokploy.json` 中已配置 GPU 资源：

```json
{
  "resources": {
    "gpu": {
      "comfyui": {
        "count": 1,
        "capabilities": ["gpu"],
        "driver": "nvidia"
      }
    }
  }
}
```

## 部署步骤

### 方式 1: 通过 Git 仓库部署（推荐）

1. **推送代码到 GitHub**

   代码已在: https://github.com/locfox-com/comfyui-server

2. **在 Dokploy 中创建项目**

   - 登录 Dokploy 控制面板
   - 点击 "New Project" 或 "创建项目"
   - 选择 "Git Repository" 部署类型
   - 输入仓库 URL: `https://github.com/locfox-com/comfyui-server.git`
   - 选择分支: `master` 或 `feature/comfyui-server`

3. **配置部署设置**

   - 部署类型: Docker Compose
   - Docker Compose 文件: `docker-compose.yml`
   - 环境变量文件: `.env`

4. **启动部署**

   - 点击 "Deploy" 或 "部署" 按钮
   - 等待所有服务启动完成

### 方式 2: 手动上传部署

1. **准备部署文件**

```bash
# 克隆仓库
git clone https://github.com/locfox-com/comfyui-server.git
cd comfyui-server

# 复制环境变量模板
cp .env.example .env
```

2. **配置环境变量**（见下一节）

3. **在 Dokploy 中上传项目**

   - 在 Dokploy 控制面板选择 "Upload Project"
   - 上传整个项目目录
   - 或上传包含以下文件的 zip 包：
     - `docker-compose.yml`
     - `dokploy.json`
     - `.env`
     - `api/Dockerfile`
     - `worker/Dockerfile`
     - `comfyui/Dockerfile`
     - `nginx/default.conf`

## 环境变量配置

### 必需的环境变量

创建 `.env` 文件并配置以下变量：

```bash
# ====================
# API 配置
# ====================
API_KEYS=your-secure-api-key-here
API_PORT=8000
API_HOST=0.0.0.0
ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
MAX_IMAGE_SIZE_BYTES=10485760
MAX_REQUEST_BODY_SIZE=15728640
SUPPORTED_FORMATS=png,jpg,jpeg,webp

# ====================
# Redis 配置
# ====================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
REDIS_MAX_MEMORY=512mb

# ====================
# ComfyUI 配置
# ====================
COMFYUI_HOST=http://comfyui:8188
COMFYUI_TIMEOUT=300

# ====================
# Cloudflare R2 配置（必需）
# ====================
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key
R2_BUCKET_NAME=ai-images
R2_PUBLIC_URL=https://your-bucket.r2.dev

# ====================
# Worker 配置
# ====================
WORKER_CONCURRENCY=1
WORKER_POLL_INTERVAL=1
GPU_TEMP_THRESHOLD=85
TASK_TIMEOUT_FACE_SWAP=60
TASK_TIMEOUT_UPSCALE=120
TASK_TIMEOUT_REMOVE_BG=30

# ====================
# Nginx 配置
# ====================
NGINX_PORT=80
NGINX_CLIENT_MAX_BODY_SIZE=15M
NGINX_RATE_LIMIT=10

# ====================
# WebSocket 配置
# ====================
WS_TOKEN_TTL=300
WS_HEARTBEAT_INTERVAL=30
WS_HEARTBEAT_TIMEOUT=60

# ====================
# 清理配置
# ====================
CLEANUP_INPUT_AFTER_HOURS=2
CLEANUP_OUTPUT_AFTER_HOURS=24
CLEANUP_INTERVAL_MINUTES=30

# ====================
# 日志配置
# ====================
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 在 Dokploy 中配置环境变量

1. **通过 UI 配置**:
   - 进入项目设置
   - 找到 "Environment Variables" 或 "环境变量"
   - 逐个添加变量

2. **通过 .env 文件**:
   - 确保项目根目录有 `.env` 文件
   - Dokploy 会自动加载

3. **敏感信息管理**:
   - 使用 Dokploy 的 Secrets 功能存储敏感信息
   - 在环境变量中引用: `R2_SECRET_ACCESS_KEY={{SECRET:r2_secret_key}}`

## 域名和 SSL 配置

### 配置自定义域名

1. **在 Dokploy 中添加域名**:

   - 进入项目设置 → Domains
   - 添加主域名: `ai.yourdomain.com`
   - Dokploy 会自动配置 DNS

2. **配置 DNS 记录**:

   在您的域名提供商处添加 A 记录：

   ```
   Type: A
   Name: ai
   Value: <your-server-ip>
   TTL: 300
   ```

### SSL 证书配置

1. **自动 Let's Encrypt 证书**:

   在 `dokploy.json` 中已配置：

   ```json
   {
     "domains": {
       "primary": "ai.yourdomain.com",
       "ssl": {
         "enabled": true,
         "provider": "letsencrypt",
         "auto_renew": true,
         "email": "your-email@example.com"
       }
     }
   }
   ```

2. **手动配置**（如果自动配置失败）:

   - 在 Dokploy UI 中启用 SSL
   - 输入邮箱地址用于证书通知
   - 点击 "Request Certificate"

3. **验证 SSL**:

   ```bash
   curl -I https://ai.yourdomain.com/health
   ```

## 监控和维护

### 日志查看

在 Dokploy 控制面板：

```bash
# 查看所有服务日志
# 在 UI 中选择 "Logs" 或 "日志"

# 查看特定服务日志
# 选择服务: api, worker, comfyui, redis, nginx

# 导出日志
# 点击 "Download Logs" 或 "导出日志"
```

### 资源监控

在 Dokploy 中监控以下指标：

- **CPU 使用率**: 各服务 CPU 占用
- **内存使用**: 内存占用情况
- **GPU 使用率**: GPU 利用率和温度
- **磁盘空间**: Volume 存储使用情况
- **网络流量**: 请求量和带宽

### 健康检查

服务健康检查端点：

```bash
# API 健康检查
curl https://ai.yourdomain.com/health

# ComfyUI 连接检查
curl https://ai.yourdomain.com/api/health

# 服务状态
docker ps  # 在 Dokploy 服务器上
```

### 扩展 Workers

根据负载情况扩展 Workers：

1. **在 Dokploy UI 中**:
   - 进入服务设置 → worker
   - 调整 replicas 数量: 1-3

2. **通过配置文件**:
   ```yaml
   # docker-compose.yml
   services:
     worker:
       deploy:
         replicas: 3
   ```

3. **自动扩展**（如果支持）:
   ```json
   {
     "worker": {
       "scalable": true,
       "max_replicas": 3,
       "target_cpu_percent": 70
     }
   }
   ```

### 备份和恢复

**备份重要数据**:

```bash
# 备份 Redis 数据
docker exec redis redis-cli SAVE
docker cp <redis-container>:/data/dump.rdb backup/

# 备份模型文件
docker cp <comfyui-container>:/app/ComfyUI/models backup/models

# 备份环境变量
cp .env backup/.env.$(date +%Y%m%d)
```

**恢复数据**:

```bash
# 恢复 Redis 数据
docker cp backup/dump.rdb <redis-container>:/data/dump.rdb
docker restart <redis-container>

# 恢复模型文件
docker cp backup/models <comfyui-container>:/app/ComfyUI/
```

## 故障排除

### 常见问题

#### 1. GPU 不可用

**症状**: ComfyUI 服务无法启动，日志显示 GPU 错误

**解决方案**:

```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 检查 Docker GPU 支持
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# 检查 NVIDIA Container Toolkit
dpkg -l | grep nvidia-container-toolkit

# 重新安装 NVIDIA Container Toolkit
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

#### 2. 服务无法通信

**症状**: API 无法连接到 Redis 或 ComfyUI

**解决方案**:

```bash
# 检查服务是否在同一网络
docker network ls
docker network inspect comfyui-internal

# 检查 DNS 解析
docker exec api ping -c 3 redis
docker exec api ping -c 3 comfyui

# 检查防火墙规则
sudo ufw status
```

#### 3. 模型文件缺失

**症状**: Worker 日志显示模型未找到

**解决方案**:

```bash
# 进入 ComfyUI 容器
docker exec -it <comfyui-container> bash

# 检查模型目录
ls -lh /app/ComfyUI/models/

# 重新下载模型
bash /app/download_models.sh

# 或手动上传模型
docker local path/to/model.pth /app/ComfyUI/models/upscale/
```

#### 4. R2 上传失败

**症状**: 任务完成但图片未上传到 R2

**解决方案**:

```bash
# 检查 R2 配置
docker exec worker env | grep R2

# 测试 R2 连接
docker exec worker python -c "
from utils.r2 import r2_client
print(r2_client.test_connection())
"

# 检查网络连接
docker exec worker curl -I https://your-bucket.r2.dev
```

#### 5. 内存不足

**症状**: 服务被 OOM Killer 杀死

**解决方案**:

```yaml
# docker-compose.yml
services:
  comfyui:
    deploy:
      resources:
        limits:
          memory: 12G  # 增加内存限制
        reservations:
          memory: 8G
```

### 日志级别调整

启用调试日志：

```bash
# .env
LOG_LEVEL=DEBUG

# 重启服务
docker compose restart api worker
```

### 性能优化

**优化 GPU 利用率**:

```yaml
# docker-compose.yml
services:
  worker:
    environment:
      - WORKER_CONCURRENCY=2  # 增加 worker 并发
```

**优化 Redis 性能**:

```yaml
services:
  redis:
    command: >
      redis-server
      --appendonly yes
      --maxmemory 1gb
      --maxmemory-policy allkeys-lru
      --save 900 1
      --save 300 10
```

## 安全建议

1. **API 密钥管理**:
   - 使用强随机密钥: `openssl rand -hex 32`
   - 定期轮换密钥
   - 不要在代码中硬编码

2. **网络安全**:
   - 启用 HTTPS
   - 配置防火墙规则
   - 限制 API 访问来源

3. **数据加密**:
   - Redis 使用密码认证
   - 敏感环境变量使用 Dokploy Secrets

4. **定期更新**:
   - 定期更新基础镜像
   - 更新依赖包
   - 监控安全漏洞

## 支持

- **文档**: [README.md](../README.md)
- **API 文档**: [docs/API.md](../docs/API.md)
- **问题反馈**: [GitHub Issues](https://github.com/locfox-com/comfyui-server/issues)

## 附录

### A. Dokploy 命令参考

```bash
# 查看项目状态
dokploy ps

# 查看日志
dokploy logs -f

# 重启服务
dokploy restart <service>

# 扩展服务
dokploy scale worker=3

# 更新部署
dokploy deploy
```

### B. 监控指标

关键监控指标：

| 指标 | 正常范围 | 警告阈值 | 严重阈值 |
|------|----------|----------|----------|
| GPU 温度 | < 75°C | > 80°C | > 85°C |
| GPU 利用率 | 60-90% | > 95% | < 20% |
| 内存使用 | < 80% | > 85% | > 95% |
| 队列长度 | < 10 | > 20 | > 50 |
| 响应时间 | < 5s | > 10s | > 30s |

### C. 快速部署检查清单

部署前检查：

- [ ] NVIDIA GPU 驱动已安装
- [ ] NVIDIA Container Toolkit 已安装
- [ ] Docker GPU 支持已验证
- [ ] 所有环境变量已配置
- [ ] R2 存储凭证已配置
- [ ] 域名 DNS 已配置
- [ ] SSL 证书已申请
- [ ] 防火墙规则已设置
- [ ] 备份策略已确定

部署后验证：

- [ ] 所有服务运行正常
- [ ] GPU 可被 ComfyUI 访问
- [ ] API 健康检查通过
- [ ] 任务可以提交和处理
- [ ] 输出图片可以上传到 R2
- [ ] WebSocket 连接正常
- [ ] 日志正常输出
- [ ] 监控指标正常
