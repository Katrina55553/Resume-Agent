import { useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useDiagnoseStore, type DoubtPoint, type OverallAssessment } from '../stores/diagnoseStore';
import { useInterviewStore } from '../stores/interviewStore';

const PRIORITY_STYLES: Record<string, { bg: string; border: string; badge: string; dot: string; label: string }> = {
  high: {
    bg: 'bg-priority-high-bg',
    border: 'border-priority-high/30',
    badge: 'bg-priority-high/10 text-priority-high',
    dot: 'bg-priority-high',
    label: '高优',
  },
  medium: {
    bg: 'bg-priority-medium-bg',
    border: 'border-priority-medium/30',
    badge: 'bg-priority-medium/10 text-priority-medium',
    dot: 'bg-priority-medium',
    label: '中优',
  },
  low: {
    bg: 'bg-priority-low-bg',
    border: 'border-priority-low/30',
    badge: 'bg-priority-low/10 text-priority-low',
    dot: 'bg-priority-low',
    label: '低优',
  },
};

const DEPTH_LABELS: Record<string, string> = { low: '较弱', medium: '中等', high: '较强' };
const MATCH_LABELS: Record<string, string> = { low: '较低', medium: '中等', high: '较高' };

const STEPS = [
  { index: 1, label: '上传解析' },
  { index: 2, label: '诊断报告' },
  { index: 3, label: '模拟面试' },
  { index: 4, label: '评估报告' },
];

/**
 * 步骤2：诊断报告页
 * 整体评估 + 存疑点列表（可勾选）+ 开始面试
 */
export default function DiagnosePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { result, selectedIds, status, error, fetchDiagnose, togglePoint, selectAll, deselectAll } = useDiagnoseStore();

  useEffect(() => {
    if (id) fetchDiagnose(id);
  }, [id, fetchDiagnose]);

  const handleStartInterview = useCallback(() => {
    if (!id) return;
    // 将选中的存疑点 ID 传递给面试模块
    useInterviewStore.getState().setSelectedPointIds(selectedIds);
    navigate(`/session/${id}/interview`);
  }, [id, navigate, selectedIds]);

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="min-h-screen bg-paper bg-noise flex items-center justify-center px-6">
        <div className="paper-card rounded-2xl px-10 py-12 text-center max-w-md w-full animate-scale-in">
          <div className="relative w-14 h-14 mx-auto mb-6">
            <div className="absolute inset-0 rounded-full border-2 border-accent/20" />
            <div className="absolute inset-0 rounded-full border-2 border-accent border-t-transparent animate-spin" />
          </div>
          <h3 className="font-display text-xl text-ink mb-2">正在生成诊断报告</h3>
          <p className="text-sm text-ink-light">AI 正在审阅简历，识别存疑点...</p>
          <div className="decor-line mt-6" />
          <p className="text-xs text-ink-muted mt-4">步骤 2 / 4 · 诊断报告</p>
        </div>
      </div>
    );
  }

  if (status === 'error' || !result) {
    return (
      <div className="min-h-screen bg-paper bg-noise flex items-center justify-center px-6">
        <div className="paper-card rounded-2xl px-10 py-12 text-center max-w-md w-full animate-scale-in">
          <div className="w-12 h-12 mx-auto mb-5 rounded-full bg-priority-high/10 flex items-center justify-center">
            <svg className="w-6 h-6 text-priority-high" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
            </svg>
          </div>
          <h3 className="font-display text-xl text-ink mb-2">诊断数据加载失败</h3>
          <p className="text-sm text-ink-light mb-6">{error || '请稍后重试'}</p>
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-accent-dark transition"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  const { overall, doubt_points, suggestions } = result;

  return (
    <div className="min-h-screen bg-paper bg-noise relative">
      <div className="relative z-10">
        {/* 顶部导航 */}
        <header className="sticky top-0 z-20 glass-card border-b border-border">
          <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
            <button
              onClick={() => navigate(`/session/${id}/parse`)}
              className="group inline-flex items-center gap-2 text-sm text-ink-light hover:text-accent transition"
            >
              <svg className="w-4 h-4 transition-transform group-hover:-translate-x-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
              </svg>
              返回解析
            </button>

            {/* 步骤指示器 */}
            <div className="hidden sm:flex items-center gap-2">
              {STEPS.map((step, i) => {
                const isCurrent = step.index === 2;
                const isDone = step.index < 2;
                return (
                  <div key={step.index} className="flex items-center gap-2">
                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition ${
                      isCurrent
                        ? 'bg-accent text-white'
                        : isDone
                        ? 'bg-accent-light text-accent-dark'
                        : 'bg-surface text-ink-muted border border-border'
                    }`}>
                      <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${
                        isCurrent ? 'bg-white/20' : isDone ? 'bg-accent/20' : 'bg-border'
                      }`}>
                        {isDone ? '✓' : step.index}
                      </span>
                      {step.label}
                    </div>
                    {i < STEPS.length - 1 && (
                      <div className={`w-4 h-px ${isDone ? 'bg-accent/40' : 'bg-border'}`} />
                    )}
                  </div>
                );
              })}
            </div>

            <span className="sm:hidden text-xs text-ink-muted font-medium">步骤 2/4 · 诊断报告</span>
          </div>
        </header>

        <main className="max-w-5xl mx-auto px-6 py-10 space-y-10">
          {/* 页面标题 */}
          <div className="animate-fade-up">
            <p className="text-xs uppercase tracking-[0.2em] text-accent font-medium mb-2">Diagnosis Report</p>
            <h1 className="font-display text-4xl text-ink leading-tight">
              诊断报告 <span className="text-gradient">·</span> 存疑点审视
            </h1>
            <p className="text-sm text-ink-light mt-2">AI 已识别 {overall.doubt_count} 个存疑点，请勾选需要在面试中重点核实的部分。</p>
            <div className="decor-line mt-6" />
          </div>

          {/* 整体评估 */}
          <OverallAssessmentCard overall={overall} />

          {/* 存疑点列表 */}
          <section className="animate-fade-up" style={{ animationDelay: '0.1s' }}>
            <div className="flex items-end justify-between mb-5">
              <div>
                <h2 className="font-display text-2xl text-ink">存疑点列表</h2>
                <p className="text-xs text-ink-muted mt-1">点击卡片选择 / 取消，将作为面试追问范围</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-sm">
                  <span className="font-display text-2xl text-accent">{selectedIds.length}</span>
                  <span className="text-ink-muted"> / {doubt_points.length}</span>
                </div>
                <button
                  onClick={selectedIds.length === doubt_points.length ? deselectAll : selectAll}
                  className="text-sm text-accent hover:text-accent-dark font-medium transition px-3 py-1.5 rounded-lg border border-accent/20 hover:border-accent/40 hover:bg-accent-light/50"
                >
                  {selectedIds.length === doubt_points.length ? '取消全选' : '全选'}
                </button>
              </div>
            </div>

            <div className="space-y-3">
              {doubt_points.map((point, i) => (
                <DoubtPointCard
                  key={point.id}
                  point={point}
                  selected={selectedIds.includes(point.id)}
                  onToggle={() => togglePoint(point.id)}
                  index={i}
                />
              ))}
            </div>
          </section>

          {/* 改进建议 */}
          <section className="paper-card rounded-2xl p-7 animate-fade-up" style={{ animationDelay: '0.15s' }}>
            <div className="flex items-center gap-3 mb-5">
              <div className="w-8 h-8 rounded-lg bg-accent-light flex items-center justify-center">
                <svg className="w-4 h-4 text-accent" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189a6.01 6.01 0 0 1-1.5-.189m3.75 7.478a12.06 12.06 0 0 1-4.5 0m3.75 2.383a14.406 14.406 0 0 1-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 1 0-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
                </svg>
              </div>
              <div>
                <h2 className="font-display text-xl text-ink">改进建议</h2>
                <p className="text-xs text-ink-muted">基于诊断结果给出的简历优化方向</p>
              </div>
            </div>
            <ul className="space-y-3">
              {suggestions.map((s, i) => (
                <li key={i} className="flex items-start gap-3 group">
                  <span className="font-display text-sm text-accent mt-0.5 shrink-0 w-6 h-6 rounded-full bg-accent-light/60 flex items-center justify-center group-hover:bg-accent-light transition">
                    {i + 1}
                  </span>
                  <p className="text-sm text-ink-light leading-relaxed pt-0.5">{s}</p>
                </li>
              ))}
            </ul>
          </section>

          {/* 开始面试按钮 */}
          <div className="text-center pt-6 pb-12 animate-fade-up" style={{ animationDelay: '0.2s' }}>
            <button
              onClick={handleStartInterview}
              disabled={selectedIds.length === 0}
              className="group inline-flex items-center gap-3 rounded-xl bg-accent px-10 py-4 text-white font-medium text-lg hover:bg-accent-dark transition disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-accent/20 disabled:shadow-none"
            >
              开始模拟面试
              <svg className="w-5 h-5 transition-transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
              </svg>
            </button>
            {selectedIds.length === 0 ? (
              <p className="text-sm text-ink-muted mt-3">请至少选择一个存疑点</p>
            ) : (
              <p className="text-sm text-ink-light mt-3">已选择 {selectedIds.length} 个存疑点，准备进入面试</p>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

/** 整体评估卡片 */
function OverallAssessmentCard({ overall }: { overall: OverallAssessment }) {
  return (
    <div className="paper-card rounded-2xl p-7 animate-fade-up">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded-lg bg-accent-light flex items-center justify-center">
          <svg className="w-4 h-4 text-accent" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
          </svg>
        </div>
        <div>
          <h2 className="font-display text-xl text-ink">整体评估</h2>
          <p className="text-xs text-ink-muted">简历整体质量概览</p>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
        <MetricBar label="简历完整度" value={overall.completeness} suffix="%" />
        <MetricLabel label="技术亮点" value={DEPTH_LABELS[overall.tech_depth] || overall.tech_depth} />
        <MetricLabel label="经验匹配度" value={MATCH_LABELS[overall.match_level] || overall.match_level} />
        <MetricLabel label="存疑点" value={`${overall.doubt_count} 个`} />
      </div>

      <div className="decor-line my-5" />

      <div className="flex items-start gap-3 rounded-xl bg-priority-medium-bg border border-priority-medium/20 px-4 py-3">
        <svg className="w-5 h-5 text-priority-medium shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
        </svg>
        <p className="text-sm text-priority-medium">
          发现 <span className="font-semibold">{overall.doubt_count}</span> 个存疑点，建议面试中重点关注
        </p>
      </div>
    </div>
  );
}

/** 进度条指标 */
function MetricBar({ label, value, suffix = '' }: { label: string; value: number; suffix?: string }) {
  return (
    <div>
      <p className="text-xs text-ink-muted mb-2">{label}</p>
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-border rounded-full h-1.5 overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all duration-700"
            style={{ width: `${Math.min(value, 100)}%` }}
          />
        </div>
        <span className="text-sm font-display font-medium text-ink">{value}{suffix}</span>
      </div>
    </div>
  );
}

/** 文字指标 */
function MetricLabel({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-ink-muted mb-2">{label}</p>
      <p className="text-sm font-display font-medium text-ink">{value}</p>
    </div>
  );
}

/** 存疑点卡片 */
function DoubtPointCard({
  point,
  selected,
  onToggle,
  index,
}: {
  point: DoubtPoint;
  selected: boolean;
  onToggle: () => void;
  index: number;
}) {
  const style = PRIORITY_STYLES[point.priority] || PRIORITY_STYLES.low;

  return (
    <div
      className={`group rounded-xl border p-4 cursor-pointer transition-all duration-200 animate-fade-up ${
        selected
          ? 'border-accent bg-accent-light/40 shadow-sm'
          : `${style.border} ${style.bg} hover:shadow-sm hover:-translate-y-0.5`
      }`}
      style={{ animationDelay: `${0.1 + index * 0.03}s` }}
      onClick={onToggle}
    >
      <div className="flex items-start gap-3">
        {/* 勾选框 */}
        <div className={`mt-0.5 w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 transition ${
          selected ? 'bg-accent border-accent' : 'border-border-strong group-hover:border-ink-muted'
        }`}>
          {selected && (
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
            </svg>
          )}
        </div>

        <div className="flex-1 min-w-0">
          {/* 标题行 */}
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${style.badge}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
              {style.label}
            </span>
            <span className="text-sm font-medium text-ink">{point.reason}</span>
          </div>

          {/* 原文引用 */}
          <div className="border-l-2 border-border-strong pl-3 my-2">
            <p className="text-xs text-ink-light italic line-clamp-2">
              "{point.source_text}"
            </p>
          </div>

          {/* 追问问题预览 */}
          {point.probe_questions?.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-ink-muted mt-2">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
              </svg>
              <span>{point.probe_questions.length} 个追问问题</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
