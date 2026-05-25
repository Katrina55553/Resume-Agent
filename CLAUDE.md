# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**简历智诊 Agent** — AI 驱动的简历诊断与模拟面试系统。用户上传简历 → AI 深度诊断 → 多轮模拟面试 → 量化评估报告。

设计文档：`AI 简历诊断 + 模拟面试 Agent — 完整流程文档.txt`（所有需求细节以此为准）

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + Zustand + React Router v6 + Axios + React Query |
| 后端 | FastAPI (Python) + LangGraph (Agent 编排) + Celery + Redis (异步任务) |
| LLM | Claude API / GPT-4o |
| 数据库 | PostgreSQL (结构化数据) + Redis (缓存/限流/WebSocket 状态) |
| 可观测 | OpenTelemetry + Prometheus + Grafana |
| 部署 | Docker Compose |

## 核心架构

### 用户流程（4 步）

1. **简历上传** — PDF/Word/TXT，Celery 异步解析，前端轮询进度
2. **解析确认** — AI 结构化提取 + 用户内联编辑修正
3. **诊断报告** — AI 标注存疑点（高/中/低优先级），用户勾选面试范围
4. **模拟面试** — WebSocket 实时对话，LangGraph 状态机驱动动态追问
5. **评估报告** — 可信度评分 + 逐点反馈 + 改进建议

### LangGraph Agent 状态机

核心循环：`question → collect → evaluate`，evaluate 后条件分支：
- `follow_up` → 继续追问当前存疑点
- `next` → 切换到下一个存疑点
- `report` → 生成最终报告

状态定义见 `agent/state.py`（`AgentState` TypedDict），图定义见 `agent/graph.py`。

### 追问防死循环（三层保障）

1. 单点最多追问 3 轮，超限强制切换
2. 用户可主动跳过
3. 连续异常 3 次触发熔断

规则引擎在 `agent/rules.py`（`InterviewRules` 类）。

### 上下文压缩策略

面试 prompt 只包含：简历关键字段（~200 tokens）+ 最近 6 轮对话（~500 tokens）+ 已确认技能点（~100 tokens），单次面试 Token 控制在 5000 以内。

## 项目结构（规划）

```
frontend/              # React SPA
├── src/
│   ├── components/    # 按功能模块分：Upload/, Parse/, Diagnose/, Interview/, Report/, shared/
│   ├── pages/         # HomePage, ParsePage, DiagnosePage, InterviewPage, ReportPage
│   ├── stores/        # Zustand：sessionStore, diagnoseStore, interviewStore, reportStore
│   ├── hooks/         # useWebSocket（封装 WS + 自动重连 + 消息队列）, usePolling
│   └── utils/         # api.ts (Axios 封装), constants.ts

backend/               # FastAPI
├── app/
│   ├── api/           # 路由：sessions, diagnose, interview, report, ws
│   ├── core/          # config, database, redis 连接
│   ├── models/        # Pydantic 校验模型 + SQLAlchemy ORM
│   ├── agent/         # LangGraph：state.py, graph.py, nodes/(question, collect, evaluate, report), rules.py
│   ├── tasks/         # Celery：celery_app.py, parse_task.py, report_task.py
│   ├── middleware/     # auth.py, rate_limit.py
│   └── utils/security/ # file_upload.py（四重校验）, prompt_guard.py, masking.py
└── tests/
```

## API 设计要点

- 统一响应格式：`{code, message, data, trace_id}`
- 错误码：0=成功, 1001=参数校验, 1002=会话不存在, 2001=LLM 超时, 2002=LLM 限流, 3001=面试状态异常, 429=限流
- 面试通过 WebSocket `/ws/interview/{id}` 实时通信，同时保留 REST 降级接口
- 所有查询强制带 `user_id` 实现数据隔离

## 安全要求

- 文件上传：扩展名 + MIME + 魔数 + 大小（10MB），四重校验，随机重命名存储
- Prompt 注入防护：分隔符隔离用户输入 + 正则过滤 + Pydantic 校验输出
- 敏感信息脱敏：手机号/邮箱自动脱敏，日志不记录完整内容
- 限流：Redis 滑动窗口，单会话 Token 配额上限 50000

## 数据库关键表

- `sessions` — 会话（UUID 主键，软删除）
- `resume_extracts` — 简历解析结果（JSONB 存结构化数据）
- `doubt_points` — 存疑点（priority: high/medium/low）
- `interview_states` — 面试 Checkpoint（断点恢复）
- `interview_messages` — 面试对话消息
- `reports` — 评估报告

## 开发计划

5 周迭代：W1 基础搭建 → W2 解析+诊断 → W3 面试 FSM → W4 报告+安全 → W5 部署
