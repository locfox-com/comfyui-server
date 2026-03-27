# ComfyUI AI 图片处理服务器设计文档

**日期**: 2026-03-26
**版本**: 2.0（Review 修订版）
**作者**: Claude

---

## 修订记录

| 版本 | 日期 | 修改内容 |
|------|------|---------|
| 1.0 | 2026-03-26 | 初始版本 |
| 2.0 | 2026-03-26 | Review 修订：修复 CUDA 版本、补充 GPU 透传配置、调整并发策略、优化 API 设计、增强安全性、补充运维方案 |

---

## 1. 项目概述

构建一个基于 ComfyUI 的局域网 AI 图片处理服务，提供换脸、图片放大、去背景功能的 RESTful API 和 WebSocket 进度推送。

### 核心需求

- **访问范围**: 局域网访问（192.168.x.x 网段）
- **核心功能**: 换脸、图片放大/超分辨率、图片去背景
- **接口类型**: 纯 API 服务（无 ComfyUI 网页界面）
- **并发规模**: 10+ 用户，中等并发
- **部署方式**: Docker Compose
- **认证方式**: API Key
- **存储**: Cloudflare R2 对象存储
- **API 风格**: RESTful 提交任务 + WebSocket 进度推送

### 系统环境

- **GPU**: NVIDIA RTX 3070 Laptop (8GB VRAM)
- **CUDA**: ⚠️ 部署前请确认实际版本（运行 `nvidia-smi` 查看 Driver 版本，`nvcc --version` 查看 Toolkit 版本，当前主流为 CUDA 12.x 系列）
- **Python**: 3.12.3
- **RAM**: 19GB
- **磁盘**: 79GB 可用

### 部署前置检查清单

```bash
# 1. 确认 GPU 和 CUDA 版本
nvidia-smi
nvcc --version

# 2. 确认 NVIDIA Container Toolkit 已安装
nvidia-ctk --version
# 如未安装：
# curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
# sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
# sudo systemctl restart docker

# 3. 验证 Docker 可访问 GPU
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi

# 4. 确认磁盘可用空间 >= 30GB（Docker 镜像 + 模型 + 临时文件）
df -h /home/abel/comfyui-server
```

---

## 2. 系统架构

### 2.1 整体架构图

```
客户端 (局域网设备)
    │
    ├─ RESTful POST /api/tasks (提交任务)
    └─ WebSocket /ws/task/{task_id} (监听进度)
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Nginx (端口 80) — external-network + internal-network  │
│  - 反向代理 RESTful 请求 → API 服务                      │
│  - 反向代理 WebSocket → API 服务                         │
│  - 限流保护 (10r/s per IP)                               │
│  - client_max_body_size 15M (Base64 编码膨胀约 33%)      │
└─────────────────────────────────────────────────────────┘
         │ (internal-network)
         ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI 服务 (端口 8000) — internal-network only        │
│  - API Key 认证中间件                                    │
│  - 统一任务提交接口 POST /api/tasks                      │
│  - 图片解码后保存到共享卷 /data/inputs/{task_id}/        │
│  - 任务元数据（不含图片）推入 Redis 队列                 │
│  - WebSocket 进度推送（短期 Token 认证）                 │
│  - R2 上传处理                                           │
│  - 健康检查端点（含 GPU 温度监控）                       │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Redis — internal-network only                          │
│  - 任务队列 (list): task:queue（最大长度 50）            │
│  - 进度缓存 (hash): task:progress:{task_id}             │
│  - 任务状态 (hash): task:status:{task_id}               │
│  - WebSocket Token 缓存: ws:token:{token} (TTL 5min)    │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Worker 进程 — internal-network only                     │
│  - 从 Redis 队列取任务 (BRPOP)                          │
│  - 从共享卷 /data/inputs/ 读取输入图片                   │
│  - 加载 Workflow JSON 模板，动态替换参数                 │
│  - 调用 ComfyUI API 执行处理                             │
│  - 更新进度到 Redis                                      │
│  - 处理完成后上传到 R2                                   │
│  - 清理本地临时文件                                      │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  ComfyUI 后端 (端口 8188) — internal-network only        │
│  - 内部 API，不对外暴露                                  │
│  - 加载换脸、放大、去背景节点                            │
│  - GPU 加速处理（NVIDIA Runtime 透传）                   │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Cloudflare R2 (外部服务)                                │
│  - 存储处理后的图片                                      │
│  - 通过 SDK 调用 (PutObject + HeadObject)                │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Docker Compose 服务

| 服务名 | 镜像/基础 | 端口 | 网络 | GPU | 作用 |
|--------|----------|------|------|-----|------|
| nginx | nginx:alpine | 80 (对外) | external + internal | 否 | 反向代理和路由 |
| api | python:3.12-slim | 8000 (仅内部) | internal | 否 | FastAPI 服务 |
| redis | redis:alpine | 6379 (仅内部) | internal | 否 | 队列和缓存 |
| worker | python:3.12-slim | - | internal | 否 | 任务处理进程 |
| comfyui | 自定义 (基于 CUDA) | 8188 (仅内部) | internal | **是** | ComfyUI 后端 |

### 2.3 Docker Compose 关键配置

```yaml
version: "3.8"

networks:
  external-network:
    driver: bridge
  internal-network:
    driver: bridge
    internal: true  # 禁止外部直接访问

volumes:
  shared-data:      # 共享卷：输入图片 + 临时文件
  comfyui-models:   # 模型持久化
  comfyui-output:   # ComfyUI 输出目录
  redis-data:       # Redis 持久化

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    networks:
      - external-network
      - internal-network
    depends_on:
      - api
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro

  api:
    build: ./api
    networks:
      - internal-network     # 只加入内部网络
    volumes:
      - shared-data:/data
    depends_on:
      - redis
    env_file: .env

  redis:
    image: redis:alpine
    networks:
      - internal-network
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru

  worker:
    build: ./worker
    networks:
      - internal-network
    volumes:
      - shared-data:/data
    depends_on:
      - redis
      - comfyui
    env_file: .env

  comfyui:
    build: ./comfyui
    networks:
      - internal-network
    volumes:
      - comfyui-models:/app/ComfyUI/models
      - comfyui-output:/app/ComfyUI/output
      - shared-data:/data
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

---

## 3. API 接口设计

### 3.1 RESTful API 接口

#### 3.1.1 统一任务提交接口

> **v2 变更**: 合并三个独立接口为统一入口，通过 `type` 字段分发，便于扩展。

```
POST /api/tasks

Headers:
  X-API-Key: <your-api-key>
  Content-Type: application/json

Request Body (换脸):
{
  "type": "face-swap",
  "images": {
    "source": "base64_encoded_image_string",
    "target": "base64_encoded_image_string"
  },
  "webhook_url": "http://192.168.1.100:3000/webhook"  // 可选
}

Request Body (图片放大):
{
  "type": "upscale",
  "images": {
    "source": "base64_encoded_image_string"
  },
  "params": {
    "scale_factor": 2   // 可选: 2, 4, 或 8，默认 2
  },
  "webhook_url": "http://192.168.1.100:3000/webhook"  // 可选
}

Request Body (去背景):
{
  "type": "remove-background",
  "images": {
    "source": "base64_encoded_image_string"
  },
  "webhook_url": "http://192.168.1.100:3000/webhook"  // 可选
}

Response (200 OK):
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "websocket_url": "ws://192.168.x.x/ws/task/550e8400-e29b-41d4-a716-446655440000",
  "ws_token": "eyJhbGciOiJIUzI1NiJ9...",  // 短期 WebSocket 认证 Token，5 分钟有效
  "queue_position": 3
}

Error Response (401 Unauthorized):
{
  "error": "Invalid API Key"
}

Error Response (400 Bad Request):
{
  "error": "Invalid image format",
  "details": "Only PNG, JPG, WEBP supported. Max 10MB after decode."
}

Error Response (429 Too Many Requests):
{
  "error": "Queue is full",
  "details": "Current queue length: 50. Estimated wait time: ~10 minutes.",
  "retry_after": 60
}
```

#### 3.1.2 查询任务状态

```
GET /api/tasks/{task_id}

Headers:
  X-API-Key: <your-api-key>

Response (200 OK):
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "face-swap",
  "status": "completed",  // queued, processing, completed, failed, cancelled
  "progress": 100,
  "result_url": "https://your-bucket.r2.dev/face-swap/550e8400-e29b-41d4-a716-446655440000.png",
  "created_at": "2026-03-26T12:00:00Z",
  "completed_at": "2026-03-26T12:00:15Z",
  "processing_time": 15.2,
  "error": null
}
```

#### 3.1.3 批量查询任务

> **v2 新增**: 支持按状态筛选和分页。

```
GET /api/tasks?status=processing&limit=20&offset=0

Headers:
  X-API-Key: <your-api-key>

Response (200 OK):
{
  "tasks": [ ... ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

#### 3.1.4 取消任务

> **v2 新增**: 支持取消队列中或处理中的任务。

```
DELETE /api/tasks/{task_id}

Headers:
  X-API-Key: <your-api-key>

Response (200 OK):
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "cancelled",
  "message": "Task removed from queue"
}

Response (409 Conflict):
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "message": "Task already completed, cannot cancel"
}
```

### 3.2 WebSocket 接口

#### 3.2.1 连接

> **v2 变更**: 使用短期 Token 替代 URL 中的 API Key，避免 Key 泄露到日志和浏览器历史。

```
ws://192.168.x.x/ws/task/{task_id}?token={ws_token}
```

`ws_token` 在任务创建时返回，绑定到特定 `task_id`，有效期 5 分钟。

#### 3.2.2 消息格式（服务器 → 客户端）

**进度消息**：
```json
{
  "type": "progress",
  "timestamp": "2026-03-26T12:00:10Z",
  "data": {
    "status": "processing",
    "progress": 45,
    "message": "正在处理中...",
    "current_step": 5,
    "total_steps": 10
  }
}
```

**完成消息**：
```json
{
  "type": "completed",
  "timestamp": "2026-03-26T12:00:15Z",
  "data": {
    "result_url": "https://your-bucket.r2.dev/face-swap/550e8400-e29b-41d4-a716-446655440000.png",
    "metadata": {
      "processing_time": 15.2,
      "model_used": "inswapper_128.onnx"
    }
  }
}
```

**错误消息**：
```json
{
  "type": "error",
  "timestamp": "2026-03-26T12:00:15Z",
  "data": {
    "error": "Image format not supported",
    "code": "INVALID_FORMAT",
    "details": "Source image is corrupted"
  }
}
```

#### 3.2.3 心跳机制

> **v2 变更**: 改为服务端主动 ping（符合 RFC 6455 标准）。

服务端每 30 秒发送 ping，客户端回复 pong。超时 60 秒未收到 pong 则断开连接。

---

## 4. ComfyUI 节点和模型

### 4.1 换脸功能

**节点**: `ReActor Fast Face Swap`
**模型**: `inswapper_128.onnx`
**下载地址**: https://huggingface.co/Gourieff/ReActor/tree/main/models

**工作流特点**:
- 支持快速换脸
- 模型大小约 130MB
- VRAM 占用约 1.5-2GB
- 单次处理约 3-8 秒

### 4.2 图片放大功能

**节点**: `ImageScale` (ComfyUI 内置) 或 `Ultimate SD Upscale`
**模型**: `RealESRGAN_x4plus.pth`
**下载地址**: https://github.com/xinntao/Real-ESRGAN/releases

**工作流特点**:
- 支持 2x, 4x, 8x 放大
- 模型大小约 67MB
- VRAM 占用约 2-6GB（取决于输入图片尺寸）
- 单次处理约 5-20 秒（取决于图片尺寸和倍数）
- ⚠️ 大图（>2K）在 8GB VRAM 下 4x/8x 放大可能 OOM，建议限制输入分辨率

### 4.3 去背景功能

**节点**: `RMBG-1.4` 或 `BiRefNet`
**模型**: `RMBG-1.4.pth`
**下载地址**: https://huggingface.co/briaai/RMBG-1.4

**工作流特点**:
- 高质量去背景
- 模型大小约 170MB
- VRAM 占用约 1-2GB
- 单次处理约 2-5 秒

### 4.4 Workflow JSON 管理

> **v2 新增**: 明确 Workflow 模板管理方案。

每个功能对应一个 ComfyUI workflow JSON 模板文件，Worker 运行时动态替换参数。

```
workflows/
├── face_swap.json        # 换脸 workflow 模板
├── upscale.json          # 放大 workflow 模板
└── remove_background.json # 去背景 workflow 模板
```

**参数替换机制**：
Worker 加载 JSON 模板后，替换以下占位符：
- `{{INPUT_IMAGE_PATH}}` → `/data/inputs/{task_id}/source.png`
- `{{TARGET_IMAGE_PATH}}` → `/data/inputs/{task_id}/target.png`（仅换脸）
- `{{SCALE_FACTOR}}` → 放大倍数（仅放大）
- `{{OUTPUT_PREFIX}}` → `{task_id}`

**Workflow 模板获取方法**：
1. 在 ComfyUI Web UI 中手动搭建完整工作流
2. 通过"Save (API Format)"导出为 JSON
3. 将具体参数替换为占位符
4. 保存到 `workflows/` 目录

---

## 5. 数据流设计

### 5.1 任务处理完整流程

```
1. 客户端提交任务 (POST /api/tasks)
   ↓
2. FastAPI 验证 API Key
   ├─ 无效 → 返回 401
   └─ 有效 → 继续
   ↓
3. FastAPI 验证请求参数
   ├─ type 不支持 → 返回 400
   ├─ 图片格式不支持 → 返回 400
   ├─ 图片解码后超过 10MB → 返回 413
   └─ 通过 → 继续
   ↓
4. 检查队列长度
   ├─ >= 50 → 返回 429 Too Many Requests
   └─ < 50 → 继续
   ↓
5. 生成 task_id (UUID)
   ↓
6. Base64 解码图片，保存到共享卷 /data/inputs/{task_id}/
   ↓
7. 生成 WebSocket 短期 Token，存入 Redis (TTL 5min)
   ↓
8. 将任务元数据（不含图片数据）推入 Redis 队列 (LPUSH)
   {
     "task_id": "uuid",
     "type": "face-swap",
     "input_path": "/data/inputs/{task_id}/",
     "params": {...},
     "created_at": "timestamp"
   }
   ↓
9. 返回 task_id、WebSocket URL、ws_token 给客户端
   ↓
10. Worker 从队列取任务 (BRPOP)
    ↓
11. Worker 检查 GPU 温度
    ├─ >= 85°C → 等待冷却后重试
    └─ < 85°C → 继续
    ↓
12. Worker 更新任务状态为 "processing"
    ↓
13. Worker 从共享卷读取输入图片
    ↓
14. Worker 加载对应 Workflow JSON 模板，替换参数
    ↓
15. Worker 调用 ComfyUI API 提交 Workflow
    ↓
16. ComfyUI 处理中，Worker 轮询进度，更新到 Redis
    ↓
17. FastAPI 通过 Redis Pub/Sub 推送进度到 WebSocket
    ↓
18. 处理完成，Worker 从 ComfyUI 输出目录获取结果图片
    ↓
19. Worker 上传图片到 R2
    ├─ 成功 → HeadObject 验证 → 保存 URL
    └─ 失败 → 重试 3 次（指数退避）
    ↓
20. Worker 更新任务状态为 "completed"，保存结果 URL
    ↓
21. Worker 清理本地临时文件
    - 删除 /data/inputs/{task_id}/
    - 删除 ComfyUI output 中对应文件
    ↓
22. WebSocket 推送完成消息
    ↓
23. 如有 webhook_url，POST 通知客户端
    ↓
24. 客户端从 R2 下载结果
```

### 5.2 Redis 数据结构

#### 任务队列 (List)
```
Key: task:queue
Type: List
Value: JSON 序列化的任务元数据（不含图片 Base64）
Max Length: 50（API 层控制）
```

#### 任务状态 (Hash)
```
Key: task:status:{task_id}
Type: Hash
TTL: 7 天
Fields:
  - type: face-swap | upscale | remove-background
  - status: queued | processing | completed | failed | cancelled
  - created_at: ISO 8601 timestamp
  - started_at: ISO 8601 timestamp (可选)
  - completed_at: ISO 8601 timestamp (可选)
  - progress: 0-100
  - result_url: string (可选)
  - error: string (可选)
  - input_path: string
```

#### 进度信息 (Hash)
```
Key: task:progress:{task_id}
Type: Hash
TTL: 24 小时
Fields:
  - current_step: int
  - total_steps: int
  - message: string
  - percentage: int
```

#### WebSocket Token (String)
```
Key: ws:token:{token_value}
Type: String
TTL: 5 分钟
Value: task_id（绑定到特定任务）
```

#### 进度频道 (Pub/Sub)
```
Channel: task:progress:{task_id}
用于实时推送进度到 FastAPI WebSocket 连接
```

### 5.3 共享卷文件结构

> **v2 新增**: 明确本地临时文件存储方案。

```
/data/
├── inputs/                    # 输入图片（API 写入，Worker 读取后清理）
│   └── {task_id}/
│       ├── source.png
│       └── target.png         # 仅换脸任务
└── temp/                      # Worker 处理中间文件
    └── {task_id}/
```

### 5.4 R2 存储结构

```
bucket-name/
├── face-swap/
│   ├── {task_id}.png
│   └── {task_id}_thumb.png  // 可选缩略图
├── upscale/
│   └── {task_id}.png
└── remove-background/
    ├── {task_id}.png
    └── {task_id}_mask.png  // 可选蒙版
```

---

## 6. 错误处理和重试机制

### 6.1 错误类型和处理

| 错误类型 | HTTP 状态 | 处理方式 | 是否重试 |
|---------|----------|---------|---------| 
| API Key 无效 | 401 | 立即返回错误 | 否 |
| 任务类型不支持 | 400 | 立即返回错误 | 否 |
| 图片格式不支持 | 400 | 立即返回错误 | 否 |
| 图片大小超限 | 413 | 立即返回错误（解码后 >10MB） | 否 |
| Base64 解码失败 | 400 | 立即返回错误 | 否 |
| 队列已满 | 429 | 返回 retry_after | 否（客户端重试）|
| GPU 温度过高 | - | Worker 暂停取新任务，等待冷却 | 是（自动）|
| ComfyUI 连接失败 | 503 | 标记任务失败，记录日志 | 是（3次）|
| ComfyUI 处理失败 | 500 | 标记任务失败，返回错误信息 | 否 |
| R2 上传失败 | 503 | 本地缓存 + 重试 | 是（3次）|
| 任务超时 | 504 | 标记任务失败 | 否 |
| Redis 连接失败 | 503 | 返回 503，记录日志 | 是（自动重连）|

### 6.2 任务超时配置

| 任务类型 | 超时时间 | 原因 |
|---------|---------|------|
| 换脸 | 60 秒 | 正常 3-8 秒，60 秒足够 |
| 图片放大 | 120 秒 | 大图片可能较慢 |
| 去背景 | 30 秒 | 正常 2-5 秒 |

### 6.3 重试策略

**指数退避重试**：
- 第 1 次重试：等待 1 秒
- 第 2 次重试：等待 2 秒
- 第 3 次重试：等待 4 秒

**重试条件**：
- 网络超时
- ComfyUI 临时不可用
- R2 上传临时失败

**不重试条件**：
- 参数错误
- API Key 无效
- 图片格式不支持
- ComfyUI 返回处理失败（非临时性错误）
- GPU OOM（需手动调整参数）

---

## 7. 配置管理

### 7.1 环境变量

```bash
# ====================
# API 配置
# ====================
API_KEYS=key1,key2,key3
API_PORT=8000
API_HOST=0.0.0.0
ALLOWED_ORIGINS=http://localhost:3000,http://192.168.1.*
MAX_IMAGE_SIZE_BYTES=10485760       # 10MB（Base64 解码后）
MAX_REQUEST_BODY_SIZE=15728640      # 15MB（Base64 编码膨胀约 33%，与 Nginx 对齐）
SUPPORTED_FORMATS=png,jpg,jpeg,webp

# ====================
# 队列保护
# ====================
MAX_QUEUE_LENGTH=50

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
# R2 配置
# ====================
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key
R2_BUCKET_NAME=ai-images
R2_PUBLIC_URL=https://your-bucket.r2.dev

# ====================
# Worker 配置
# ====================
WORKER_CONCURRENCY=1                # ⚠️ 8GB VRAM 建议从 1 开始，监控后调整
WORKER_POLL_INTERVAL=1              # 队列轮询间隔（秒）
GPU_TEMP_THRESHOLD=85               # GPU 温度阈值（°C），超过则暂停

# 任务超时配置
TASK_TIMEOUT_FACE_SWAP=60
TASK_TIMEOUT_UPSCALE=120
TASK_TIMEOUT_REMOVE_BG=30

# ====================
# Nginx 配置
# ====================
NGINX_PORT=80
NGINX_CLIENT_MAX_BODY_SIZE=15M      # 对齐 MAX_REQUEST_BODY_SIZE
NGINX_RATE_LIMIT=10                 # 每秒每 IP 请求数

# ====================
# WebSocket 配置
# ====================
WS_TOKEN_TTL=300                    # WebSocket Token 有效期（秒）
WS_HEARTBEAT_INTERVAL=30            # 服务端 ping 间隔（秒）
WS_HEARTBEAT_TIMEOUT=60             # pong 超时断开（秒）

# ====================
# 清理配置
# ====================
CLEANUP_INPUT_AFTER_HOURS=2         # 输入图片保留时间
CLEANUP_OUTPUT_AFTER_HOURS=24       # ComfyUI 输出保留时间
CLEANUP_INTERVAL_MINUTES=30         # 清理任务执行间隔

# ====================
# 日志配置
# ====================
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 7.2 配置文件结构

```
comfyui-server/
├── docker-compose.yml
├── .env
├── .env.example
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置加载
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── tasks.py         # 统一任务接口
│   │   └── health.py        # 健康检查
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── auth.py          # API Key 认证
│   ├── websocket/
│   │   ├── __init__.py
│   │   └── handler.py       # WebSocket 处理（Token 认证）
│   └── utils/
│       ├── __init__.py
│       ├── r2.py            # R2 上传工具
│       ├── redis.py         # Redis 工具
│       ├── image.py         # 图片验证和保存
│       └── token.py         # WebSocket Token 生成和验证
├── worker/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py              # Worker 入口
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── base.py          # 处理器基类
│   │   ├── face_swap.py     # 换脸处理
│   │   ├── upscale.py       # 放大处理
│   │   └── remove_bg.py     # 去背景处理
│   ├── workflows/           # Workflow JSON 模板
│   │   ├── face_swap.json
│   │   ├── upscale.json
│   │   └── remove_background.json
│   └── utils/
│       ├── __init__.py
│       ├── comfyui.py       # ComfyUI API 客户端
│       ├── r2.py            # R2 上传工具
│       ├── gpu_monitor.py   # GPU 温度监控
│       └── cleanup.py       # 临时文件清理
├── comfyui/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── models/              # 模型文件（挂载为 Docker Volume）
│       ├── checkpoints/
│       ├── lora/
│       ├── upscale/
│       ├── face_swap/
│       └── rmbg/
├── nginx/
│   └── default.conf
└── docs/
    └── design/
        └── comfyui-ai-image-server-design.md
```

---

## 8. 安全性设计

### 8.1 认证和授权

**API Key 认证**：
- 存储在环境变量 `API_KEYS` 中，逗号分隔
- 所有 API 请求必须在 Header 中携带 `X-API-Key`
- 未来迁移方向：将 API Key 存入 Redis，支持动态增删和配额控制

**WebSocket Token 认证**：
> **v2 变更**: 使用短期 Token 替代 URL 中直接传递 API Key。

- 任务创建时生成 `ws_token`，绑定到特定 `task_id`
- Token 存储在 Redis，TTL 5 分钟
- WebSocket 连接时通过 `?token=xxx` 传递
- Token 一次性使用，连接建立后立即从 Redis 删除

**API Key 生成**：
```bash
openssl rand -hex 32
```

### 8.2 网络隔离

> **v2 变更**: 明确 Nginx 是唯一同时加入两个网络的服务。

```
external-network (对外，bridge)
  └─ nginx

internal-network (内部，bridge + internal: true)
  ├─ nginx (双网络)
  ├─ api
  ├─ worker
  ├─ comfyui
  └─ redis
```

**关键隔离规则**：
- `internal-network` 设置 `internal: true`，容器无法直接被宿主机外部访问
- API 服务不映射端口到宿主机，只通过 Nginx 内部网络名访问
- ComfyUI 不对外暴露，只通过 Docker 内部网络访问
- Redis 不对外暴露，不设置密码（内部网络隔离即可）

### 8.3 输入验证

**图片验证（双层保护）**：

| 检查层 | 检查项 | 限制 |
|--------|-------|------|
| Nginx | 请求体大小 | `client_max_body_size 15M` |
| FastAPI | Base64 解码后图片大小 | 最大 10MB |
| FastAPI | 图片格式 | 只允许 PNG, JPG, JPEG, WEBP |
| FastAPI | 图片魔数 (magic bytes) | 验证文件头与声明格式一致 |
| FastAPI | 图片尺寸 | 最大 4096x4096（防止放大时 OOM）|

**参数验证**：
- `type`: 只允许 `face-swap`, `upscale`, `remove-background`
- `scale_factor`: 只允许 2, 4, 8
- `task_id`: UUID 格式验证
- `webhook_url`: HTTP 或 HTTPS URL 格式验证（局域网允许 HTTP）

### 8.4 Nginx 限流

```nginx
# 限制每个 IP 每秒 10 个请求
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# 限制 WebSocket 连接数
limit_conn_zone $binary_remote_addr zone=ws_conn:10m;

server {
    listen 80;
    client_max_body_size 15M;

    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws/ {
        limit_conn ws_conn 10;  # 每 IP 最多 10 个 WebSocket 连接
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }

    location /health {
        proxy_pass http://api:8000;
    }
}
```

### 8.5 R2 权限配置

> **v2 变更**: 补充 HeadObject 权限用于上传验证。

**R2 API Token 权限**：
- `PutObject` — 上传图片
- `HeadObject` — 上传后验证文件完整性
- 不授予 `DeleteObject`（清理通过单独管理 Token 或 R2 生命周期规则处理）

**R2 生命周期规则（可选）**：
- 90 天自动删除所有对象（如不需要永久保留）

### 8.6 CORS 配置

> **v2 变更**: 允许局域网 HTTP（非仅 HTTPS）。

```
ALLOWED_ORIGINS=http://localhost:3000,http://192.168.1.*
```

---

## 9. 监控和日志

### 9.1 日志级别

| 组件 | 日志级别 | 内容 |
|------|---------|------|
| API | INFO | 请求日志、错误日志、性能日志 |
| Worker | INFO | 任务处理日志、GPU 温度日志、错误日志 |
| Nginx | INFO | 访问日志、错误日志 |
| ComfyUI | WARNING | 仅错误和警告 |

### 9.2 日志格式

**JSON 格式**：
```json
{
  "timestamp": "2026-03-26T12:00:00Z",
  "level": "INFO",
  "service": "worker",
  "message": "Task completed",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "face-swap",
  "processing_time": 15.2,
  "gpu_temp": 72,
  "vram_used_mb": 4200
}
```

### 9.3 健康检查端点

> **v2 变更**: 增加 GPU 温度和 VRAM 监控。

```
GET /health

Response (200 OK):
{
  "status": "healthy",
  "timestamp": "2026-03-26T12:00:00Z",
  "services": {
    "api": "ok",
    "redis": "ok",
    "comfyui": "ok",
    "r2": "ok"
  },
  "gpu": {
    "temperature": 68,
    "vram_total_mb": 8192,
    "vram_used_mb": 3200,
    "vram_free_mb": 4992,
    "utilization_percent": 45
  },
  "queue": {
    "pending": 5,
    "processing": 1,
    "max_length": 50
  },
  "disk": {
    "available_gb": 45.2,
    "inputs_size_mb": 120,
    "outputs_size_mb": 340
  }
}
```

**GPU 监控实现**：
```bash
# Worker 定期调用，解析输出
nvidia-smi --query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu \
  --format=csv,noheader,nounits
```

### 9.4 监控告警

| 指标 | 阈值 | 动作 |
|------|------|------|
| GPU 温度 | >= 85°C | Worker 暂停取新任务，日志记录 WARNING |
| GPU 温度 | >= 92°C | 发送告警（如有 webhook），拒绝新任务 |
| VRAM 占用 | >= 90% | 日志记录 WARNING |
| 队列积压 | >= 40/50 | 日志记录 WARNING |
| 磁盘可用 | <= 5GB | 触发紧急清理，日志记录 ERROR |
| 任务失败率 | >= 20% (最近 100 任务) | 日志记录 ERROR |

---

## 10. 性能优化

### 10.1 并发配置

> **v2 变更**: 默认并发数从 2 调整为 1。

**Worker 配置**：
```bash
WORKER_CONCURRENCY=1  # ⚠️ 首次部署使用 1
```

**调优流程**：
1. 以 `WORKER_CONCURRENCY=1` 启动
2. 分别测试三种任务，记录 VRAM 峰值使用量
3. 如果最大 VRAM 占用 < 4GB，可尝试 `WORKER_CONCURRENCY=2`
4. 同时运行两种任务，确认 VRAM 不超 7.5GB（留 0.5GB buffer）
5. 监控 GPU 温度是否持续高于 80°C

**Worker 扩展（未来多 GPU）**：
```bash
docker-compose up --scale worker=2
```

### 10.2 缓存策略

| 数据类型 | 存储位置 | TTL | 说明 |
|---------|---------|-----|------|
| 任务进度 | Redis Hash | 24 小时 | 任务完成后逐渐失效 |
| 任务状态 | Redis Hash | 7 天 | 客户端可查询历史任务 |
| WebSocket Token | Redis String | 5 分钟 | 一次性使用 |
| 输入图片 | 共享卷 | 2 小时 | Worker 处理完后清理 |
| ComfyUI 输出 | ComfyUI 卷 | 24 小时 | 定时清理 |

### 10.3 GPU 资源管理

**CUDA 内存管理**：
- ComfyUI 自动管理 VRAM 分配和回收
- 8GB VRAM 在 `WORKER_CONCURRENCY=1` 下可处理所有任务类型
- 图片放大（特别是 4x/8x）对 VRAM 需求最高，建议限制输入分辨率

**输入图片分辨率限制（建议）**：

| 任务类型 | 最大输入分辨率 | 原因 |
|---------|-------------|------|
| 换脸 | 4096x4096 | 内部会缩放人脸区域 |
| 放大 2x | 2048x2048 | 输出 4096x4096 约占 4GB VRAM |
| 放大 4x | 1024x1024 | 输出 4096x4096 约占 6GB VRAM |
| 放大 8x | 512x512 | 输出 4096x4096 约占 7GB VRAM |
| 去背景 | 4096x4096 | 较低 VRAM 需求 |

### 10.4 磁盘清理策略

> **v2 新增**: 防止 79GB 磁盘被临时文件占满。

**自动清理任务**（Worker 内嵌定时任务）：

```python
# 每 30 分钟执行一次
async def cleanup_task():
    # 1. 清理超过 2 小时的输入图片
    cleanup_directory("/data/inputs/", max_age_hours=2)
    
    # 2. 清理超过 24 小时的 ComfyUI 输出
    cleanup_directory("/app/ComfyUI/output/", max_age_hours=24)
    
    # 3. 清理超过 24 小时的临时文件
    cleanup_directory("/data/temp/", max_age_hours=24)
    
    # 4. 如果磁盘可用 < 5GB，紧急清理（保留最近 1 小时）
    if get_disk_free_gb() < 5:
        emergency_cleanup(keep_hours=1)
```

**磁盘空间估算**：

| 项目 | 预估大小 |
|------|---------|
| Docker 镜像（所有服务） | ~10GB |
| AI 模型文件 | ~2GB |
| Redis 数据 | ~0.5GB |
| 临时文件（峰值） | ~5GB |
| 系统和其他 | ~5GB |
| **可用于处理** | **~56GB** |

---

## 11. 部署流程

### 11.1 初始部署

```bash
# 1. 前置检查（见第 1 节"部署前置检查清单"）

# 2. 克隆项目
cd /home/abel/comfyui-server

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入实际配置

# 4. 生成 API Key
echo "API_KEYS=$(openssl rand -hex 32)" >> .env

# 5. 下载模型文件
mkdir -p comfyui/models/{face_swap,upscale,rmbg}
# 按第 4 节下载地址，将模型放入对应目录

# 6. 构建并启动服务
docker-compose build
docker-compose up -d

# 7. 检查服务状态
docker-compose ps
curl http://localhost/health

# 8. 查看日志
docker-compose logs -f

# 9. 测试 GPU 访问
docker-compose exec comfyui nvidia-smi

# 10. 运行端到端测试
curl -X POST http://localhost/api/tasks \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type": "remove-background", "images": {"source": "BASE64..."}}'
```

### 11.2 更新部署

```bash
# 拉取最新代码
git pull

# 重建镜像
docker-compose build

# 重启服务（等待队列清空后）
docker-compose up -d

# 或使用 rolling update（零停机，仅更新 Worker）
docker-compose up -d --no-deps --build worker
```

### 11.3 笔记本作为服务器的注意事项

> **v2 新增**: 针对笔记本部署的运维建议。

1. **散热**：使用散热底座，保持通风良好。避免合盖运行（除非 BIOS 支持合盖不休眠且散热口不被阻挡）。
2. **电源**：始终接通电源适配器，BIOS 中设置为"高性能"电源模式。
3. **休眠/睡眠**：关闭自动休眠和屏幕自动关闭（`systemctl mask sleep.target suspend.target`）。
4. **系统更新**：关闭自动更新重启，手动选择维护窗口更新。
5. **GPU 温度监控**：建议在 Worker 日志中每 5 分钟输出一次 GPU 温度，方便事后排查。
6. **UPS**：如条件允许，接 UPS 防止意外断电导致数据损坏。

---

## 12. 测试计划

### 12.1 单元测试

- API 接口测试（统一入口各 type 分发）
- 输入验证测试（图片格式、大小、魔数检查）
- WebSocket Token 生成和验证
- Redis 队列操作（LPUSH、BRPOP、队列长度检查）
- R2 上传和验证（PutObject + HeadObject）
- GPU 温度读取和阈值判断

### 12.2 集成测试

- 完整任务流程测试（提交 → 处理 → 上传 → 返回结果）
- 任务取消测试（队列中取消、处理中取消）
- 错误处理测试（无效图片、ComfyUI 超时、R2 上传失败）
- WebSocket 进度推送测试
- Webhook 回调测试

### 12.3 性能测试

- 单任务 VRAM 占用测量（三种任务类型分别测试）
- 并发任务 VRAM 占用（验证 WORKER_CONCURRENCY 设置）
- GPU 温度长时间运行监控（持续 1 小时满载）
- 磁盘清理策略验证

### 12.4 负载测试

- 使用 Locust 或 Apache Bench
- 测试 50 个任务快速提交（验证队列保护）
- 测试 WebSocket 多连接稳定性
- 测试任务积压恢复（队列清空后的处理速度）

---

## 13. 未来扩展

### 13.1 短期可选功能

1. **API Key 动态管理**
   - 将 API Key 迁移到 Redis
   - 支持 CRUD 操作（无需重启）
   - 配额控制（每 Key 每日限额）

2. **Web 管理界面**
   - 任务队列监控
   - 任务历史查询
   - GPU 状态实时仪表盘
   - 统计图表

3. **CDN 集成**
   - 使用 Cloudflare CDN 加速 R2 图片访问
   - 图片缩略图自动生成

### 13.2 中期扩展功能

1. **更多 AI 功能**
   - 图片风格迁移
   - 图片修复 (Inpainting)
   - ControlNet 支持
   - 文生图 (Text-to-Image)

2. **用户系统**
   - 用户注册和登录（JWT）
   - 配额管理
   - 使用统计和账单

### 13.3 长期性能优化

1. **多 GPU 支持**
   - 任务分配到不同 GPU
   - GPU 负载均衡

2. **分布式部署**
   - 多台服务器部署
   - 统一任务队列（Redis Cluster 或 RabbitMQ）

3. **模型优化**
   - 使用量化模型减少 VRAM 占用
   - 使用 TensorRT 加速推理

---

## 14. 参考资源

### 14.1 官方文档

- [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI)
- [ComfyUI Documentation](https://docs.comfy.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)

### 14.2 模型下载

- [ReActor Face Swap](https://huggingface.co/Gourieff/ReActor)
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN)
- [RMBG-1.4](https://huggingface.co/briaai/RMBG-1.4)

### 14.3 ComfyUI 节点

- [ComfyUI Manager](https://github.com/ltdrdata/ComfyUI-Manager)
- [ComfyUI Custom Scripts](https://github.com/pythongosssss/ComfyUI-Custom-Scripts)

---

## 15. 附录

### 15.1 端口使用

| 服务 | 端口 | 对外暴露 | 网络 |
|------|------|---------|------|
| Nginx | 80 | 是 | external + internal |
| FastAPI | 8000 | 否（仅内网） | internal |
| Redis | 6379 | 否（仅内网） | internal |
| ComfyUI | 8188 | 否（仅内网） | internal |

### 15.2 目录权限

```bash
# 确保以下目录有正确的权限
mkdir -p comfyui/models/{checkpoints,lora,upscale,face_swap,rmbg}
chmod -R 755 comfyui/models/

# 共享卷目录（Docker 会自动创建）
# /data/inputs/ — API 服务写入，Worker 读取
# /data/temp/   — Worker 读写
```

### 15.3 故障排查

**ComfyUI 无法启动**：
```bash
# 检查 GPU 是否可用
docker-compose exec comfyui nvidia-smi

# 检查 CUDA 版本匹配
docker-compose exec comfyui python -c "import torch; print(torch.cuda.is_available())"

# 查看 ComfyUI 日志
docker-compose logs comfyui
```

**Worker 无法处理任务**：
```bash
# 检查 Redis 连接
docker-compose exec worker redis-cli -h redis ping

# 检查队列状态
docker-compose exec worker redis-cli -h redis LLEN task:queue

# 查看 Worker 日志
docker-compose logs worker
```

**GPU 温度过高**：
```bash
# 查看实时 GPU 状态
docker-compose exec comfyui nvidia-smi -l 5

# 查看 Worker 是否已暂停
docker-compose logs worker | grep "temperature"
```

**R2 上传失败**：
```bash
# 检查 R2 配置
docker-compose exec api env | grep R2

# 测试 R2 连接
docker-compose exec api python -c "from utils.r2 import R2Client; R2Client().test_connection()"
```

**磁盘空间不足**：
```bash
# 查看磁盘使用
df -h

# 查看临时文件占用
du -sh /var/lib/docker/volumes/comfyui-server_shared-data/_data/inputs/
du -sh /var/lib/docker/volumes/comfyui-server_comfyui-output/_data/

# 手动触发清理（如 Worker 清理任务未生效）
docker-compose exec worker python -c "from utils.cleanup import emergency_cleanup; emergency_cleanup(keep_hours=1)"
```

### 15.4 v1 → v2 变更摘要

| 变更项 | v1 | v2 | 原因 |
|--------|----|----|------|
| CUDA 版本 | 13.0 | 部署前确认 | 13.0 不存在 |
| GPU 透传 | 未配置 | docker-compose deploy.resources | 容器内无法访问 GPU |
| Worker 并发 | 2 | 1 | 8GB VRAM 避免 OOM |
| API 接口 | 3 个独立接口 | 1 个统一接口 | 便于扩展维护 |
| WebSocket 认证 | URL 中 API Key | 短期 Token | 避免 Key 泄露 |
| 图片存储 | 未说明 | 共享卷 /data/ | 避免大数据存入 Redis |
| Workflow 管理 | 未说明 | workflows/ JSON 模板 | Worker 需要模板 |
| 队列保护 | 无限制 | 最大 50 任务 | 防止积压 |
| 心跳方向 | 客户端 ping | 服务端 ping | RFC 6455 标准 |
| Webhook URL | 仅 HTTPS | HTTP + HTTPS | 局域网兼容 |
| GPU 温度监控 | 无 | 健康检查 + Worker 暂停 | 笔记本散热 |
| 磁盘清理 | 无 | 定时清理策略 | 79GB 防满 |
| R2 权限 | PutObject | PutObject + HeadObject | 上传验证 |
| 任务取消 | 无 | DELETE /api/tasks/{id} | 用户体验 |
| 批量查询 | 无 | GET /api/tasks?status=... | 用户体验 |
| 请求体限制 | Nginx 10M | Nginx 15M + API 10MB | Base64 膨胀对齐 |
| 文档路径 | docs/superpowers/specs/ | docs/design/ | 清理残留 |

---

**文档结束**
