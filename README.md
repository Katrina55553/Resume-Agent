# 简历智诊 Agent

AI 驱动的简历诊断与模拟面试系统。上传简历 → AI 深度诊断 → 多轮模拟面试 → 量化评估报告。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + Zustand + React Router v6 |
| 后端 | FastAPI + LangGraph + Celery + SQLAlchemy |
| LLM | Claude API / GPT-4o（当前为 mock 实现） |
| 数据库 | PostgreSQL + Redis |
| 部署 | Docker Compose + Nginx |

## 用户流程

1. **简历上传** — 支持 PDF/Word/TXT，异步解析，实时进度
2. **解析确认** — AI 结构化提取，用户内联编辑修正
3. **诊断报告** — AI 标注存疑点（高/中/低优先级），用户勾选面试范围
4. **模拟面试** — 实时对话，LangGraph 状态机驱动动态追问（单点 ≤3 轮自动切换）
5. **评估报告** — 可信度评分 + 逐点反馈 + 改进建议

## 快速开始

### Docker Compose 一键部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/Katrina55553/resume-agent.git
cd resume-agent

# 2. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，按需修改配置

# 3. 启动所有服务
docker compose up -d --build

# 4. 访问
# 浏览器打开 http://localhost:8000
```

### 本地开发

```bash
# 启动数据库和 Redis
docker compose up -d postgres redis

# 后端
cd backend
pip install -r requirements.txt
cp .env.example .env
# 修改 .env 中的数据库连接为 localhost
uvicorn app.main:app --reload --port 8000

# Celery worker
celery -A app.tasks.celery_app worker --loglevel=info

# 前端
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

## 项目结构

```
├── frontend/                  # React SPA
│   ├── src/
│   │   ├── components/Upload/ # FileDropzone, UploadProgress
│   │   ├── pages/             # 5 个页面组件
│   │   ├── stores/            # Zustand 状态管理
│   │   ├── hooks/             # useWebSocket
│   │   └── utils/             # api.ts (Axios 封装)
│   ├── Dockerfile             # 多阶段构建 + Nginx
│   └── nginx.conf             # 反向代理配置
│
├── backend/                   # FastAPI 服务
│   ├── app/
│   │   ├── api/               # REST + WebSocket 路由
│   │   ├── core/              # config, database, redis
│   │   ├── models/            # ORM + Pydantic 模型
│   │   ├── agent/             # LangGraph 状态机
│   │   ├── tasks/             # Celery 异步任务
│   │   ├── middleware/        # auth, rate_limit
│   │   └── utils/security/    # 文件校验, Prompt 防护
│   └── tests/
│
└── docker-compose.yml         # 5 服务编排
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions` | 上传简历 |
| GET | `/api/sessions/{id}/status` | 解析进度 |
| GET/PUT | `/api/sessions/{id}/parse` | 获取/修正解析结果 |
| POST | `/api/sessions/{id}/diagnose` | 触发诊断 |
| GET | `/api/sessions/{id}/diagnose` | 诊断结果 |
| POST | `/api/sessions/{id}/interview/start` | 开始面试 |
| POST | `/api/sessions/{id}/interview/respond` | 提交回答 |
| POST | `/api/sessions/{id}/interview/skip` | 跳过问题 |
| POST | `/api/sessions/{id}/interview/rephrase` | 换个问法 |
| GET | `/api/sessions/{id}/interview/resume` | 恢复面试 |
| GET | `/api/sessions/{id}/report` | 评估报告 |
| WS | `/ws/interview/{id}` | 面试实时对话 |

## 核心设计

### LangGraph 状态机

```
question → collect → evaluate → (follow_up | next | report)
```

### 追问防死循环

1. 单点最多追问 3 轮，超限强制切换
2. 用户可主动跳过
3. 连续异常 3 次触发熔断
