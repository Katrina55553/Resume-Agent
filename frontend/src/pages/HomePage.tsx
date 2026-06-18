import { useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSessionStore } from '../stores/sessionStore';
import FileDropzone from '../components/Upload/FileDropzone';
import UploadProgress from '../components/Upload/UploadProgress';

const FEATURES = [
  {
    title: 'AI 简历诊断',
    desc: '智能识别简历中的存疑点，标注高/中/低优先级，精准定位薄弱环节',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" />
      </svg>
    ),
  },
  {
    title: '模拟面试',
    desc: '基于 LangGraph 状态机的多轮追问，像真实面试官一样层层深入验证',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a7.115 7.115 0 0 1-.625-.174 3.256 3.256 0 0 1-1.5-.767m6.736-3.042a49.86 49.86 0 0 0-3.27-.523M3 9.5a2.25 2.25 0 0 1 2.25-2.25h.5a2.25 2.25 0 0 1 2.25 2.25v3a2.25 2.25 0 0 1-2.25 2.25h-.5A2.25 2.25 0 0 1 3 12.5v-3Z" />
      </svg>
    ),
  },
  {
    title: '量化评估',
    desc: '可信度评分 + 逐点反馈 + 改进建议，量化呈现简历真实度',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
      </svg>
    ),
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
    <div className="min-h-screen bg-paper bg-noise">
      {/* 导航栏 */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
            <svg className="w-4.5 h-4.5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" />
            </svg>
          </div>
          <span className="font-display text-xl font-semibold text-ink tracking-tight">简历智诊</span>
        </div>
        <a
          href="https://github.com/Katrina55553/resume-agent"
          target="_blank"
          rel="noopener noreferrer"
          className="text-ink-muted hover:text-ink transition"
          title="GitHub"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
          </svg>
        </a>
      </nav>

      {/* Hero 区域 */}
      <div className="relative z-10 max-w-6xl mx-auto px-6 pt-16 pb-20">
        <div className="text-center mb-14">
          <div className="inline-flex items-center gap-2 mb-6 px-4 py-1.5 rounded-full bg-accent-light/60 border border-accent/20 text-accent text-sm font-medium animate-fade-in">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            AI 驱动 · DeepSeek + LangGraph + RAG
          </div>
          <h1 className="font-display text-6xl font-light text-ink mb-5 leading-[1.1] tracking-tight animate-fade-up">
            简历深度诊断
            <br />
            <span className="text-gradient font-medium">与模拟面试</span>
          </h1>
          <p className="text-lg text-ink-light max-w-2xl mx-auto leading-relaxed animate-fade-up" style={{ animationDelay: '0.1s' }}>
            上传简历，AI 深度解析存疑点，多轮追问验证真实性，
            <br className="hidden sm:block" />
            生成量化评估报告 — 让每一份简历都经得起检验
          </p>
        </div>

        {/* 上传卡片 */}
        <div className="max-w-xl mx-auto mb-20 animate-scale-in" style={{ animationDelay: '0.2s' }}>
          <div className="glass-card rounded-2xl p-8">
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
                <div className="w-12 h-12 rounded-full bg-accent-light mx-auto mb-3 flex items-center justify-center">
                  <svg className="w-6 h-6 text-accent" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                  </svg>
                </div>
                <p className="text-accent font-medium text-lg">解析完成，正在跳转...</p>
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-20">
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              className="paper-card rounded-xl p-6 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300 animate-fade-up"
              style={{ animationDelay: `${0.3 + i * 0.1}s` }}
            >
              <div className="w-10 h-10 rounded-lg bg-accent-light text-accent flex items-center justify-center mb-4">
                {f.icon}
              </div>
              <h3 className="font-display text-lg font-semibold text-ink mb-2">{f.title}</h3>
              <p className="text-sm text-ink-light leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* 流程步骤 */}
        <div className="text-center mb-10">
          <div className="decor-line max-w-xs mx-auto mb-6" />
          <h2 className="font-display text-3xl font-light text-ink mb-2">使用流程</h2>
          <p className="text-ink-light">四步完成简历诊断与模拟面试</p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {STEPS.map((s, i) => (
            <div key={s.step} className="text-center group">
              <div className="font-display text-5xl font-light text-border-strong mb-3 transition-colors group-hover:text-accent">
                {s.step}
              </div>
              <div className="decor-line w-8 mx-auto mb-3" />
              <h4 className="font-semibold text-ink mb-1">{s.title}</h4>
              <p className="text-sm text-ink-light">{s.desc}</p>
              {i < STEPS.length - 1 && (
                <div className="hidden md:block absolute" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 底部 */}
      <footer className="relative z-10 text-center py-8 text-sm text-ink-muted">
        <div className="decor-line max-w-2xl mx-auto mb-6" />
        © 2026 简历智诊 Agent · Powered by DeepSeek + LangGraph
      </footer>
    </div>
  );
}
