import { useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSessionStore } from '../stores/sessionStore';
import FileDropzone from '../components/Upload/FileDropzone';
import UploadProgress from '../components/Upload/UploadProgress';

const FEATURES = [
  {
    title: 'AI 简历诊断',
    desc: '智能识别简历中的存疑点，标注高/中/低优先级',
  },
  {
    title: '模拟面试',
    desc: '基于 LangGraph 状态机的多轮追问，验证简历真实性',
  },
  {
    title: '量化评估',
    desc: '可信度评分 + 逐点反馈 + 改进建议',
  },
];

const STEPS = [
  { step: '01', title: '上传简历', desc: '支持 PDF / Word / TXT' },
  { step: '02', title: 'AI 解析', desc: '结构化提取关键信息' },
  { step: '03', title: '诊断报告', desc: '识别存疑点与改进空间' },
  { step: '04', title: '模拟面试', desc: '多轮追问验证真实性' },
];

/**
 * 首页 — 上传简历
 */
export default function HomePage() {
  const navigate = useNavigate();
  const {
    sessionId, status, progress, error, fileName,
    uploadFile, startPolling, stopPolling, reset,
  } = useSessionStore();

  const isUploading = status === 'uploading';
  const isParsing = status === 'parsing';
  const isBusy = isUploading || isParsing;

  useEffect(() => {
    if (status === 'parsed' && sessionId) {
      const timer = setTimeout(() => {
        navigate(`/session/${sessionId}/parse`);
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [status, sessionId, navigate]);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const handleFileSelected = useCallback(async (file: File) => {
    try {
      const id = await uploadFile(file);
      startPolling(id);
    } catch {
      // 错误已在 store 中处理
    }
  }, [uploadFile, startPolling]);

  const handleRetry = useCallback(() => {
    reset();
  }, [reset]);

  // 进入首页时清空旧 session，避免残留状态导致自动跳转
  useEffect(() => {
    reset();
  }, [reset]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* 导航栏 */}
      <nav className="flex items-center justify-between px-8 py-4">
        <span className="text-lg font-bold text-gray-800">简历智诊</span>
        <a
          href="https://github.com/Katrina55553/resume-agent"
          target="_blank"
          rel="noopener noreferrer"
          className="text-gray-400 hover:text-gray-700 transition"
          title="GitHub"
        >
          <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
          </svg>
        </a>
      </nav>

      {/* Hero 区域 */}
      <div className="max-w-6xl mx-auto px-6 pt-12 pb-16">
        <div className="text-center mb-12">
          <div className="inline-block mb-4 px-4 py-1.5 rounded-full bg-blue-100 text-blue-700 text-sm font-medium">
            AI 驱动 · DeepSeek + LangGraph + RAG
          </div>
          <h1 className="text-5xl font-bold text-gray-900 mb-4 leading-tight">
            AI 简历诊断
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent"> + </span>
            模拟面试
          </h1>
          <p className="text-lg text-gray-500 max-w-2xl mx-auto">
            上传简历 → AI 深度诊断 → 多轮模拟面试 → 量化评估报告
          </p>
        </div>

        {/* 上传卡片 */}
        <div className="max-w-xl mx-auto mb-16">
          <div className="bg-white rounded-2xl shadow-lg shadow-blue-100/50 border border-gray-100 p-8">
            {isBusy || status === 'failed' ? (
              <UploadProgress
                fileName={fileName || ''}
                progress={progress}
                status={status}
                error={error}
                onRetry={status === 'failed' ? handleRetry : undefined}
              />
            ) : status === 'parsed' ? (
              <div className="text-center py-4">
                <p className="text-green-700 font-medium text-lg">解析完成，正在跳转...</p>
              </div>
            ) : (
              <FileDropzone
                onFileSelected={handleFileSelected}
                disabled={false}
              />
            )}
          </div>
        </div>

        {/* 功能亮点 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm hover:shadow-md transition-shadow"
            >
              <h3 className="text-lg font-semibold text-gray-800 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* 流程步骤 */}
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-gray-800 mb-2">使用流程</h2>
          <p className="text-gray-500">四步完成简历诊断与模拟面试</p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {STEPS.map((s) => (
            <div key={s.step} className="text-center">
              <div className="text-4xl font-bold text-blue-300 mb-2">{s.step}</div>
              <h4 className="font-semibold text-gray-800 mb-1">{s.title}</h4>
              <p className="text-sm text-gray-500">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 底部 */}
      <footer className="text-center py-6 text-sm text-gray-400">
        © 2026 简历智诊 Agent · Powered by DeepSeek + LangGraph
      </footer>
    </div>
  );
}
