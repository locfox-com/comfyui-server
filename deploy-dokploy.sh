#!/bin/bash
# ComfyUI AI Server - Dokploy 快速部署脚本
# 此脚本帮助您准备 Dokploy 部署所需的所有文件

set -e

echo "=========================================="
echo "ComfyUI AI Server - Dokploy 部署准备"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查必要的命令
check_requirements() {
    echo -e "${YELLOW}检查系统要求...${NC}"

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker 未安装${NC}"
        exit 1
    fi

    if ! command -v git &> /dev/null; then
        echo -e "${RED}错误: Git 未安装${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ 系统要求检查通过${NC}"
    echo ""
}

# 检查 GPU 支持
check_gpu() {
    echo -e "${YELLOW}检查 GPU 支持...${NC}"

    if command -v nvidia-smi &> /dev/null; then
        echo -e "${GREEN}✓ NVIDIA GPU 已检测到${NC}"
        nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    else
        echo -e "${YELLOW}⚠ 未检测到 NVIDIA GPU，ComfyUI 将在 CPU 模式下运行${NC}"
        echo -e "${YELLOW}  如需 GPU 加速，请安装 NVIDIA 驱动和 Container Toolkit${NC}"
    fi
    echo ""
}

# 准备环境变量
prepare_env() {
    echo -e "${YELLOW}准备环境变量文件...${NC}"

    if [ ! -f ".env" ]; then
        if [ -f ".env.dokploy" ]; then
            cp .env.dokploy .env
            echo -e "${GREEN}✓ 从 .env.dokploy 创建 .env 文件${NC}"
            echo -e "${YELLOW}⚠ 请编辑 .env 文件并填入实际配置值${NC}"
        else
            echo -e "${RED}错误: .env.dokploy 文件不存在${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✓ .env 文件已存在${NC}"
    fi
    echo ""
}

# 验证配置文件
validate_config() {
    echo -e "${YELLOW}验证配置文件...${NC}"

    required_files=(
        "docker-compose.yml"
        "dokploy.json"
        ".env"
        "api/Dockerfile"
        "worker/Dockerfile"
        "comfyui/Dockerfile"
        "nginx/default.conf"
    )

    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            echo -e "${GREEN}✓ $file${NC}"
        else
            echo -e "${RED}✗ $file 缺失${NC}"
            exit 1
        fi
    done
    echo ""
}

# 生成 API 密钥
generate_api_key() {
    echo -e "${YELLOW}生成安全 API 密钥...${NC}"

    if command -v openssl &> /dev/null; then
        api_key=$(openssl rand -hex 32)
        echo ""
        echo -e "${GREEN}生成的 API 密钥:${NC}"
        echo "$api_key"
        echo ""
        read -p "是否要将此密钥添加到 .env 文件? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sed -i "s/API_KEYS=.*/API_KEYS=$api_key/" .env
            echo -e "${GREEN}✓ API 密钥已添加到 .env${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ openssl 未安装，跳过密钥生成${NC}"
    fi
    echo ""
}

# 验证环境变量
validate_env_vars() {
    echo -e "${YELLOW}验证必需的环境变量...${NC}"

    source .env

    required_vars=(
        "API_KEYS"
        "R2_ACCOUNT_ID"
        "R2_ACCESS_KEY_ID"
        "R2_SECRET_ACCESS_KEY"
        "R2_BUCKET_NAME"
        "R2_PUBLIC_URL"
    )

    missing_vars=()

    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ] || [[ "${!var}" == *"your-"* ]]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo -e "${RED}以下环境变量未配置:${NC}"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo -e "${YELLOW}请编辑 .env 文件并配置这些变量${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ 所有必需的环境变量已配置${NC}"
    fi
    echo ""
}

# 构建镜像（可选）
build_images() {
    echo ""
    read -p "是否现在构建 Docker 镜像? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}构建 Docker 镜像...${NC}"
        echo ""
        docker compose build
        echo -e "${GREEN}✓ 镜像构建完成${NC}"
    fi
}

# 显示部署摘要
show_summary() {
    echo ""
    echo "=========================================="
    echo -e "${GREEN}部署准备完成！${NC}"
    echo "=========================================="
    echo ""
    echo "接下来的步骤："
    echo ""
    echo "1. 编辑 .env 文件，确认所有配置正确"
    echo "   vim .env"
    echo ""
    echo "2. (可选) 构建并测试本地部署"
    echo "   docker compose up -d"
    echo "   docker compose logs -f"
    echo ""
    echo "3. 推送代码到 GitHub"
    echo "   git add ."
    echo "   git commit -m 'chore: prepare for Dokploy deployment'"
    echo "   git push origin master"
    echo ""
    echo "4. 在 Dokploy 中创建项目："
    echo "   - 登录 Dokploy 控制面板"
    echo "   - 创建新项目，选择 Git Repository"
    echo "   - 输入仓库 URL: https://github.com/locfox-com/comfyui-server.git"
    echo "   - 选择部署类型: Docker Compose"
    echo "   - 配置环境变量（可从 .env 复制）"
    echo "   - 点击部署"
    echo ""
    echo "5. 下载 AI 模型（部署后）"
    echo "   docker compose exec comfyui bash /app/download_models.sh"
    echo ""
    echo "详细文档："
    echo "  - Dokploy 部署指南: docs/DOKPLOY_DEPLOYMENT.md"
    echo "  - 项目 README: README.md"
    echo ""
    echo "=========================================="
}

# 主函数
main() {
    check_requirements
    check_gpu
    prepare_env
    validate_config
    generate_api_key
    validate_env_vars
    build_images
    show_summary
}

# 运行主函数
main
