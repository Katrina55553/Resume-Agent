# 阶段1：构建
FROM node:lts-alpine AS builder

WORKDIR /app

# 直接下载 Node 22 二进制，替换容器内旧版本
RUN apk add --no-cache curl xz && \
    curl -fsSL https://cdn.npmmirror.com/binaries/node/v22.16.0/node-v22.16.0-linux-x64-musl.tar.xz | \
    tar -xJ -C /usr/local --strip-components=1 && \
    node -v

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# 阶段2：Nginx 部署
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
