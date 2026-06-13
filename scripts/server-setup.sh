#!/bin/bash
# ============================================================
# 服务器初始化脚本 — 在目标服务器上运行一次即可
# 用法: bash scripts/server-setup.sh
# ============================================================

set -e

echo "=== 1. 安装 Docker ==="
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "Docker installed."
else
    echo "Docker already installed, skipping."
fi

echo "=== 2. 安装 Docker Compose 插件 ==="
if ! docker compose version &>/dev/null; then
    apt-get update && apt-get install -y docker-compose-plugin
    echo "Docker Compose plugin installed."
else
    echo "Docker Compose plugin already installed, skipping."
fi

echo "=== 3. 创建部署目录 ==="
DEPLOY_DIR="/root/resume-agent"
mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

echo "=== 4. 克隆代码（如果尚未存在）==="
if [ ! -d ".git" ]; then
    echo "请手动执行: git clone <your-repo-url> ."
    echo "然后运行: bash scripts/server-setup.sh"
else
    echo "代码已存在，跳过克隆。"
fi

echo "=== 5. 配置 GitHub Actions 部署公钥 ==="
AUTH_DIR="$HOME/.ssh"
mkdir -p "$AUTH_DIR"
chmod 700 "$AUTH_DIR"

if [ ! -f "$AUTH_DIR/id_ed25519" ]; then
    ssh-keygen -t ed25519 -f "$AUTH_DIR/id_ed25519" -N "" -C "deploy@resume-agent"
    echo ""
    echo "=========================================="
    echo "  部署密钥已生成！"
    echo "  请将以下公钥添加到 GitHub Secrets: SERVER_SSH_KEY"
    echo "=========================================="
    cat "$AUTH_DIR/id_ed25519"
    echo ""
    echo "  公钥（添加到服务器 ~/.ssh/authorized_keys）:"
    cat "$AUTH_DIR/id_ed25519.pub"
    echo "=========================================="
else
    echo "SSH 密钥已存在，跳过生成。"
fi

echo "=== 6. 创建 .env 文件模板 ==="
if [ ! -f "$DEPLOY_DIR/backend/.env" ]; then
    cat > "$DEPLOY_DIR/backend/.env" << 'ENVEOF'
# === LLM 配置 ===
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# === 数据库 ===
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/resume_agent

# === Redis ===
REDIS_URL=redis://redis:6379/0

# === 安全 ===
SECRET_KEY=change-me-to-a-random-string
ENVEOF
    echo ".env 模板已创建，请编辑: $DEPLOY_DIR/backend/.env"
else
    echo ".env 已存在，跳过。"
fi

echo ""
echo "=== 初始化完成！==="
echo "下一步:"
echo "  1. 编辑 $DEPLOY_DIR/backend/.env 填入真实配置"
echo "  2. 在 GitHub 仓库 Settings > Secrets 中配置:"
echo "     - SERVER_HOST: 服务器 IP"
echo "     - SERVER_USER: 登录用户名（如 root）"
echo "     - SERVER_SSH_KEY: 上面生成的私钥内容"
echo "     - DEPLOY_PATH: $DEPLOY_DIR"
echo "  3. push 代码到 main 分支即可自动部署"
