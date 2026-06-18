import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useReportStore, type PointFeedback } from '../stores/reportStore';
import { useInterviewStore } from '../stores/interviewStore';

/**
 * 步骤4：评估报告页
 * 面试总结 + 逐点反馈 + 改进建议
 */
export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { report: storeReport, status, error, fetchReport } = useReportStore();
  const interviewReport = useInterviewStore((s) => s.report);

  // 优先从面试 store 取报告（面试完成后直接跳转过来），否则从 API 获取
  const report = interviewReport || storeReport;

  useEffect(() => {
    if (id && !interviewReport && status === 'idle') {
      fetchReport(id);
    }
  }, [id, interviewReport, status, fetchReport]);

  if (!report && (status === 'loading' || status === 'idle')) {
    return (
      <div className="relative min-h-screen bg-paper bg-noise flex items-center justify-center">
        <div className="relative z-10 text-center animate-fade-in">
          <div className="w-10 h-10 border-2 border-accent/20 border-t-accent rounded-full animate-spin mx-auto mb-5" />
          <p className="font-display text-lg text-ink mb-1">正在生成评估报告</p>
          <p className="text-sm text-ink-muted">AI 正在整理面试记录与评分...</p>
        </div>
      </div>
    );
  }

  if (status === 'error' || !report) {
    return (
      <div className="relative min-h-screen bg-paper bg-noise flex items-center justify-center px-6">
        <div className="relative z-10 paper-card rounded-2xl p-8 max-w-md w-full text-center animate-scale-in">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-priority-high-bg flex items-center justify-center">
            <svg className="w-6 h-6 text-priority-high" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
            </svg>
          </div>
          <p className="font-display text-lg text-ink mb-2">报告加载失败</p>
          <p className="text-sm text-ink-light mb-5">{error || '请稍后重试'}</p>
          <button
            onClick={() => navigate('/')}
            className="rounded-xl bg-accent px-6 py-2.5 text-white text-sm font-medium hover:bg-accent-dark transition"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  const resolvedCount = report.point_feedbacks?.filter((p) => p.status === 'resolved').length || 0;
  const partialCount = report.point_feedbacks?.filter((p) => p.status !== 'resolved' && p.status !== 'skipped').length || 0;
  const skippedCount = report.skipped_points || 0;

  return (
    <div className="relative min-h-screen bg-paper bg-noise">
      {/* 顶部导航 */}
      <div className="sticky top-0 z-20 bg-surface/80 backdrop-blur-md border-b border-border">
        <div className="max-w-4xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <button
            onClick={() => navigate(`/session/${id}/interview`)}
            className="group flex items-center gap-1.5 text-sm text-ink-light hover:text-accent transition"
          >
            <svg className="w-4 h-4 transition-transform group-hover:-translate-x-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
            </svg>
            返回面试
          </button>
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <span className="font-display text-ink-light">步骤 4 / 4</span>
            <span className="w-1 h-1 rounded-full bg-ink-muted/40" />
            <span>评估报告</span>
          </div>
        </div>
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-6 py-10 space-y-8">
        {/* 页面标题 */}
        <div className="animate-fade-up">
          <p className="text-xs tracking-[0.2em] uppercase text-accent font-medium mb-2">Final Report</p>
          <h1 className="font-display text-3xl text-ink leading-tight">评估报告</h1>
          <div className="decor-line mt-4" />
        </div>

        {/* 面试总结 */}
        <div className="paper-card rounded-2xl p-6 sm:p-8 animate-fade-up" style={{ animationDelay: '0.05s' }}>
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-display text-xl text-ink">面试总结</h2>
            <span className="text-xs text-ink-muted">共 {report.total_points} 个存疑点</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
            {/* 完成度 */}
            <div>
              <p className="text-xs text-ink-muted mb-1.5 tracking-wide">面试完成度</p>
              <p className="font-display text-2xl text-ink">
                {report.total_points}/{report.total_points}
              </p>
              <p className="text-xs text-ink-light mt-0.5">存疑点已追问</p>
            </div>
            {/* 可信度 */}
            <div>
              <p className="text-xs text-ink-muted mb-1.5 tracking-wide">综合可信度</p>
              <div className="flex items-baseline gap-1 mb-2">
                <span className="font-display text-2xl text-gradient">{report.overall_score}</span>
                <span className="text-sm text-ink-light">%</span>
              </div>
              <div className="h-1.5 bg-paper-dark rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent rounded-full transition-all duration-700"
                  style={{ width: `${report.overall_score}%` }}
                />
              </div>
            </div>
            {/* 可信点 */}
            <div>
              <p className="text-xs text-ink-muted mb-1.5 tracking-wide">可信点</p>
              <div className="flex items-baseline gap-1">
                <span className="font-display text-2xl text-accent">{resolvedCount}</span>
                <span className="text-sm text-ink-light">个</span>
              </div>
              <p className="text-xs text-ink-light mt-0.5">已澄清</p>
            </div>
            {/* 存疑/跳过 */}
            <div>
              <p className="text-xs text-ink-muted mb-1.5 tracking-wide">存疑 / 跳过</p>
              <div className="flex items-baseline gap-1">
                <span className="font-display text-2xl text-priority-medium">{partialCount + skippedCount}</span>
                <span className="text-sm text-ink-light">个</span>
              </div>
              <p className="text-xs text-ink-light mt-0.5">需关注</p>
            </div>
          </div>
        </div>

        {/* 逐点反馈 */}
        <div className="animate-fade-up" style={{ animationDelay: '0.1s' }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-xl text-ink">逐点反馈</h2>
            <span className="text-xs text-ink-muted">{report.point_feedbacks?.length || 0} 条记录</span>
          </div>
          <div className="space-y-3">
            {report.point_feedbacks?.map((fb, i) => (
              <PointFeedbackCard key={i} feedback={fb} />
            ))}
          </div>
        </div>

        {/* 改进建议 */}
        {report.suggestions?.length > 0 && (
          <div className="paper-card rounded-2xl p-6 sm:p-8 animate-fade-up" style={{ animationDelay: '0.15s' }}>
            <div className="flex items-center gap-2 mb-5">
              <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189a6.01 6.01 0 0 1-1.5-.189m3.75 7.478a12.06 12.06 0 0 1-4.5 0m3.75 2.383a14.406 14.406 0 0 1-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 1 0-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
              </svg>
              <h2 className="font-display text-xl text-ink">改进建议</h2>
            </div>
            <ul className="space-y-3.5">
              {report.suggestions.map((s, i) => (
                <li key={i} className="flex items-start gap-3.5">
                  <span className="shrink-0 w-7 h-7 rounded-lg bg-accent-light text-accent flex items-center justify-center text-sm font-display font-medium">
                    {i + 1}
                  </span>
                  <span className="text-sm text-ink-light leading-relaxed pt-0.5">{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 面试官评语 */}
        {report.summary && (
          <div className="rounded-2xl bg-accent-light/60 border border-accent/20 p-6 sm:p-8 animate-fade-up" style={{ animationDelay: '0.2s' }}>
            <div className="flex items-center gap-2 mb-3">
              <svg className="w-4 h-4 text-accent-dark" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.184-4.183a1.14 1.14 0 0 1 .778-.332 48.294 48.294 0 0 0 5.83-.498c1.585-.233 2.708-1.626 2.708-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" />
              </svg>
              <h2 className="font-display text-sm text-accent-dark tracking-wide">面试官评语</h2>
            </div>
            <p className="font-display text-base text-ink leading-relaxed italic">"{report.summary}"</p>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex justify-center pt-4 pb-8 animate-fade-up" style={{ animationDelay: '0.25s' }}>
          <button
            onClick={() => navigate('/')}
            className="group inline-flex items-center gap-2 rounded-xl bg-accent px-8 py-3.5 text-white font-medium shadow-sm hover:bg-accent-dark hover:shadow-md transition-all"
          >
            回到首页
            <svg className="w-4 h-4 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

const STATUS_CONFIG: Record<string, { icon: string; color: string; label: string }> = {
  resolved: { icon: '✓', color: 'text-accent bg-accent-light border-accent/30', label: '可信' },
  skipped: { icon: '—', color: 'text-ink-muted bg-paper-dark border-border', label: '已跳过' },
};

/** 单个存疑点反馈卡片 */
function PointFeedbackCard({ feedback }: { feedback: PointFeedback }) {
  const [expanded, setExpanded] = useState(false);
  const config = STATUS_CONFIG[feedback.status] || {
    icon: '!',
    color: 'text-priority-medium bg-priority-medium-bg border-priority-medium/30',
    label: '部分可信',
  };

  return (
    <div className="paper-card rounded-xl overflow-hidden transition-shadow hover:shadow-md">
      {/* 卡头 */}
      <div
        className="flex items-center gap-3 p-4 cursor-pointer hover:bg-paper/50 transition"
        onClick={() => setExpanded(!expanded)}
      >
        {/* 状态图标 */}
        <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-display font-bold border ${config.color}`}>
          {config.icon}
        </div>

        {/* 内容 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-md font-medium border ${config.color}`}>
              {config.label}
            </span>
            <span className="text-sm text-ink truncate">{feedback.source_text.slice(0, 40)}</span>
          </div>
        </div>

        {/* 评分 */}
        <div className="text-right shrink-0">
          <span className="font-display text-xl text-ink">{feedback.score}</span>
          <span className="text-xs text-ink-muted ml-0.5">分</span>
        </div>

        {/* 展开箭头 */}
        <svg
          className={`w-4 h-4 text-ink-muted transition-transform duration-300 ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </div>

      {/* 展开内容 — grid-rows 实现高度过渡动画 */}
      <div
        className={`grid transition-all duration-300 ease-out ${expanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}
      >
        <div className="overflow-hidden">
          <div className="px-4 pb-4">
            <div className="decor-line my-3" />
            <div>
              <p className="text-xs text-ink-muted mb-1.5 tracking-wide">简历原文</p>
              <p className="text-sm text-ink-light bg-paper-dark rounded-lg p-3 leading-relaxed">"{feedback.source_text}"</p>
            </div>
            <div className="mt-3">
              <p className="text-xs text-ink-muted mb-1.5 tracking-wide">评估详情</p>
              <p className="text-sm text-ink-light leading-relaxed">{feedback.feedback}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
