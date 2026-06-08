FROM python:3.11-slim

WORKDIR /app

# 换阿里云 Debian 镜像源（加速 apt）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖（python-magic 需要 libmagic，psycopg2 需要 libpq-dev）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装（重试 3 次，优先用预编译 wheel）
COPY requirements.txt .
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --default-timeout=120 \
    --retries=3 \
    --prefer-binary \
    -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
