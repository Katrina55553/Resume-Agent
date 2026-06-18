# 简历智诊 · 前端

基于 React 19 + TypeScript + Vite + Tailwind CSS 4 的 SPA 前端。

## 快速开始

```bash
npm install
npm run dev      # 开发服务器 (http://localhost:5173)
npm run build    # 生产构建（产物在 dist/）
npm run lint     # ESLint 检查
```

## 页面路由

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | [HomePage.tsx](src/pages/HomePage.tsx) | 首页，上传简历 |
| `/session/{id}/parse` | [ParsePage.tsx](src/pages/ParsePage.tsx) | 解析确认，内联编辑结构化字段 |
| `/session/{id}/diagnose` | [DiagnosePage.tsx](src/pages/DiagnosePage.tsx) | 诊断报告，勾选存疑点 |
| `/session/{id}/interview` | [InterviewPage.tsx](src/pages/InterviewPage.tsx) | 模拟面试，WebSocket 实时对话 |
| `/session/{id}/report` | [ReportPage.tsx](src/pages/ReportPage.tsx) | 评估报告，量化评分与反馈 |

## 状态管理（Zustand）

- `sessionStore`：上传与解析进度
- `diagnoseStore`：诊断报告与存疑点选择
- `interviewStore`：WebSocket 连接、消息队列、重连逻辑
- `reportStore`：评估报告数据

## 设计规范

- **设计风格**：Refined Editorial —— 暖纸色背景 + 墨黑排版 + 翡翠绿点缀
- **字体**：Fraunces（衬线展示体） × Plus Jakarta Sans（正文）
- **色彩变量**：在 `src/index.css` 中定义，使用时引用 CSS 变量
- **动效**：错峰入场动画（animate-fade-up）、缩放入场（animate-scale-in）
- **组件容器**：`glass-card`（毛玻璃）、`paper-card`（纸质）

详见 [../README.md](../README.md) 项目根 README 与 [src/index.css](src/index.css)。
