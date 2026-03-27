# ComfyUI AI 图片处理服务器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个基于 ComfyUI 的局域网 AI 图片处理服务，提供换脸、图片放大、去背景功能的 RESTful API 和 WebSocket 进度推送。

**Architecture:**
- Docker Compose 编排 5 个服务（Nginx + FastAPI + Redis + Worker + ComfyUI）
- 双网络隔离（external-network 对外 + internal-network 内部隔离）
- 共享卷传递图片，Redis 队列传递任务元数据
- ComfyUI 后端 GPU 加速处理，Worker 上传结果到 R2

**Tech Stack:**
- Python 3.12, FastAPI, Redis, ComfyUI
- Docker & Docker Compose, NVIDIA Container Toolkit
- Cloudflare R2 (AWS S3 SDK)
- Nginx 反向代理, WebSocket

---

## 任务分组

**Phase 1: 项目基础设施** (Tasks 1-8)
**Phase 2: API 服务** (Tasks 9-26)
**Phase 3: Worker 任务处理器** (Tasks 27-44)
**Phase 4: ComfyUI 后端** (Tasks 45-52)
**Phase 5: Nginx 反向代理** (Tasks 53-57)
**Phase 6: 集成测试** (Tasks 58-61)

---

## Phase 1: 项目基础设施

### Task 1: 创建项目目录结构

**Files:**
- Create: `api/`, `worker/`, `comfyui/`, `nginx/`, `docs/`
- Create: `api/routers/`, `api/middleware/`, `api/websocket/`, `api/utils/`
- Create: `worker/processors/`, `worker/workflows/`, `worker/utils/`
- Create: `comfyui/models/{face_swap,upscale,rmbg}/`

- [ ] **Step 1: 创建完整目录结构**

```bash
cd /home/abel/comfyui-server

# API 服务目录
mkdir -p api/routers api/middleware api/websocket api/utils
mkdir -p api/tests

# Worker 目录
mkdir -p worker/processors worker/workflows worker/utils
mkdir -p worker/tests

# ComfyUI 目录
mkdir -p comfyui/models/{face_swap,upscale,rmbg}

# Nginx 目录
mkdir -p nginx

# 文档目录
mkdir -p docs/design

# 创建 .gitkeep
touch api/routers/__init__.py api/middleware/__init__.py api/websocket/__init__.py api/utils/__init__.py
touch worker/processors/__init__.py worker/utils/__init__.py
```

- [ ] **Step 2: 验证目录创建**

```bash
tree -L 3 -d
```

Expected output: 目录树显示 api/, worker/, comfyui/, nginx/, docs/ 及其子目录

- [ ] **Step 3: 提交**

```bash
git add .
git commit -m "feat: create project directory structure"
```

---

### Task 2: 创建 Docker Compose 配置文件

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: 创建 docker-compose.yml**

```yaml
version: "3.8"

networks:
  external-network:
    driver: bridge
  internal-network:
    driver: bridge
    internal: true

volumes:
  shared-data:
  comfyui-models:
  comfyui-output:
  redis-data:

services:
  nginx:
    image: nginx:alpine
    ports:
      - "${NGINX_PORT:-80}:80"
    networks:
      - external-network
      - internal-network
    depends_on:
      - api
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
    restart: unless-stopped

  api:
    build: ./api
    networks:
      - internal-network
    volumes:
      - shared-data:/data
    depends_on:
      - redis
    env_file: .env
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped

  redis:
    image: redis:alpine
    networks:
      - internal-network
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    restart: unless-stopped

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
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped

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
    restart: unless-stopped
```

- [ ] **Step 2: 创建 .env.example**

```bash
# ====================
# API 配置
# ====================
API_KEYS=your-api-key-here
API_PORT=8000
API_HOST=0.0.0.0
ALLOWED_ORIGINS=http://localhost:3000,http://192.168.1.*
MAX_IMAGE_SIZE_BYTES=10485760
MAX_REQUEST_BODY_SIZE=15728640
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

- [ ] **Step 3: 创建 .env 文件（从 .env.example 复制）**

```bash
cp .env.example .env
openssl rand -hex 32 | xargs -I {} sed -i "s/your-api-key-here/{}/" .env
```

- [ ] **Step 4: 提交**

```bash
git add docker-compose.yml .env.example .env
git commit -m "feat: add docker compose configuration and environment variables"
```

---

### Task 3: 创建 API Dockerfile

**Files:**
- Create: `api/Dockerfile`
- Create: `api/requirements.txt`

- [ ] **Step 1: 创建 API Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/logs

# 暴露端口（内部网络使用）
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 API requirements.txt**

```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
websockets==12.0
redis==5.0.1
boto3==1.34.19
pydantic==2.5.3
pydantic-settings==2.1.0
python-multipart==0.0.6
pillow==10.2.0
python-dotenv==1.0.0
httpx==0.26.0
```

- [ ] **Step 3: 提交**

```bash
git add api/Dockerfile api/requirements.txt
git commit -m "feat: add API Dockerfile and dependencies"
```

---

### Task 4: 创建 Worker Dockerfile

**Files:**
- Create: `worker/Dockerfile`
- Create: `worker/requirements.txt`

- [ ] **Step 1: 创建 Worker Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/logs /data/inputs /data/temp

# 启动命令
CMD ["python", "main.py"]
```

- [ ] **Step 2: 创建 Worker requirements.txt**

```txt
redis==5.0.1
boto3==1.34.19
requests==2.31.0
pillow==10.2.0
python-dotenv==1.0.0
pydantic==2.5.3
```

- [ ] **Step 3: 提交**

```bash
git add worker/Dockerfile worker/requirements.txt
git commit -m "feat: add Worker Dockerfile and dependencies"
```

---

### Task 5: 创建 ComfyUI Dockerfile

**Files:**
- Create: `comfyui/Dockerfile`
- Create: `comfyui/entrypoint.sh`

- [ ] **Step 1: 创建 ComfyUI Dockerfile**

```dockerfile
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    git \
    wget \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境
RUN python3.10 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# 克隆 ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI

WORKDIR /app/ComfyUI

# 安装 ComfyUI 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 ComfyUI Manager（用于管理自定义节点）
RUN pip install --no-cache-dir git+https://github.com/ltdrdata/ComfyUI-Manager.git

# 安装必要节点（将在首次启动时通过 Manager 安装）
# ReActor Face Swap
# RMBG-1.4

# 复制启动脚本
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# 暴露端口（内部网络使用）
EXPOSE 8188

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8188/system_stats || exit 1

# 启动命令
CMD ["/app/entrypoint.sh"]
```

- [ ] **Step 2: 创建 entrypoint.sh**

```bash
#!/bin/bash

set -e

echo "Starting ComfyUI server..."

# 启动 ComfyUI（仅监听内部网络）
cd /app/ComfyUI

python main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --enable-cors-header * \
    --disable-auto-launch \
    --disable-xformers
```

- [ ] **Step 3: 提交**

```bash
git add comfyui/Dockerfile comfyui/entrypoint.sh
git commit -m "feat: add ComfyUI Dockerfile with CUDA support"
```

---

### Task 6: 创建配置加载模块

**Files:**
- Create: `api/config.py`

- [ ] **Step 1: 创建配置类**

```python
# api/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    # API 配置
    api_keys: list[str] = Field(default_factory=list)
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    max_image_size_bytes: int = 10485760  # 10MB
    max_request_body_size: int = 15728640  # 15MB
    supported_formats: list[str] = Field(default_factory=lambda: ["png", "jpg", "jpeg", "webp"])

    # 队列配置
    max_queue_length: int = 50

    # Redis 配置
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    redis_max_memory: str = "512mb"

    # ComfyUI 配置
    comfyui_host: str = "http://comfyui:8188"
    comfyui_timeout: int = 300

    # R2 配置
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""

    # WebSocket 配置
    ws_token_ttl: int = 300  # 5 minutes
    ws_heartbeat_interval: int = 30
    ws_heartbeat_timeout: int = 60

    # 日志配置
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @classmethod
    def from_env(cls):
        """从环境变量加载配置"""
        api_keys_str = os.getenv("API_KEYS", "")
        api_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]

        allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
        allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]

        supported_formats_str = os.getenv("SUPPORTED_FORMATS", "png,jpg,jpeg,webp")
        supported_formats = [f.strip().lower() for f in supported_formats_str.split(",") if f.strip()]

        return cls(
            api_keys=api_keys,
            allowed_origins=allowed_origins,
            supported_formats=supported_formats,
            api_port=int(os.getenv("API_PORT", "8000")),
            max_image_size_bytes=int(os.getenv("MAX_IMAGE_SIZE_BYTES", "10485760")),
            max_queue_length=int(os.getenv("MAX_QUEUE_LENGTH", "50")),
            redis_host=os.getenv("REDIS_HOST", "redis"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            comfyui_host=os.getenv("COMFYUI_HOST", "http://comfyui:8188"),
            r2_account_id=os.getenv("R2_ACCOUNT_ID", ""),
            r2_access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
            r2_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
            r2_bucket_name=os.getenv("R2_BUCKET_NAME", ""),
            r2_public_url=os.getenv("R2_PUBLIC_URL", ""),
        )

# 全局配置实例
settings = Settings.from_env()
```

- [ ] **Step 2: 测试配置加载**

```bash
cd /home/abel/comfyui-server/api
python -c "from config import settings; print(f'API Keys: {len(settings.api_keys)}'); print(f'Redis: {settings.redis_host}:{settings.redis_port}')"
```

Expected output: 显示配置已加载

- [ ] **Step 3: 提交**

```bash
git add api/config.py
git commit -m "feat: add configuration module with environment variable support"
```

---

### Task 7: 创建 Redis 工具类

**Files:**
- Create: `api/utils/redis.py`

- [ ] **Step 1: 创建 Redis 客户端工具**

```python
# api/utils/redis.py
import redis
import json
import logging
from typing import Optional, Any
from config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password if settings.redis_password else None,
            db=settings.redis_db,
            decode_responses=True,
            health_check_interval=30
        )

    def ping(self) -> bool:
        """检查 Redis 连接"""
        try:
            return self.client.ping()
        except redis.RedisError as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def push_task(self, task_data: dict) -> bool:
        """推送任务到队列"""
        try:
            task_json = json.dumps(task_data)
            self.client.lpush("task:queue", task_json)
            logger.info(f"Task {task_data['task_id']} pushed to queue")
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to push task: {e}")
            return False

    def get_queue_length(self) -> int:
        """获取当前队列长度"""
        try:
            return self.client.llen("task:queue")
        except redis.RedisError as e:
            logger.error(f"Failed to get queue length: {e}")
            return 0

    def set_task_status(self, task_id: str, status_data: dict, ttl: int = 604800) -> bool:
        """设置任务状态（默认 TTL 7 天）"""
        try:
            key = f"task:status:{task_id}"
            self.client.hset(key, mapping=status_data)
            self.client.expire(key, ttl)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set task status: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        try:
            key = f"task:status:{task_id}"
            data = self.client.hgetall(key)
            return data if data else None
        except redis.RedisError as e:
            logger.error(f"Failed to get task status: {e}")
            return None

    def set_progress(self, task_id: str, progress_data: dict, ttl: int = 86400) -> bool:
        """设置任务进度（默认 TTL 24 小时）"""
        try:
            key = f"task:progress:{task_id}"
            self.client.hset(key, mapping=progress_data)
            self.client.expire(key, ttl)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set progress: {e}")
            return False

    def get_progress(self, task_id: str) -> Optional[dict]:
        """获取任务进度"""
        try:
            key = f"task:progress:{task_id}"
            data = self.client.hgetall(key)
            return data if data else None
        except redis.RedisError as e:
            logger.error(f"Failed to get progress: {e}")
            return None

    def set_ws_token(self, token: str, task_id: str, ttl: int = 300) -> bool:
        """设置 WebSocket Token（默认 TTL 5 分钟）"""
        try:
            key = f"ws:token:{token}"
            self.client.setex(key, ttl, task_id)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set ws token: {e}")
            return False

    def get_ws_token_task_id(self, token: str) -> Optional[str]:
        """验证 WebSocket Token 并获取 task_id"""
        try:
            key = f"ws:token:{token}"
            task_id = self.client.get(key)
            # Token 一次性使用，删除
            self.client.delete(key)
            return task_id
        except redis.RedisError as e:
            logger.error(f"Failed to get ws token: {e}")
            return None

    def publish_progress(self, task_id: str, message: dict) -> bool:
        """发布进度消息到 Pub/Sub"""
        try:
            channel = f"task:progress:{task_id}"
            self.client.publish(channel, json.dumps(message))
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to publish progress: {e}")
            return False

    def close(self):
        """关闭连接"""
        self.client.close()

# 全局实例
redis_client = RedisClient()
```

- [ ] **Step 2: 测试 Redis 连接（需先启动 Redis）**

```bash
docker-compose up -d redis
docker-compose exec api python -c "from utils.redis import redis_client; print(redis_client.ping())"
```

Expected output: `True`

- [ ] **Step 3: 提交**

```bash
git add api/utils/redis.py
git commit -m "feat: add Redis client utility with queue and pub/sub support"
```

---

### Task 8: 创建 R2 工具类

**Files:**
- Create: `api/utils/r2.py`

- [ ] **Step 1: 创建 R2 上传工具**

```python
# api/utils/r2.py
import boto3
from botocore.exceptions import ClientError
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

class R2Client:
    def __init__(self):
        self.endpoint_url = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name='auto'
        )
        self.bucket_name = settings.r2_bucket_name
        self.public_url = settings.r2_public_url

    def upload_image(self, task_id: str, task_type: str, image_data: bytes, filename: str = None) -> Optional[str]:
        """
        上传图片到 R2

        Args:
            task_id: 任务 ID
            task_type: 任务类型 (face-swap, upscale, remove-background)
            image_data: 图片二进制数据
            filename: 文件名（可选，默认使用 task_id.png）

        Returns:
            公共访问 URL，失败返回 None
        """
        if not filename:
            filename = f"{task_id}.png"

        # 根据任务类型确定存储路径
        prefix_map = {
            "face-swap": "face-swap",
            "upscale": "upscale",
            "remove-background": "remove-background"
        }
        prefix = prefix_map.get(task_type, "unknown")

        key = f"{prefix}/{filename}"

        try:
            # 上传图片
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=image_data,
                ContentType='image/png'
            )

            # 验证上传（HeadObject）
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )

            # 返回公共 URL
            url = f"{self.public_url}/{key}"
            logger.info(f"Successfully uploaded {key} to R2")
            return url

        except ClientError as e:
            logger.error(f"Failed to upload to R2: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading to R2: {e}")
            return None

    def test_connection(self) -> bool:
        """测试 R2 连接"""
        try:
            # 尝试列出 bucket
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info("R2 connection test successful")
            return True
        except ClientError as e:
            logger.error(f"R2 connection test failed: {e}")
            return False

# 全局实例
r2_client = R2Client() if settings.r2_access_key_id else None
```

- [ ] **Step 2: 创建测试脚本（需要配置 R2 后测试）**

```python
# api/tests/test_r2.py
import unittest
from utils.r2 import r2_client

class TestR2Client(unittest.TestCase):
    def test_connection(self):
        if r2_client:
            result = r2_client.test_connection()
            self.assertTrue(result)
        else:
            self.skipTest("R2 not configured")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 提交**

```bash
git add api/utils/r2.py api/tests/test_r2.py
git commit -m "feat: add R2 client utility with upload and verification"
```

---

## Phase 2: API 服务

### Task 9: 创建 API Key 认证中间件

**Files:**
- Create: `api/middleware/auth.py`

- [ ] **Step 1: 创建认证中间件**

```python
# api/middleware/auth.py
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from typing import Optional
from config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    验证 API Key

    Args:
        api_key: 从 Header 中提取的 API Key

    Returns:
        验证通过的 API Key

    Raises:
        HTTPException: API Key 无效
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required"
        )

    if api_key not in settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    return api_key
```

- [ ] **Step 2: 测试认证中间件**

```python
# api/tests/test_auth.py
import pytest
from fastapi import HTTPException
from middleware.auth import verify_api_key
from fastapi.security import Security

@pytest.mark.asyncio
async def test_valid_api_key(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "api_keys", ["test-key-123"])

    result = await verify_api_key("test-key-123")
    assert result == "test-key-123"

@pytest.mark.asyncio
async def test_missing_api_key():
    with pytest.raises(HTTPException) as exc:
        await verify_api_key(None)
    assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_invalid_api_key(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "api_keys", ["test-key-123"])

    with pytest.raises(HTTPException) as exc:
        await verify_api_key("wrong-key")
    assert exc.value.status_code == 401
```

- [ ] **Step 3: 运行测试**

```bash
cd /home/abel/comfyui-server/api
pytest tests/test_auth.py -v
```

Expected output: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add api/middleware/auth.py api/tests/test_auth.py
git commit -m "feat: add API Key authentication middleware"
```

---

### Task 10: 创建图片验证工具

**Files:**
- Create: `api/utils/image.py`

- [ ] **Step 1: 创建图片验证和处理工具**

```python
# api/utils/image.py
import base64
import io
from typing import tuple
from PIL import Image
import logging
from config import settings

logger = logging.getLogger(__name__)

# 图片魔数（Magic Bytes）用于验证真实格式
MAGIC_BYTES = {
    b'\x89PNG\r\n\x1a\n': 'png',
    b'\xff\xd8\xff': 'jpg',
    b'GIF87a': 'gif',
    b'GIF89a': 'gif',
    b'RIFF': 'webp',  # WEBP 文件以 RIFF...WEBP 开头
}

def decode_base64_image(data: str) -> tuple[bytes, str]:
    """
    解码 Base64 图片并验证格式

    Args:
        data: Base64 编码的图片数据

    Returns:
        (image_bytes, format) 元组

    Raises:
        ValueError: 解码失败或格式不支持
    """
    try:
        # 移除 Data URL 前缀（如果有）
        if ',' in data:
            data = data.split(',', 1)[1]

        # 解码 Base64
        image_bytes = base64.b64decode(data)

        # 验证大小
        if len(image_bytes) > settings.max_image_size_bytes:
            raise ValueError(f"Image size {len(image_bytes)} exceeds maximum {settings.max_image_size_bytes}")

        # 检测真实格式
        image_format = detect_format(image_bytes)

        if image_format not in settings.supported_formats:
            raise ValueError(f"Unsupported format: {image_format}. Supported: {settings.supported_formats}")

        return image_bytes, image_format

    except base64.binascii.Error as e:
        raise ValueError(f"Invalid Base64 encoding: {e}")
    except Exception as e:
        raise ValueError(f"Failed to decode image: {e}")

def detect_format(image_bytes: bytes) -> str:
    """
    通过魔数检测图片真实格式

    Args:
        image_bytes: 图片二进制数据

    Returns:
        格式字符串（小写）
    """
    for magic, fmt in MAGIC_BYTES.items():
        if image_bytes.startswith(magic):
            # WEBP 需要额外检查
            if fmt == 'webp':
                if b'WEBP' in image_bytes[:12]:
                    return 'webp'
                continue
            return fmt

    # 默认尝试通过 PIL 检测
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            return img.format.lower()
    except:
        return 'unknown'

def validate_image_dimensions(image_bytes: bytes, max_size: tuple = (4096, 4096)) -> bool:
    """
    验证图片尺寸

    Args:
        image_bytes: 图片二进制数据
        max_size: 最大尺寸 (width, height)

    Returns:
        是否符合尺寸要求

    Raises:
        ValueError: 尺寸超限
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
            max_width, max_height = max_size

            if width > max_width or height > max_height:
                raise ValueError(f"Image dimensions {width}x{height} exceed maximum {max_width}x{max_height}")

            return True

    except Exception as e:
        raise ValueError(f"Failed to validate dimensions: {e}")

def save_image_to_shared_volume(image_bytes: bytes, task_id: str, filename: str) -> str:
    """
    保存图片到共享卷

    Args:
        image_bytes: 图片二进制数据
        task_id: 任务 ID
        filename: 文件名

    Returns:
        完整文件路径
    """
    import os

    # 创建任务目录
    task_dir = f"/data/inputs/{task_id}"
    os.makedirs(task_dir, exist_ok=True)

    # 保存文件
    filepath = os.path.join(task_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)

    logger.info(f"Saved image to {filepath}")
    return filepath
```

- [ ] **Step 2: 创建图片验证测试**

```python
# api/tests/test_image.py
import pytest
import base64
from utils.image import decode_base64_image, detect_format, validate_image_dimensions

def test_decode_valid_png():
    # 创建一个小的 PNG 图片
    png_data = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'x' * 100).decode()
    image_bytes, fmt = decode_base64_image(png_data)
    assert fmt == 'png'

def test_decode_invalid_base64():
    with pytest.raises(ValueError) as exc:
        decode_base64_image("not-valid-base64!!!")
    assert "Invalid Base64" in str(exc.value)

def test_detect_format_png():
    fmt = detect_format(b'\x89PNG\r\n\x1a\n' + b'x' * 100)
    assert fmt == 'png'

def test_detect_format_jpg():
    fmt = detect_format(b'\xff\xd8\xff' + b'x' * 100)
    assert fmt == 'jpg'
```

- [ ] **Step 3: 运行测试**

```bash
cd /home/abel/comfyui-server/api
pytest tests/test_image.py -v
```

Expected output: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add api/utils/image.py api/tests/test_image.py
git commit -m "feat: add image validation and processing utilities"
```

---

### Task 11: 创建 WebSocket Token 工具

**Files:**
- Create: `api/utils/token.py`

- [ ] **Step 1: 创建 Token 生成和验证工具**

```python
# api/utils/token.py
import secrets
import logging
from typing import tuple
from config import settings

logger = logging.getLogger(__name__)

def generate_ws_token() -> str:
    """
    生成 WebSocket Token

    Returns:
        32 字节随机 Token（十六进制）
    """
    token = secrets.token_hex(32)
    return token

def save_ws_token(token: str, task_id: str, ttl: int = None) -> bool:
    """
    保存 WebSocket Token 到 Redis

    Args:
        token: Token 字符串
        task_id: 任务 ID
        ttl: 过期时间（秒），默认使用配置

    Returns:
        是否保存成功
    """
    from utils.redis import redis_client

    if ttl is None:
        ttl = settings.ws_token_ttl

    return redis_client.set_ws_token(token, task_id, ttl)

def validate_ws_token(token: str) -> str | None:
    """
    验证 WebSocket Token 并返回 task_id

    Args:
        token: Token 字符串

    Returns:
        任务 ID，验证失败返回 None
    """
    from utils.redis import redis_client

    task_id = redis_client.get_ws_token_task_id(token)

    if not task_id:
        logger.warning(f"Invalid or expired WebSocket token")
        return None

    return task_id
```

- [ ] **Step 2: 创建 Token 测试**

```python
# api/tests/test_token.py
import pytest
from utils.token import generate_ws_token, save_ws_token, validate_ws_token

def test_generate_token():
    token = generate_ws_token()
    assert isinstance(token, str)
    assert len(token) == 64  # 32 bytes = 64 hex chars

def test_save_and_validate_token():
    token = generate_ws_token()
    task_id = "test-task-123"

    # 保存 token
    assert save_ws_token(token, task_id, ttl=60)

    # 验证 token
    retrieved_task_id = validate_ws_token(token)
    assert retrieved_task_id == task_id

    # Token 是一次性的，第二次验证应该失败
    retrieved_task_id_2 = validate_ws_token(token)
    assert retrieved_task_id_2 is None
```

- [ ] **Step 3: 运行测试**

```bash
cd /home/abel/comfyui-server/api
pytest tests/test_token.py -v
```

Expected output: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add api/utils/token.py api/tests/test_token.py
git commit -m "feat: add WebSocket token generation and validation"
```

---

### Task 12: 创建任务数据模型

**Files:**
- Create: `api/models.py`

- [ ] **Step 1: 创建 Pydantic 模型**

```python
# api/models.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime

class TaskRequest(BaseModel):
    """统一任务请求模型"""
    type: Literal["face-swap", "upscale", "remove-background"]
    images: dict
    params: Optional[dict] = None
    webhook_url: Optional[str] = None

    @field_validator('images')
    def validate_images(cls, v, info):
        task_type = info.data.get('type')

        if task_type == "face-swap":
            if "source" not in v or "target" not in v:
                raise ValueError("face-swap requires 'source' and 'target' images")
        elif task_type in ("upscale", "remove-background"):
            if "source" not in v:
                raise ValueError(f"{task_type} requires 'source' image")

        return v

    @field_validator('params')
    def validate_params(cls, v, info):
        task_type = info.data.get('type')

        if task_type == "upscale" and v:
            scale_factor = v.get('scale_factor', 2)
            if scale_factor not in [2, 4, 8]:
                raise ValueError("scale_factor must be 2, 4, or 8")

        return v

class TaskResponse(BaseModel):
    """任务创建响应"""
    task_id: str
    status: Literal["queued"]
    websocket_url: str
    ws_token: str
    queue_position: int

class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    type: str
    status: Literal["queued", "processing", "completed", "failed", "cancelled"]
    progress: int
    result_url: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None

class TasksListResponse(BaseModel):
    """批量任务查询响应"""
    tasks: list[TaskStatusResponse]
    total: int
    limit: int
    offset: int

class ProgressMessage(BaseModel):
    """进度消息"""
    type: Literal["progress", "completed", "error"]
    timestamp: str
    data: dict

class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    details: Optional[str] = None
    retry_after: Optional[int] = None

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: str
    services: dict
    gpu: Optional[dict] = None
    queue: dict
    disk: Optional[dict] = None
```

- [ ] **Step 2: 测试模型验证**

```python
# api/tests/test_models.py
import pytest
from pydantic import ValidationError
from models import TaskRequest

def test_valid_face_swap_request():
    data = {
        "type": "face-swap",
        "images": {
            "source": "base64data...",
            "target": "base64data..."
        }
    }
    req = TaskRequest(**data)
    assert req.type == "face-swap"

def test_face_swap_missing_target():
    data = {
        "type": "face-swap",
        "images": {
            "source": "base64data..."
        }
    }
    with pytest.raises(ValidationError) as exc:
        TaskRequest(**data)
    assert "source" in str(exc.value).lower() or "target" in str(exc.value).lower()

def test_invalid_scale_factor():
    data = {
        "type": "upscale",
        "images": {"source": "base64data..."},
        "params": {"scale_factor": 3}
    }
    with pytest.raises(ValidationError) as exc:
        TaskRequest(**data)
    assert "scale_factor" in str(exc.value)
```

- [ ] **Step 3: 运行测试**

```bash
cd /home/abel/comfyui-server/api
pytest tests/test_models.py -v
```

Expected output: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add api/models.py api/tests/test_models.py
git commit -m "feat: add Pydantic models for request/response validation"
```

---

### Task 13: 创建 WebSocket 处理器

**Files:**
- Create: `api/websocket/handler.py`

- [ ] **Step 1: 创建 WebSocket 连接处理**

```python
# api/websocket/handler.py
from fastapi import WebSocket, WebSocketDisconnect, Query
from typing import Optional
import json
import asyncio
import logging
from datetime import datetime
from utils.token import validate_ws_token
from utils.redis import redis_client

logger = logging.getLogger(__name__)

class WebSocketHandler:
    def __init__(self, websocket: WebSocket, task_id: str):
        self.websocket = websocket
        self.task_id = task_id
        self.connected = True
        self.heartbeat_task: Optional[asyncio.Task] = None

    async def connect(self):
        """接受 WebSocket 连接"""
        await self.websocket.accept()
        logger.info(f"WebSocket connected for task {self.task_id}")

    async def send_progress(self, data: dict):
        """
        发送进度消息

        Args:
            data: 进度数据
        """
        if not self.connected:
            return

        message = {
            "type": "progress",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data
        }

        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send progress: {e}")
            self.connected = False

    async def send_completed(self, result_url: str, metadata: dict = None):
        """
        发送完成消息

        Args:
            result_url: 结果图片 URL
            metadata: 元数据
        """
        if not self.connected:
            return

        message = {
            "type": "completed",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "result_url": result_url,
                "metadata": metadata or {}
            }
        }

        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send completed: {e}")

    async def send_error(self, error: str, code: str = "UNKNOWN_ERROR", details: str = None):
        """
        发送错误消息

        Args:
            error: 错误描述
            code: 错误代码
            details: 详细信息
        """
        if not self.connected:
            return

        message = {
            "type": "error",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "error": error,
                "code": code,
                "details": details
            }
        }

        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send error: {e}")

    async def start_heartbeat(self, interval: int = 30, timeout: int = 60):
        """
        启动心跳检测

        Args:
            interval: ping 间隔（秒）
            timeout: pong 超时（秒）
        """
        async def heartbeat():
            while self.connected:
                try:
                    await asyncio.wait_for(
                        self.websocket.ping(),
                        timeout=timeout
                    )
                    await asyncio.sleep(interval)
                except asyncio.TimeoutError:
                    logger.warning(f"WebSocket heartbeat timeout for task {self.task_id}")
                    self.connected = False
                    break
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
                    self.connected = False
                    break

        self.heartbeat_task = asyncio.create_task(heartbeat())

    async def disconnect(self):
        """断开连接"""
        self.connected = False
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

        try:
            await self.websocket.close()
        except:
            pass

        logger.info(f"WebSocket disconnected for task {self.task_id}")

async def websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    token: str = Query(...),
    api_key: str = Query(None)
):
    """
    WebSocket 端点

    Args:
        websocket: WebSocket 连接
        task_id: 任务 ID
        token: WebSocket Token
        api_key: API Key（可选，用于兼容）
    """
    # 验证 Token
    validated_task_id = validate_ws_token(token)

    if not validated_task_id or validated_task_id != task_id:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    # 创建处理器
    handler = WebSocketHandler(websocket, task_id)

    try:
        # 接受连接
        await handler.connect()

        # 启动心跳
        await handler.start_heartbeat()

        # 订阅 Redis 进度频道
        pubsub = redis_client.client.pubsub()
        channel = f"task:progress:{task_id}"
        await pubsub.subscribe(channel)

        logger.info(f"Subscribed to progress channel: {channel}")

        # 监听进度消息
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    await handler.send_progress(data)

                    # 如果任务完成，断开连接
                    if data.get('status') == 'completed':
                        await asyncio.sleep(1)  # 确保消息发送完成
                        break
                    elif data.get('status') == 'failed':
                        await handler.send_error(
                            error=data.get('error', 'Task failed'),
                            code=data.get('error_code', 'TASK_FAILED')
                        )
                        break

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in progress message: {message['data']}")
                except Exception as e:
                    logger.error(f"Error handling progress message: {e}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected by client for task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
        await handler.send_error(str(e), "WEBSOCKET_ERROR")
    finally:
        await handler.disconnect()
        await pubsub.unsubscribe(channel)
```

- [ ] **Step 2: 提交**

```bash
git add api/websocket/handler.py
git commit -m "feat: add WebSocket handler with progress streaming and heartbeat"
```

---

### Task 14: 创建任务路由（统一接口）

**Files:**
- Create: `api/routers/tasks.py`

- [ ] **Step 1: 创建任务路由**

```python
# api/routers/tasks.py
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
import uuid
import os
from datetime import datetime
from config import settings
from models import (
    TaskRequest, TaskResponse, TaskStatusResponse,
    TasksListResponse, ErrorResponse
)
from middleware.auth import verify_api_key
from utils.redis import redis_client
from utils.image import decode_base64_image, save_image_to_shared_volume, validate_image_dimensions
from utils.token import generate_ws_token, save_ws_token
from config import settings

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.post("", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def create_task(
    request: TaskRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    创建任务（统一接口）

    支持的任务类型：
    - face-swap: 换脸
    - upscale: 图片放大
    - remove-background: 去背景
    """
    try:
        # 1. 检查队列长度
        queue_length = redis_client.get_queue_length()
        if queue_length >= settings.max_queue_length:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Queue is full",
                    "details": f"Current queue length: {queue_length}. Estimated wait time: ~{queue_length * 0.5:.0f} minutes.",
                    "retry_after": 60
                }
            )

        # 2. 生成 task_id
        task_id = str(uuid.uuid4())

        # 3. 解码并验证图片
        task_type = request.type

        if task_type == "face-swap":
            # 换脸需要两张图片
            source_bytes, source_fmt = decode_base64_image(request.images["source"])
            target_bytes, target_fmt = decode_base64_image(request.images["target"])

            # 验证尺寸
            validate_image_dimensions(source_bytes)
            validate_image_dimensions(target_bytes)

            # 保存到共享卷
            source_path = save_image_to_shared_volume(source_bytes, task_id, "source.png")
            target_path = save_image_to_shared_volume(target_bytes, task_id, "target.png")

        elif task_type in ("upscale", "remove-background"):
            # 放大和去背景只需一张图片
            source_bytes, source_fmt = decode_base64_image(request.images["source"])

            # 验证尺寸
            validate_image_dimensions(source_bytes)

            # 保存到共享卷
            source_path = save_image_to_shared_volume(source_bytes, task_id, "source.png")

        # 4. 生成 WebSocket Token
        ws_token = generate_ws_token()
        save_ws_token(ws_token, task_id)

        # 5. 准备任务元数据（不含图片 Base64）
        task_metadata = {
            "task_id": task_id,
            "type": task_type,
            "input_path": f"/data/inputs/{task_id}/",
            "params": request.params or {},
            "webhook_url": request.webhook_url,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }

        # 6. 推送到 Redis 队列
        redis_client.push_task(task_metadata)

        # 7. 设置初始任务状态
        redis_client.set_task_status(task_id, {
            "type": task_type,
            "status": "queued",
            "created_at": task_metadata["created_at"],
            "progress": "0"
        })

        # 8. 返回响应
        return TaskResponse(
            task_id=task_id,
            status="queued",
            websocket_url=f"ws://{settings.api_host}:{settings.api_port}/ws/task/{task_id}",
            ws_token=ws_token,
            queue_position=queue_length + 1
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "details": None}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Internal server error", "details": str(e)}
        )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """查询单个任务状态"""
    # 验证 UUID 格式
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id format"
        )

    # 从 Redis 获取状态
    status_data = redis_client.get_task_status(task_id)

    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    return TaskStatusResponse(
        task_id=task_id,
        type=status_data.get("type", "unknown"),
        status=status_data.get("status", "unknown"),
        progress=int(status_data.get("progress", 0)),
        result_url=status_data.get("result_url"),
        created_at=status_data.get("created_at", ""),
        completed_at=status_data.get("completed_at"),
        processing_time=float(status_data.get("processing_time")) if status_data.get("processing_time") else None,
        error=status_data.get("error")
    )


@router.get("", response_model=TasksListResponse)
async def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    api_key: str = Depends(verify_api_key)
):
    """批量查询任务（按状态筛选）"""
    # 注意：Redis 不支持直接查询所有 key，这里简化实现
    # 生产环境建议使用 Sorted Set 存储任务 ID

    # 暂时返回空列表，完整实现需要维护任务索引
    return TasksListResponse(
        tasks=[],
        total=0,
        limit=limit,
        offset=offset
    )


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def cancel_task(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """取消任务"""
    # 验证 UUID 格式
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id format"
        )

    # 获取当前状态
    status_data = redis_client.get_task_status(task_id)

    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    current_status = status_data.get("status")

    # 只能取消队列中或处理中的任务
    if current_status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "task_id": task_id,
                "status": current_status,
                "message": f"Task already {current_status}, cannot cancel"
            }
        )

    # 从队列中移除（如果是 queued 状态）
    if current_status == "queued":
        # 从 Redis 列表中删除（需要遍历查找）
        queue_length = redis_client.get_queue_length()
        for _ in range(queue_length):
            task_json = redis_client.client.rpop("task:queue")
            if task_json:
                import json
                task_data = json.loads(task_json)
                if task_data["task_id"] != task_id:
                    redis_client.client.lpush("task:queue", task_json)

    # 更新状态为 cancelled
    redis_client.set_task_status(task_id, {
        **status_data,
        "status": "cancelled",
        "error": "Task cancelled by user"
    })

    return {
        "task_id": task_id,
        "status": "cancelled",
        "message": "Task removed from queue"
    }
```

- [ ] **Step 2: 测试任务路由**

```python
# api/tests/test_tasks.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_create_task_requires_auth():
    response = client.post("/api/tasks", json={
        "type": "remove-background",
        "images": {"source": "invalid"}
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_create_face_swap_task(monkeypatch):
    # Mock API Key
    from config import settings
    monkeypatch.setattr(settings, "api_keys", ["test-key"])

    # 需要提供有效的 base64 图片
    import base64
    tiny_png = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'x' * 100).decode()

    response = client.post(
        "/api/tasks",
        json={
            "type": "face-swap",
            "images": {
                "source": tiny_png,
                "target": tiny_png
            }
        },
        headers={"X-API-Key": "test-key"}
    )

    # 注意：需要 Redis 运行
    assert response.status_code in [200, 503]  # 503 if Redis not available

    if response.status_code == 200:
        data = response.json()
        assert "task_id" in data
        assert "ws_token" in data
        assert data["status"] == "queued"
```

- [ ] **Step 3: 提交**

```bash
git add api/routers/tasks.py api/tests/test_tasks.py
git commit -m "feat: add unified task creation and status endpoints"
```

---

### Task 15: 创建健康检查路由

**Files:**
- Create: `api/routers/health.py`

- [ ] **Step 1: 创建健康检查端点**

```python
# api/routers/health.py
from fastapi import APIRouter
from datetime import datetime
import subprocess
import os
from config import settings
from models import HealthResponse
from utils.redis import redis_client
from utils.r2 import r2_client

router = APIRouter(prefix="/health", tags=["health"])

@router.get("", response_model=HealthResponse)
async def health_check():
    """
    健康检查端点

    检查项目：
    - API 服务状态
    - Redis 连接
    - ComfyUI 连接（通过 HTTP）
    - R2 连接
    - GPU 状态（通过 nvidia-smi）
    - 队列状态
    - 磁盘空间
    """
    services = {}
    gpu_info = None
    disk_info = None

    # 1. API 服务
    services["api"] = "ok"

    # 2. Redis
    services["redis"] = "ok" if redis_client.ping() else "failed"

    # 3. ComfyUI
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.comfyui_host}/system_stats")
            services["comfyui"] = "ok" if response.status_code == 200 else "failed"
    except:
        services["comfyui"] = "failed"

    # 4. R2
    if r2_client:
        services["r2"] = "ok" if r2_client.test_connection() else "failed"
    else:
        services["r2"] = "not_configured"

    # 5. GPU 信息（通过 nvidia-smi）
    try:
        result = subprocess.run(
            ['nvidia-smi',
             '--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            if len(parts) == 4:
                gpu_info = {
                    "temperature": int(parts[0]),
                    "vram_used_mb": int(parts[1]),
                    "vram_total_mb": int(parts[2]),
                    "vram_free_mb": int(parts[2]) - int(parts[1]),
                    "utilization_percent": int(parts[3])
                }
    except:
        pass

    # 6. 队列状态
    queue_length = redis_client.get_queue_length()
    queue_info = {
        "pending": queue_length,
        "processing": 0,  # 需要从 Worker 获取
        "max_length": settings.max_queue_length
    }

    # 7. 磁盘空间
    try:
        stat = os.statvfs('/data')
        available_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)

        # 计算输入和输出目录大小
        inputs_size = 0
        outputs_size = 0

        for dirpath, dirnames, filenames in os.walk('/data/inputs'):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                inputs_size += os.path.getsize(fp)

        disk_info = {
            "available_gb": round(available_gb, 2),
            "inputs_size_mb": round(inputs_size / (1024**2), 2),
            "outputs_size_mb": outputs_size  # ComfyUI output 挂载为不同 volume
        }
    except:
        pass

    # 判断整体健康状态
    overall_status = "healthy"
    if any(s == "failed" for s in services.values()):
        overall_status = "unhealthy"
    elif any(s == "degraded" for s in services.values()):
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat() + "Z",
        services=services,
        gpu=gpu_info,
        queue=queue_info,
        disk=disk_info
    )
```

- [ ] **Step 2: 测试健康检查**

```bash
# 启动必要的服务
docker-compose up -d redis

# 测试
curl http://localhost/health
```

Expected output: JSON 显示各服务状态

- [ ] **Step 3: 提交**

```bash
git add api/routers/health.py
git commit -m "feat: add health check endpoint with GPU and disk monitoring"
```

---

### Task 16: 创建 FastAPI 主应用

**Files:**
- Create: `api/main.py`

- [ ] **Step 1: 创建应用入口**

```python
# api/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
from config import settings
from routers import tasks, health
from websocket.handler import websocket_endpoint

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="ComfyUI AI Image Server",
    description="AI 图片处理服务：换脸、放大、去背景",
    version="2.0.0"
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tasks.router)
app.include_router(health.router)

# WebSocket 路由
@app.websocket("/ws/task/{task_id}")
async def websocket_route(task_id: str, request: Request):
    """WebSocket 端点包装"""
    from fastapi import Query, WebSocket
    from typing import Optional

    websocket = WebSocket(request.scope, receive=request.receive, send=request.send)

    # 获取查询参数
    token = request.query_params.get("token")

    await websocket_endpoint(websocket, task_id, token)

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "details": str(exc)}
    )

# 启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("Starting ComfyUI AI Image Server API...")
    logger.info(f"Allowed origins: {settings.allowed_origins}")
    logger.info(f"API Keys configured: {len(settings.api_keys)}")

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down ComfyUI AI Image Server API...")

# 根路径
@app.get("/")
async def root():
    return {
        "service": "ComfyUI AI Image Server",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "endpoints": {
            "tasks": "/api/tasks",
            "health": "/health",
            "websocket": "/ws/task/{task_id}"
        }
    }
```

- [ ] **Step 2: 测试应用启动**

```bash
cd /home/abel/comfyui-server/api
python -c "from main import app; print('App loaded successfully')"
```

Expected output: `App loaded successfully`

- [ ] **Step 3: 提交**

```bash
git add api/main.py
git commit -m "feat: add FastAPI main application with CORS and exception handling"
```

---

## Phase 3: Worker 任务处理器

### Task 17: 创建 Worker 配置加载

**Files:**
- Create: `worker/config.py`

- [ ] **Step 1: 创建 Worker 配置类**

```python
# worker/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
import os

class WorkerSettings(BaseSettings):
    # Redis 配置
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # ComfyUI 配置
    comfyui_host: str = "http://comfyui:8188"
    comfyui_timeout: int = 300

    # R2 配置
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""

    # Worker 配置
    worker_concurrency: int = 1
    worker_poll_interval: int = 1
    gpu_temp_threshold: int = 85

    # 任务超时配置
    task_timeout_face_swap: int = 60
    task_timeout_upscale: int = 120
    task_timeout_remove_bg: int = 30

    # 清理配置
    cleanup_input_after_hours: int = 2
    cleanup_output_after_hours: int = 24
    cleanup_interval_minutes: int = 30

    # 日志配置
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @classmethod
    def from_env(cls):
        """从环境变量加载配置"""
        return cls(
            redis_host=os.getenv("REDIS_HOST", "redis"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            comfyui_host=os.getenv("COMFYUI_HOST", "http://comfyui:8188"),
            comfyui_timeout=int(os.getenv("COMFYUI_TIMEOUT", "300")),
            r2_account_id=os.getenv("R2_ACCOUNT_ID", ""),
            r2_access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
            r2_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
            r2_bucket_name=os.getenv("R2_BUCKET_NAME", ""),
            r2_public_url=os.getenv("R2_PUBLIC_URL", ""),
            worker_concurrency=int(os.getenv("WORKER_CONCURRENCY", "1")),
            worker_poll_interval=int(os.getenv("WORKER_POLL_INTERVAL", "1")),
            gpu_temp_threshold=int(os.getenv("GPU_TEMP_THRESHOLD", "85")),
            task_timeout_face_swap=int(os.getenv("TASK_TIMEOUT_FACE_SWAP", "60")),
            task_timeout_upscale=int(os.getenv("TASK_TIMEOUT_UPSCALE", "120")),
            task_timeout_remove_bg=int(os.getenv("TASK_TIMEOUT_REMOVE_BG", "30")),
            cleanup_input_after_hours=int(os.getenv("CLEANUP_INPUT_AFTER_HOURS", "2")),
            cleanup_output_after_hours=int(os.getenv("CLEANUP_OUTPUT_AFTER_HOURS", "24")),
            cleanup_interval_minutes=int(os.getenv("CLEANUP_INTERVAL_MINUTES", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

# 全局配置实例
settings = WorkerSettings.from_env()
```

- [ ] **Step 2: 提交**

```bash
git add worker/config.py
git commit -m "feat: add worker configuration module"
```

---

### Task 18: 创建 Worker Redis 工具

**Files:**
- Create: `worker/utils/redis.py`

- [ ] **Step 1: 创建 Redis 队列工具**

```python
# worker/utils/redis.py
import redis
import json
import logging
from typing import Optional, dict
from config import settings

logger = logging.getLogger(__name__)

class WorkerRedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password if settings.redis_password else None,
            db=settings.redis_db,
            decode_responses=True
        )

    def pop_task(self, timeout: int = 5) -> Optional[dict]:
        """
        从队列中取出一个任务（阻塞）

        Args:
            timeout: 阻塞超时时间（秒）

        Returns:
            任务字典，超时返回 None
        """
        try:
            result = self.client.brpop("task:queue", timeout=timeout)
            if result:
                _, task_json = result
                return json.loads(task_json)
            return None
        except redis.RedisError as e:
            logger.error(f"Failed to pop task: {e}")
            return None

    def set_task_status(self, task_id: str, status_data: dict) -> bool:
        """设置任务状态"""
        try:
            key = f"task:status:{task_id}"
            self.client.hset(key, mapping=status_data)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set task status: {e}")
            return False

    def set_progress(self, task_id: str, progress_data: dict) -> bool:
        """设置任务进度"""
        try:
            key = f"task:progress:{task_id}"
            self.client.hset(key, mapping=progress_data)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set progress: {e}")
            return False

    def publish_progress(self, task_id: str, message: dict) -> bool:
        """发布进度消息"""
        try:
            channel = f"task:progress:{task_id}"
            self.client.publish(channel, json.dumps(message))
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to publish progress: {e}")
            return False

    def close(self):
        """关闭连接"""
        self.client.close()

# 全局实例
redis_client = WorkerRedisClient()
```

- [ ] **Step 2: 提交**

```bash
git add worker/utils/redis.py
git commit -m "feat: add worker Redis client with queue operations"
```

---

### Task 19: 创建 ComfyUI API 客户端

**Files:**
- Create: `worker/utils/comfyui.py`

- [ ] **Step 1: 创建 ComfyUI API 客户端**

```python
# worker/utils/comfyui.py
import requests
import json
import logging
from typing import dict
from config import settings

logger = logging.getLogger(__name__)

class ComfyUIClient:
    def __init__(self):
        self.base_url = settings.comfyui_host
        self.timeout = settings.comfyui_timeout

    def submit_workflow(self, workflow: dict) -> str:
        """
        提交 Workflow 到 ComfyUI

        Args:
            workflow: Workflow JSON

        Returns:
            prompt_id

        Raises:
            Exception: 提交失败
        """
        try:
            response = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow},
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            prompt_id = data.get("prompt_id")

            if not prompt_id:
                raise Exception("No prompt_id in response")

            logger.info(f"Workflow submitted: {prompt_id}")
            return prompt_id

        except requests.RequestException as e:
            logger.error(f"Failed to submit workflow: {e}")
            raise

    def get_history(self, prompt_id: str) -> dict:
        """
        获取 Workflow 执行历史

        Args:
            prompt_id: Prompt ID

        Returns:
            历史数据
        """
        try:
            response = requests.get(
                f"{self.base_url}/history/{prompt_id}",
                timeout=10
            )
            response.raise_for_status()

            return response.json()

        except requests.RequestException as e:
            logger.error(f"Failed to get history: {e}")
            return {}

    def get_queue_info(self) -> dict:
        """
        获取队列信息

        Returns:
            队列信息
        """
        try:
            response = requests.get(
                f"{self.base_url}/queue",
                timeout=10
            )
            response.raise_for_status()

            return response.json()

        except requests.RequestException as e:
            logger.error(f"Failed to get queue info: {e}")
            return {}

    def wait_for_completion(self, prompt_id: str, timeout: int = None) -> dict:
        """
        等待 Workflow 完成

        Args:
            prompt_id: Prompt ID
            timeout: 超时时间（秒）

        Returns:
            结果字典

        Raises:
            TimeoutError: 超时
            Exception: 执行失败
        """
        import time

        if timeout is None:
            timeout = self.timeout

        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Workflow execution timeout after {timeout}s")

            history = self.get_history(prompt_id)

            if prompt_id in history:
                data = history[prompt_id]

                # 检查是否完成
                if data.get("status", {}).get("completed", False):
                    logger.info(f"Workflow {prompt_id} completed")
                    return data

                # 检查是否有错误
                if data.get("status", {}).get("messages", {}):
                    messages = data["status"]["messages"]
                    for msg in messages:
                        if msg[0] == "execution_error":
                            error_str = json.dumps(msg[1], indent=2)
                            logger.error(f"Workflow execution error: {error_str}")
                            raise Exception(f"Workflow execution failed: {error_str}")

            time.sleep(1)

    def get_output_images(self, prompt_id: str) -> list:
        """
        获取输出图片路径

        Args:
            prompt_id: Prompt ID

        Returns:
            图片路径列表
        """
        history = self.get_history(prompt_id)

        if prompt_id not in history:
            return []

        data = history[prompt_id]
        outputs = data.get("outputs", {})

        image_paths = []

        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img in node_output["images"]:
                    # ComfyUI 图片路径格式: {filename} [subfolder]
                    # 例如: test-0001.png []
                    subfolder = img.get("subfolder", "")
                    filename = img["filename"]

                    if subfolder:
                        path = f"api/v2/view?filename={filename}&subfolder={subfolder}&type=output"
                    else:
                        path = f"api/v2/view?filename={filename}&type=output"

                    full_url = f"{self.base_url}/{path}"
                    image_paths.append(full_url)

        return image_paths

    def download_image(self, url: str) -> bytes:
        """
        下载图片

        Args:
            url: 图片 URL

        Returns:
            图片二进制数据
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.error(f"Failed to download image: {e}")
            raise

# 全局实例
comfyui_client = ComfyUIClient()
```

- [ ] **Step 2: 提交**

```bash
git add worker/utils/comfyui.py
git commit -m "feat: add ComfyUI API client with workflow submission and image download"
```

---

### Task 20: 创建 Worker R2 工具

**Files:**
- Create: `worker/utils/r2.py`

- [ ] **Step 1: 创建 R2 上传工具（Worker 版本）**

```python
# worker/utils/r2.py
import boto3
from botocore.exceptions import ClientError
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

class WorkerR2Client:
    def __init__(self):
        self.endpoint_url = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name='auto'
        )
        self.bucket_name = settings.r2_bucket_name
        self.public_url = settings.r2_public_url

    def upload_result(self, task_id: str, task_type: str, image_data: bytes) -> Optional[str]:
        """
        上传处理结果到 R2

        Args:
            task_id: 任务 ID
            task_type: 任务类型
            image_data: 图片二进制数据

        Returns:
            公共 URL，失败返回 None
        """
        prefix_map = {
            "face-swap": "face-swap",
            "upscale": "upscale",
            "remove-background": "remove-background"
        }
        prefix = prefix_map.get(task_type, "unknown")
        filename = f"{task_id}.png"
        key = f"{prefix}/{filename}"

        # 重试逻辑（指数退避）
        import time

        for attempt in range(3):
            try:
                # 上传
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=image_data,
                    ContentType='image/png'
                )

                # 验证
                self.client.head_object(
                    Bucket=self.bucket_name,
                    Key=key
                )

                url = f"{self.public_url}/{key}"
                logger.info(f"Successfully uploaded {key} (attempt {attempt + 1})")
                return url

            except ClientError as e:
                logger.error(f"Upload attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s
                else:
                    return None

# 全局实例
r2_client = WorkerR2Client()
```

- [ ] **Step 2: 提交**

```bash
git add worker/utils/r2.py
git commit -m "feat: add worker R2 client with retry logic"
```

---

### Task 21: 创建 GPU 监控工具

**Files:**
- Create: `worker/utils/gpu_monitor.py`

- [ ] **Step 1: 创建 GPU 温度监控**

```python
# worker/utils/gpu_monitor.py
import subprocess
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

class GPUMonitor:
    def get_temperature(self) -> Optional[int]:
        """
        获取 GPU 温度

        Returns:
            温度（摄氏度），获取失败返回 None
        """
        try:
            result = subprocess.run(
                ['nvidia-smi',
                 '--query-gpu=temperature.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                temp = int(result.stdout.strip())
                return temp

        except Exception as e:
            logger.error(f"Failed to get GPU temperature: {e}")

        return None

    def get_memory_info(self) -> Optional[dict]:
        """
        获取 GPU 显存信息

        Returns:
            {"used_mb": int, "total_mb": int, "free_mb": int}
        """
        try:
            result = subprocess.run(
                ['nvidia-smi',
                 '--query-gpu=memory.used,memory.total',
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                parts = result.stdout.strip().split(', ')
                if len(parts) == 2:
                    used = int(parts[0])
                    total = int(parts[1])
                    return {
                        "used_mb": used,
                        "total_mb": total,
                        "free_mb": total - used
                    }

        except Exception as e:
            logger.error(f"Failed to get GPU memory info: {e}")

        return None

    def get_utilization(self) -> Optional[int]:
        """
        获取 GPU 利用率

        Returns:
            利用率百分比
        """
        try:
            result = subprocess.run(
                ['nvidia-smi',
                 '--query-gpu=utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                util = int(result.stdout.strip())
                return util

        except Exception as e:
            logger.error(f"Failed to get GPU utilization: {e}")

        return None

    def is_too_hot(self) -> bool:
        """
        检查 GPU 温度过高

        Returns:
            是否超过阈值
        """
        temp = self.get_temperature()

        if temp is None:
            return False

        threshold = settings.gpu_temp_threshold
        if temp >= threshold:
            logger.warning(f"GPU temperature {temp}°C exceeds threshold {threshold}°C")
            return True

        return False

# 全局实例
gpu_monitor = GPUMonitor()
```

- [ ] **Step 2: 提交**

```bash
git add worker/utils/gpu_monitor.py
git commit -m "feat: add GPU monitoring utilities"
```

---

### Task 22: 创建处理器基类

**Files:**
- Create: `worker/processors/base.py`

- [ ] **Step 1: 创建任务处理器基类**

```python
# worker/processors/base.py
from abc import ABC, abstractmethod
import logging
from datetime import datetime
from utils.redis import redis_client
from utils.r2 import r2_client
from utils.comfyui import comfyui_client
from utils.gpu_monitor import gpu_monitor
from config import settings

logger = logging.getLogger(__name__)

class BaseProcessor(ABC):
    """任务处理器基类"""

    def __init__(self, task: dict):
        self.task = task
        self.task_id = task["task_id"]
        self.task_type = task["type"]
        self.input_path = task["input_path"]
        self.params = task.get("params", {})

    @abstractmethod
    def load_workflow(self) -> dict:
        """
        加载 Workflow JSON 模板

        Returns:
            Workflow 字典
        """
        pass

    @abstractmethod
    def prepare_workflow(self, workflow: dict) -> dict:
        """
        准备 Workflow（替换参数）

        Args:
            workflow: Workflow 模板

        Returns:
            准备好的 Workflow
        """
        pass

    def update_progress(self, current: int, total: int, message: str):
        """更新任务进度"""
        progress = int((current / total) * 100)

        progress_data = {
            "status": "processing",
            "progress": progress,
            "message": message,
            "current_step": current,
            "total_steps": total
        }

        redis_client.set_progress(self.task_id, progress_data)
        redis_client.publish_progress(self.task_id, progress_data)

        logger.info(f"Task {self.task_id}: {progress}% - {message}")

    def update_status(self, status: str, **kwargs):
        """更新任务状态"""
        status_data = {
            "status": status,
            "type": self.task_type,
            **kwargs
        }

        redis_client.set_task_status(self.task_id, status_data)

    def process(self) -> str:
        """
        执行任务处理

        Returns:
            结果图片 URL

        Raises:
            Exception: 处理失败
        """
        start_time = datetime.utcnow()

        try:
            logger.info(f"Processing task {self.task_id} (type: {self.task_type})")

            # 1. 检查 GPU 温度
            if gpu_monitor.is_too_hot():
                raise Exception("GPU temperature too high, cannot process task")

            # 2. 更新状态为 processing
            self.update_status(
                "processing",
                started_at=start_time.isoformat() + "Z"
            )

            # 3. 加载 Workflow
            workflow = self.load_workflow()
            self.update_progress(1, 5, "Loading workflow")

            # 4. 准备 Workflow
            workflow = self.prepare_workflow(workflow)
            self.update_progress(2, 5, "Preparing workflow")

            # 5. 提交到 ComfyUI
            prompt_id = comfyui_client.submit_workflow(workflow)
            self.update_progress(3, 5, "Workflow submitted")

            # 6. 等待完成
            timeout = self.get_timeout()
            result = comfyui_client.wait_for_completion(prompt_id, timeout=timeout)
            self.update_progress(4, 5, "Processing")

            # 7. 获取输出图片
            image_urls = comfyui_client.get_output_images(prompt_id)

            if not image_urls:
                raise Exception("No output images generated")

            # 8. 下载图片
            image_data = comfyui_client.download_image(image_urls[0])
            self.update_progress(5, 5, "Downloading result")

            # 9. 上传到 R2
            result_url = r2_client.upload_result(
                self.task_id,
                self.task_type,
                image_data
            )

            if not result_url:
                raise Exception("Failed to upload result to R2")

            # 10. 计算处理时间
            completed_at = datetime.utcnow()
            processing_time = (completed_at - start_time).total_seconds()

            # 11. 更新任务状态为 completed
            self.update_status(
                "completed",
                progress="100",
                result_url=result_url,
                completed_at=completed_at.isoformat() + "Z",
                processing_time=str(processing_time)
            )

            # 12. 发布完成消息
            completion_data = {
                "status": "completed",
                "progress": 100,
                "result_url": result_url,
                "processing_time": processing_time
            }
            redis_client.publish_progress(self.task_id, completion_data)

            logger.info(f"Task {self.task_id} completed in {processing_time:.2f}s")

            # 13. 清理本地文件
            self.cleanup()

            return result_url

        except Exception as e:
            logger.error(f"Task {self.task_id} failed: {e}")

            # 更新状态为 failed
            self.update_status(
                "failed",
                error=str(e)
            )

            # 发布错误消息
            error_data = {
                "status": "failed",
                "error": str(e),
                "error_code": "TASK_FAILED"
            }
            redis_client.publish_progress(self.task_id, error_data)

            raise

    def cleanup(self):
        """清理临时文件"""
        import os
        import shutil

        # 删除输入图片
        input_dir = f"/data/inputs/{self.task_id}"
        if os.path.exists(input_dir):
            shutil.rmtree(input_dir)
            logger.info(f"Cleaned up input directory: {input_dir}")

    def get_timeout(self) -> int:
        """获取任务超时时间"""
        timeouts = {
            "face-swap": settings.task_timeout_face_swap,
            "upscale": settings.task_timeout_upscale,
            "remove-background": settings.task_timeout_remove_bg
        }
        return timeouts.get(self.task_type, 120)
```

- [ ] **Step 2: 提交**

```bash
git add worker/processors/base.py
git commit -m "feat: add base processor class with task lifecycle management"
```

---

### Task 23: 创建换脸处理器

**Files:**
- Create: `worker/processors/face_swap.py`

- [ ] **Step 1: 创建换脸任务处理器**

```python
# worker/processors/face_swap.py
import json
from .base import BaseProcessor

class FaceSwapProcessor(BaseProcessor):
    """换脸任务处理器"""

    def load_workflow(self) -> dict:
        """加载换脸 Workflow 模板"""
        import os

        workflow_path = "/app/workflows/face_swap.json"

        if not os.path.exists(workflow_path):
            raise FileNotFoundError(f"Workflow template not found: {workflow_path}")

        with open(workflow_path, 'r') as f:
            return json.load(f)

    def prepare_workflow(self, workflow: dict) -> dict:
        """准备换脸 Workflow（替换图片路径）"""
        import os

        # 替换图片路径占位符
        for node_id, node_data in workflow.items():
            if "inputs" in node_data:
                inputs = node_data["inputs"]

                # 查找图片输入节点
                if "image" in inputs:
                    if isinstance(inputs["image"], str) and "source" in inputs["image"].lower():
                        inputs["image"] = os.path.join(self.input_path, "source.png")

                if "target_image" in inputs:
                    if isinstance(inputs["target_image"], str) and "target" in inputs["target_image"].lower():
                        inputs["target_image"] = os.path.join(self.input_path, "target.png")

        return workflow
```

- [ ] **Step 2: 提交**

```bash
git add worker/processors/face_swap.py
git commit -m "feat: add face swap processor"
```

---

### Task 24: 创建图片放大处理器

**Files:**
- Create: `worker/processors/upscale.py`

- [ ] **Step 1: 创建放大任务处理器**

```python
# worker/processors/upscale.py
import json
from .base import BaseProcessor

class UpscaleProcessor(BaseProcessor):
    """图片放大任务处理器"""

    def load_workflow(self) -> dict:
        """加载放大 Workflow 模板"""
        import os

        workflow_path = "/app/workflows/upscale.json"

        if not os.path.exists(workflow_path):
            raise FileNotFoundError(f"Workflow template not found: {workflow_path}")

        with open(workflow_path, 'r') as f:
            return json.load(f)

    def prepare_workflow(self, workflow: dict) -> dict:
        """准备放大 Workflow（替换图片路径和放大倍数）"""
        import os

        scale_factor = self.params.get("scale_factor", 2)

        # 替换占位符
        for node_id, node_data in workflow.items():
            if "inputs" in node_data:
                inputs = node_data["inputs"]

                # 替换图片路径
                if "image" in inputs:
                    if isinstance(inputs["image"], str) and "input" in inputs["image"].lower():
                        inputs["image"] = os.path.join(self.input_path, "source.png")

                # 替换放大倍数
                if "scale" in inputs or "upscale_factor" in inputs:
                    scale_key = "scale" if "scale" in inputs else "upscale_factor"
                    if isinstance(inputs[scale_key], (int, str)):
                        inputs[scale_key] = scale_factor

        return workflow
```

- [ ] **Step 2: 提交**

```bash
git add worker/processors/upscale.py
git commit -m "feat: add upscale processor"
```

---

### Task 25: 创建去背景处理器

**Files:**
- Create: `worker/processors/remove_bg.py`

- [ ] **Step 1: 创建去背景任务处理器**

```python
# worker/processors/remove_bg.py
import json
from .base import BaseProcessor

class RemoveBackgroundProcessor(BaseProcessor):
    """去背景任务处理器"""

    def load_workflow(self) -> dict:
        """加载去背景 Workflow 模板"""
        import os

        workflow_path = "/app/workflows/remove_background.json"

        if not os.path.exists(workflow_path):
            raise FileNotFoundError(f"Workflow template not found: {workflow_path}")

        with open(workflow_path, 'r') as f:
            return json.load(f)

    def prepare_workflow(self, workflow: dict) -> dict:
        """准备去背景 Workflow（替换图片路径）"""
        import os

        # 替换图片路径占位符
        for node_id, node_data in workflow.items():
            if "inputs" in node_data:
                inputs = node_data["inputs"]

                # 查找图片输入节点
                if "image" in inputs:
                    if isinstance(inputs["image"], str) and "input" in inputs["image"].lower():
                        inputs["image"] = os.path.join(self.input_path, "source.png")

        return workflow
```

- [ ] **Step 2: 提交**

```bash
git add worker/processors/remove_bg.py
git commit -m "feat: add remove background processor"
```

---

### Task 26: 创建 Worker 主程序

**Files:**
- Create: `worker/main.py`

- [ ] **Step 1: 创建 Worker 主程序**

```python
# worker/main.py
import asyncio
import logging
from datetime import datetime
from config import settings
from utils.redis import redis_client
from processors.face_swap import FaceSwapProcessor
from processors.upscale import UpscaleProcessor
from processors.remove_bg import RemoveBackgroundProcessor
from utils.cleanup import cleanup_task, emergency_cleanup

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 处理器映射
PROCESSORS = {
    "face-swap": FaceSwapProcessor,
    "upscale": UpscaleProcessor,
    "remove-background": RemoveBackgroundProcessor
}

async def process_single_task(task: dict):
    """处理单个任务"""
    task_id = task["task_id"]
    task_type = task["type"]

    logger.info(f"Processing task {task_id} (type: {task_type})")

    try:
        # 获取处理器
        processor_class = PROCESSORS.get(task_type)

        if not processor_class:
            raise ValueError(f"Unknown task type: {task_type}")

        # 创建处理器实例
        processor = processor_class(task)

        # 执行处理
        result_url = processor.process()

        logger.info(f"Task {task_id} completed: {result_url}")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")

async def worker_loop():
    """Worker 主循环"""
    logger.info("Worker started")
    logger.info(f"Poll interval: {settings.worker_poll_interval}s")
    logger.info(f"Concurrency: {settings.worker_concurrency}")

    while True:
        try:
            # 从队列取任务
            task = redis_client.pop_task(timeout=settings.worker_poll_interval)

            if task:
                await process_single_task(task)
            else:
                # 没有任务，继续轮询
                pass

        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(5)

async def cleanup_loop():
    """定期清理临时文件"""
    while True:
        try:
            await asyncio.sleep(settings.cleanup_interval_minutes * 60)

            logger.info("Running cleanup task...")

            cleanup_task(
                input_hours=settings.cleanup_input_after_hours,
                output_hours=settings.cleanup_output_after_hours
            )

        except Exception as e:
            logger.error(f"Cleanup task error: {e}")

async def main():
    """主函数"""
    logger.info("Starting ComfyUI Worker...")

    # 启动清理任务
    cleanup_task_handle = asyncio.create_task(cleanup_loop())

    # 启动 worker 循环
    try:
        await worker_loop()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    finally:
        cleanup_task_handle.cancel()

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 提交**

```bash
git add worker/main.py
git commit -m "feat: add worker main loop with cleanup task"
```

---

### Task 27: 创建清理工具

**Files:**
- Create: `worker/utils/cleanup.py`

- [ ] **Step 1: 创建临时文件清理工具**

```python
# worker/utils/cleanup.py
import os
import shutil
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def cleanup_directory(directory: str, max_age_hours: int):
    """
    清理目录中超过指定时间的文件

    Args:
        directory: 目录路径
        max_age_hours: 最大保留时间（小时）
    """
    if not os.path.exists(directory):
        return

    now = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0
    deleted_size = 0

    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)

        # 检查修改时间
        item_mtime = os.path.getmtime(item_path)
        item_age = now - item_mtime

        if item_age > max_age_seconds:
            try:
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    os.remove(item_path)
                    deleted_size += size
                    deleted_count += 1
                elif os.path.isdir(item_path):
                    size = sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, _, filenames in os.walk(item_path)
                        for filename in filenames
                    )
                    shutil.rmtree(item_path)
                    deleted_size += size
                    deleted_count += 1

            except Exception as e:
                logger.error(f"Failed to delete {item_path}: {e}")

    if deleted_count > 0:
        logger.info(f"Cleaned {deleted_count} items ({deleted_size / (1024**2):.2f} MB) from {directory}")

def cleanup_task(input_hours: int = 2, output_hours: int = 24):
    """
    执行清理任务

    Args:
        input_hours: 输入图片保留时间
        output_hours: ComfyUI 输出保留时间
    """
    # 清理输入图片
    cleanup_directory("/data/inputs", input_hours)

    # 清理 ComfyUI 输出
    cleanup_directory("/app/ComfyUI/output", output_hours)

    # 清理临时文件
    cleanup_directory("/data/temp", 24)

def get_disk_free_gb() -> float:
    """
    获取磁盘可用空间（GB）

    Returns:
        可用空间（GB）
    """
    stat = os.statvfs('/data')
    return (stat.f_bavail * stat.f_frsize) / (1024**3)

def emergency_cleanup(keep_hours: int = 1):
    """
    紧急清理（磁盘空间不足时）

    Args:
        keep_hours: 只保留最近 N 小时的文件
    """
    logger.warning(f"Emergency cleanup triggered, keeping only last {keep_hours} hours")

    cleanup_directory("/data/inputs", keep_hours)
    cleanup_directory("/app/ComfyUI/output", keep_hours)
    cleanup_directory("/data/temp", keep_hours)

    free_gb = get_disk_free_gb()
    logger.info(f"After emergency cleanup: {free_gb:.2f} GB free")
```

- [ ] **Step 2: 提交**

```bash
git add worker/utils/cleanup.py
git commit -m "feat: add cleanup utilities for temporary files"
```

---

## Phase 4: ComfyUI 后端

### Task 28: 创建 ComfyUI Workflow 模板

**Files:**
- Create: `worker/workflows/face_swap.json`
- Create: `worker/workflows/upscale.json`
- Create: `worker/workflows/remove_background.json`

- [ ] **Step 1: 创建换脸 Workflow 模板**

```json
{
  "3": {
    "inputs": {
      "image": "{{INPUT_IMAGE_PATH}}",
      "upload": "image"
    },
    "class_type": "LoadImage"
  },
  "4": {
    "inputs": {
      "image": "{{TARGET_IMAGE_PATH}}",
      "upload": "image"
    },
    "class_type": "LoadImage"
  },
  "5": {
    "inputs": {
      "image": ["3", 0],
      "upload": "image"
    },
    "class_type": "ReActorFaceSwap"
  },
  "6": {
    "inputs": {
      "images": ["5", 0],
      "filename_prefix": "{{OUTPUT_PREFIX}}"
    },
    "class_type": "SaveImage"
  }
}
```

**注意**: 上述模板是简化示例。实际 Workflow JSON 需要在 ComfyUI 中创建完整工作流后导出。

- [ ] **Step 2: 创建放大 Workflow 模板**

```json
{
  "3": {
    "inputs": {
      "image": "{{INPUT_IMAGE_PATH}}",
      "upload": "image"
    },
    "class_type": "LoadImage"
  },
  "4": {
    "inputs": {
      "upscale_model": "RealESRGAN_x4plus.pth",
      "image": ["3", 0]
    },
    "class_type": "ImageUpscaleWithModel"
  },
  "5": {
    "inputs": {
      "images": ["4", 0],
      "filename_prefix": "{{OUTPUT_PREFIX}}"
    },
    "class_type": "SaveImage"
  }
}
```

- [ ] **Step 3: 创建去背景 Workflow 模板**

```json
{
  "3": {
    "inputs": {
      "image": "{{INPUT_IMAGE_PATH}}",
      "upload": "image"
    },
    "class_type": "LoadImage"
  },
  "4": {
    "inputs": {
      "rmbg_model": "RMBG-1.4.pth",
      "image": ["3", 0]
    },
    "class_type": "RemoveBackground"
  },
  "5": {
    "inputs": {
      "images": ["4", 0],
      "filename_prefix": "{{OUTPUT_PREFIX}}"
    },
    "class_type": "SaveImage"
  }
}
```

- [ ] **Step 4: 提交**

```bash
git add worker/workflows/
git commit -m "feat: add ComfyUI workflow templates for all task types"
```

---

### Task 29: 创建模型下载脚本

**Files:**
- Create: `comfyui/download_models.sh`

- [ ] **Step 1: 创建模型下载脚本**

```bash
#!/bin/bash

# ComfyUI 模型下载脚本

set -e

MODELS_DIR="/app/ComfyUI/models"

echo "Downloading AI models..."

# 1. 换脸模型 (ReActor / inswapper)
mkdir -p "$MODELS_DIR/insightface"
echo "Downloading inswapper_128.onnx..."
curl -L -o "$MODELS_DIR/insightface/inswapper_128.onnx" \
  "https://huggingface.co/Gourieff/ReActor/resolve/main/models/inswapper_128.onnx"

# 2. 图片放大模型 (Real-ESRGAN)
mkdir -p "$MODELS_DIR/upscale_models"
echo "Downloading RealESRGAN_x4plus.pth..."
curl -L -o "$MODELS_DIR/upscale_models/RealESRGAN_x4plus.pth" \
  "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"

# 3. 去背景模型 (RMBG-1.4)
mkdir -p "$MODELS_DIR/rmbg"
echo "Downloading RMBG-1.4.pth..."
curl -L -o "$MODELS_DIR/rmbg/RMBG-1.4.pth" \
  "https://huggingface.co/briaai/RMBG-1.4/resolve/main/RMBG-1.4.pth"

echo "All models downloaded successfully!"
echo "Model sizes:"
du -sh "$MODELS_DIR"/*/
```

- [ ] **Step 2: 添加执行权限**

```bash
chmod +x comfyui/download_models.sh
```

- [ ] **Step 3: 提交**

```bash
git add comfyui/download_models.sh
git commit -m "feat: add model download script"
```

---

## Phase 5: Nginx 反向代理

### Task 30: 创建 Nginx 配置

**Files:**
- Create: `nginx/default.conf`

- [ ] **Step 1: 创建 Nginx 配置文件**

```nginx
# 限流配置
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_conn_zone $binary_remote_addr zone=ws_conn:10m;

server {
    listen 80;
    server_name _;

    # 请求体大小限制
    client_max_body_size 15M;

    # API 路由
    location /api/ {
        # 限流
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket 路由
    location /ws/ {
        # 连接数限制
        limit_conn ws_conn 10;

        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # WebSocket 超时（保持长连接）
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    # 健康检查
    location /health {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
    }

    # 根路径
    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
    }
}
```

- [ ] **Step 2: 测试 Nginx 配置**

```bash
docker run --rm -v $(pwd)/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro nginx:alpine nginx -t
```

Expected output: `syntax is ok`

- [ ] **Step 3: 提交**

```bash
git add nginx/default.conf
git commit -m "feat: add Nginx configuration with rate limiting and WebSocket support"
```

---

## Phase 6: 集成测试

### Task 31: 创建集成测试

**Files:**
- Create: `tests/integration/test_full_flow.py`

- [ ] **Step 1: 创建端到端测试**

```python
# tests/integration/test_full_flow.py
import pytest
import base64
import time
import requests
from typing import Generator

API_BASE = "http://localhost:80"
API_KEY = "test-api-key"

# 创建一个小的测试图片
TEST_IMAGE = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'x' * 100).decode()


@pytest.fixture(scope="module")
def api_session():
    """创建 API 会话"""
    session = requests.Session()
    session.headers.update({"X-API-Key": API_KEY})
    yield session


def test_health_check(api_session):
    """测试健康检查"""
    response = api_session.get(f"{API_BASE}/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "services" in data
    assert "queue" in data


def test_create_remove_background_task(api_session):
    """测试创建去背景任务"""
    response = api_session.post(
        f"{API_BASE}/api/tasks",
        json={
            "type": "remove-background",
            "images": {
                "source": TEST_IMAGE
            }
        }
    )

    assert response.status_code == 200

    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert "ws_token" in data
    assert "websocket_url" in data

    return data["task_id"]


def test_task_status(api_session):
    """测试查询任务状态"""
    # 先创建任务
    create_response = api_session.post(
        f"{API_BASE}/api/tasks",
        json={
            "type": "remove-background",
            "images": {
                "source": TEST_IMAGE
            }
        }
    )

    task_id = create_response.json()["task_id"]

    # 查询状态
    response = api_session.get(f"{API_BASE}/api/tasks/{task_id}")

    assert response.status_code == 200

    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] in ["queued", "processing", "completed", "failed"]


def test_invalid_api_key():
    """测试无效 API Key"""
    session = requests.Session()
    session.headers.update({"X-API-Key": "invalid-key"})

    response = session.post(
        f"{API_BASE}/api/tasks",
        json={
            "type": "remove-background",
            "images": {
                "source": TEST_IMAGE
            }
        }
    )

    assert response.status_code == 401


def test_invalid_image_format(api_session):
    """测试无效图片格式"""
    response = api_session.post(
        f"{API_BASE}/api/tasks",
        json={
            "type": "remove-background",
            "images": {
                "source": "not-a-valid-image"
            }
        }
    )

    assert response.status_code == 400


def test_face_swap_missing_target(api_session):
    """测试换脸缺少目标图片"""
    response = api_session.post(
        f"{API_BASE}/api/tasks",
        json={
            "type": "face-swap",
            "images": {
                "source": TEST_IMAGE
            }
        }
    )

    assert response.status_code == 400


def test_cancel_task(api_session):
    """测试取消任务"""
    # 创建任务
    create_response = api_session.post(
        f"{API_BASE}/api/tasks",
        json={
            "type": "remove-background",
            "images": {
                "source": TEST_IMAGE
            }
        }
    )

    task_id = create_response.json()["task_id"]

    # 取消任务
    response = api_session.delete(f"{API_BASE}/api/tasks/{task_id}")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "cancelled"
```

- [ ] **Step 2: 运行集成测试**

```bash
# 确保服务运行
docker-compose up -d

# 运行测试
pytest tests/integration/test_full_flow.py -v
```

Expected output: 所有测试通过

- [ ] **Step 3: 提交**

```bash
git add tests/integration/test_full_flow.py
git commit -m "feat: add integration tests for full task flow"
```

---

### Task 32: 创建部署文档

**Files:**
- Create: `docs/DEPLOYMENT.md`

- [ ] **Step 1: 创建部署文档**

```markdown
# ComfyUI AI 图片处理服务器 - 部署指南

## 前置检查

### 1. 确认 GPU 和 CUDA 版本

```bash
nvidia-smi
nvcc --version
```

### 2. 安装 NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 3. 验证 Docker 可访问 GPU

```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

### 4. 确认磁盘空间

```bash
df -h /home/abel/comfyui-server
# 需要至少 30GB 可用空间
```

## 部署步骤

### 1. 克隆项目

```bash
cd /home/abel/comfyui-server
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 必填项
API_KEYS=your-generated-api-key
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=your-bucket-name
R2_PUBLIC_URL=https://your-bucket.r2.dev

# 生成 API Key
openssl rand -hex 32
```

### 3. 下载模型

```bash
# 启动 ComfyUI 容器（仅用于下载模型）
docker-compose up -d comfyui

# 下载模型
docker-compose exec comfyui /app/download_models.sh

# 验证模型
docker-compose exec comfyui ls -lh /app/ComfyUI/models/
```

### 4. 配置 ComfyUI Workflow

1. 在浏览器访问 `http://localhost:8188`（临时映射端口进行配置）
2. 安装必要的自定义节点：
   - ComfyUI Manager
   - ReActor Face Swap
   - RMBG-1.4
3. 创建三个工作流：换脸、放大、去背景
4. 导出为 API Format JSON
5. 保存到 `worker/workflows/` 目录

### 5. 构建并启动

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 检查状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 6. 验证部署

```bash
# 健康检查
curl http://localhost/health

# 测试去背景任务
curl -X POST http://localhost/api/tasks \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "remove-background",
    "images": {"source": "BASE64_IMAGE_DATA"}
  }'
```

## 运维命令

### 查看日志

```bash
# 所有服务
docker-compose logs -f

# 特定服务
docker-compose logs -f worker
docker-compose logs -f api
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart worker
```

### 更新部署

```bash
# 拉取最新代码
git pull

# 重建镜像
docker-compose build

# 重启服务
docker-compose up -d
```

### 清理

```bash
# 停止并删除容器
docker-compose down

# 删除卷（谨慎！）
docker-compose down -v
```

## 监控

### GPU 监控

```bash
# 实时监控
watch -n 5 nvidia-smi
```

### 队列状态

```bash
docker-compose exec api python -c "from utils.redis import redis_client; print(redis_client.get_queue_length())"
```

### 磁盘使用

```bash
df -h
du -sh /var/lib/docker/volumes/comfyui-server_*/
```

## 故障排查

详见设计文档第 15.3 节。
```

- [ ] **Step 2: 提交**

```bash
git add docs/DEPLOYMENT.md
git commit -m "docs: add deployment guide"
```

---

### Task 33: 创建 API 使用文档

**Files:**
- Create: `docs/API.md`

- [ ] **Step 1: 创建 API 使用文档**

```markdown
# ComfyUI AI 图片处理服务器 - API 文档

## 基础信息

- **Base URL**: `http://YOUR_SERVER_IP:80`
- **认证**: Header `X-API-Key: YOUR_API_KEY`
- **请求格式**: JSON
- **响应格式**: JSON

## 接口列表

### 1. 创建任务

**Endpoint**: `POST /api/tasks`

**请求示例**：

```bash
curl -X POST http://YOUR_SERVER_IP/api/tasks \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "remove-background",
    "images": {
      "source": "data:image/png;base64,iVBORw0KG..."
    },
    "webhook_url": "http://your-callback.com/webhook"
  }'
```

**任务类型**：

#### 换脸 (face-swap)

```json
{
  "type": "face-swap",
  "images": {
    "source": "base64_encoded_source_image",
    "target": "base64_encoded_target_image"
  }
}
```

#### 图片放大 (upscale)

```json
{
  "type": "upscale",
  "images": {
    "source": "base64_encoded_image"
  },
  "params": {
    "scale_factor": 2
  }
}
```

#### 去背景 (remove-background)

```json
{
  "type": "remove-background",
  "images": {
    "source": "base64_encoded_image"
  }
}
```

**响应示例**：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "websocket_url": "ws://192.168.1.100/ws/task/550e8400-e29b-41d4-a716-446655440000",
  "ws_token": "eyJhbGciOiJIUzI1NiJ9...",
  "queue_position": 3
}
```

### 2. 查询任务状态

**Endpoint**: `GET /api/tasks/{task_id}`

**请求示例**：

```bash
curl http://YOUR_SERVER_IP/api/tasks/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: YOUR_API_KEY"
```

**响应示例**：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "remove-background",
  "status": "completed",
  "progress": 100,
  "result_url": "https://your-bucket.r2.dev/remove-background/550e8400.png",
  "created_at": "2026-03-26T12:00:00Z",
  "completed_at": "2026-03-26T12:00:05Z",
  "processing_time": 5.2,
  "error": null
}
```

### 3. 取消任务

**Endpoint**: `DELETE /api/tasks/{task_id}`

**请求示例**：

```bash
curl -X DELETE http://YOUR_SERVER_IP/api/tasks/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: YOUR_API_KEY"
```

### 4. 健康检查

**Endpoint**: `GET /health`

**请求示例**：

```bash
curl http://YOUR_SERVER_IP/health
```

**响应示例**：

```json
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
    "vram_free_mb": 4992
  },
  "queue": {
    "pending": 5,
    "processing": 1,
    "max_length": 50
  }
}
```

## WebSocket 连接

### 连接 URL

```
ws://YOUR_SERVER_IP/ws/task/{task_id}?token={ws_token}
```

### 消息格式

#### 进度消息

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

#### 完成消息

```json
{
  "type": "completed",
  "timestamp": "2026-03-26T12:00:15Z",
  "data": {
    "result_url": "https://your-bucket.r2.dev/remove-background/xxx.png",
    "metadata": {
      "processing_time": 5.2,
      "model_used": "RMBG-1.4.pth"
    }
  }
}
```

#### 错误消息

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

## 错误码

| HTTP 状态 | 错误类型 | 说明 |
|----------|---------|------|
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | API Key 无效 |
| 404 | Not Found | 任务不存在 |
| 413 | Payload Too Large | 图片过大 |
| 429 | Too Many Requests | 队列已满 |
| 500 | Internal Server Error | 服务器内部错误 |
| 503 | Service Unavailable | 服务不可用 |

## 限制

- 图片大小：最大 10MB（Base64 解码后）
- 图片格式：PNG, JPG, JPEG, WEBP
- 图片尺寸：最大 4096x4096
- 队列长度：最大 50 个任务
- WebSocket Token：有效期 5 分钟

## 客户端示例

### Python

```python
import requests
import base64
import json

# 读取图片
with open("input.png", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

# 创建任务
response = requests.post(
    "http://192.168.1.100/api/tasks",
    headers={"X-API-Key": "your-api-key"},
    json={
        "type": "remove-background",
        "images": {"source": image_data}
    }
)

task_info = response.json()
task_id = task_info["task_id"]
print(f"Task created: {task_id}")

# 查询状态
status_response = requests.get(
    f"http://192.168.1.100/api/tasks/{task_id}",
    headers={"X-API-Key": "your-api-key"}
)

print(status_response.json())
```

### JavaScript

```javascript
const axios = require('axios');

const API_BASE = 'http://192.168.1.100';
const API_KEY = 'your-api-key';

async function removeBackground(imageBase64) {
  // 创建任务
  const { data: task } = await axios.post(`${API_BASE}/api/tasks`, {
    type: 'remove-background',
    images: { source: imageBase64 }
  }, {
    headers: { 'X-API-Key': API_KEY }
  });

  console.log('Task created:', task.task_id);

  // 连接 WebSocket
  const ws = new WebSocket(`${task.websocket_url}?token=${task.ws_token}`);

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'progress') {
      console.log(`Progress: ${message.data.progress}%`);
    } else if (message.type === 'completed') {
      console.log('Result:', message.data.result_url);
      ws.close();
    } else if (message.type === 'error') {
      console.error('Error:', message.data.error);
      ws.close();
    }
  };
}
```

### curl

```bash
# 去背景
IMAGE_BASE64=$(base64 -w 0 input.png)

curl -X POST http://192.168.1.100/api/tasks \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"remove-background\",
    \"images\": {\"source\": \"$IMAGE_BASE64\"}
  }"
```
```

- [ ] **Step 2: 提交**

```bash
git add docs/API.md
git commit -m "docs: add API usage documentation"
```

---

### Task 34: 创建 README

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建项目 README**

```markdown
# ComfyUI AI 图片处理服务器

基于 ComfyUI 的局域网 AI 图片处理服务，提供换脸、图片放大、去背景功能的 RESTful API。

## 功能特性

- 🎭 **换脸**: 基于ReActor的快速人脸替换
- 🔍 **图片放大**: Real-ESRGAN 超分辨率放大（2x/4x/8x）
- ✂️ **去背景**: RMBG-1.4 高质量背景移除
- 📡 **WebSocket**: 实时进度推送
- 📊 **任务队列**: 支持并发处理
- ☁️ **R2 存储**: 自动上传到 Cloudflare R2

## 系统要求

- NVIDIA GPU (8GB+ VRAM 推荐)
- CUDA 12.x
- Docker & Docker Compose
- NVIDIA Container Toolkit
- 30GB+ 可用磁盘空间

## 快速开始

### 1. 安装 NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API Key 和 R2 配置
openssl rand -hex 32  # 生成 API Key
```

### 3. 启动服务

```bash
docker-compose build
docker-compose up -d
```

### 4. 下载模型

```bash
docker-compose exec comfyui /app/download_models.sh
```

### 5. 验证部署

```bash
curl http://localhost/health
```

## 使用示例

```python
import requests
import base64

# 读取图片
with open("photo.png", "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode()

# 创建去背景任务
response = requests.post(
    "http://YOUR_SERVER_IP/api/tasks",
    headers={"X-API-Key": "YOUR_API_KEY"},
    json={
        "type": "remove-background",
        "images": {"source": image_base64}
    }
)

task = response.json()
print(f"Task ID: {task['task_id']}")
print(f"WebSocket: {task['websocket_url']}?token={task['ws_token']}")
```

## 文档

- [部署指南](docs/DEPLOYMENT.md)
- [API 文档](docs/API.md)
- [设计文档](docs/design/comfyui-ai-image-server-design.md)

## 架构

```
Nginx (80) → FastAPI (8000) → Redis Queue → Worker → ComfyUI (8188)
                                                      ↓
                                                   Cloudflare R2
```

## 许可证

MIT
```

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: add project README"
```

---

### Task 35: 创建 .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: 创建 .gitignore**

```
# 环境变量
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
dist/
build/

# Docker
*.log

# IDE
.vscode/
.idea/
*.swp
*.swo

# 操作系统
.DS_Store
Thumbs.db

# 模型文件（大文件，不提交到 Git）
comfyui/models/**/*.pth
comfyui/models/**/*.onnx
comfyui/models/**/*.safetensors

# 临时文件
data/inputs/
data/temp/
*.tmp
```

- [ ] **Step 2: 提交**

```bash
git add .gitignore
git commit -m "chore: add gitignore"
```

---

### Task 36: 最终验证和测试

**Files:**
- No new files

- [ ] **Step 1: 构建所有服务**

```bash
cd /home/abel/comfyui-server
docker-compose build
```

Expected: 所有镜像构建成功

- [ ] **Step 2: 启动服务**

```bash
docker-compose up -d
```

Expected: 所有服务正常启动

- [ ] **Step 3: 验证 GPU 访问**

```bash
docker-compose exec comfyui nvidia-smi
```

Expected: 显示 GPU 信息

- [ ] **Step 4: 测试健康检查**

```bash
curl http://localhost/health
```

Expected: 返回健康状态 JSON

- [ ] **Step 5: 运行集成测试**

```bash
pytest tests/integration/test_full_flow.py -v
```

Expected: 所有测试通过

- [ ] **Step 6: 提交最终版本**

```bash
git add .
git commit -m "chore: complete implementation - all tests passing"
```

---

## 总结

本实现计划包含 **36 个任务**，分为 6 个阶段：

1. **项目基础设施** (Tasks 1-8): Docker 配置、目录结构、基础工具类
2. **API 服务** (Tasks 9-16): FastAPI 应用、路由、中间件、WebSocket
3. **Worker 任务处理器** (Tasks 17-27): 任务处理逻辑、ComfyUI 客户端
4. **ComfyUI 后端** (Tasks 28-29): Workflow 模板、模型下载
5. **Nginx 反向代理** (Task 30): 反向代理配置、限流
6. **集成测试和文档** (Tasks 31-36): 测试、文档、验证

每个任务都包含详细的代码、测试和提交步骤，确保实现质量和可追溯性。

**下一步**: 选择执行方式（Subagent-Driven 或 Inline Execution）
