import { useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useDiagnoseStore, type DoubtPoint, type OverallAssessment } from '../stores/diagnoseStore';
import { useInterviewStore } from '../stores/interviewStore';

const PRIORITY_STYLES: Record<string, { bg: string; badge: string; label: string }> = {
  high: { bg: 'border-red-200 bg-red-50', badge: 'bg-red-100 text-red-700', label: '高优' },
  medium: { bg: 'border-yellow-200 bg-yellow-50', badge: 'bg-yellow-100 text-yellow-700', label: '中优' },
  low: { bg: 'border-green-200 bg-green-50', badge: 'bg-green-100 text-green-700', label: '低优' },
};

const DEPTH_LABELS: Record<string, string> = { low: '较弱', medium: '中等', high: '较强' };
const MATCH_LABELS: Record<string, string> = { low: '较低', medium: '中等', high: '较高' };

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
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500">正在生成诊断报告...</p>
        </div>
      </div>
    );
  }

  if (status === 'error' || !result) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error || '诊断数据加载失败'}</p>
          <button onClick={() => navigate('/')} className="text-blue-500 underline">返回首页</button>
        </div>
      </div>
    );
  }

  const { overall, doubt_points, suggestions } = result;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航 */}
      <div className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <button
          onClick={() => navigate(`/session/${id}/parse`)}
          className="text-gray-500 hover:text-gray-700"
        >
          ← 返回解析
        </button>
        <span className="text-sm text-gray-400">步骤 2/4 · 诊断报告</span>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
        {/* 整体评估 */}
        <OverallAssessmentCard overall={overall} />

        {/* 存疑点列表 */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-800">
              存疑点列表
            </h2>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">
                已选 {selectedIds}/{doubt_points.length}
              </span>
              <button
                onClick={selectedIds.length === doubt_points.length ? deselectAll : selectAll}
                className="text-sm text-blue-600 hover:text-blue-700"
              >
                {selectedIds.length === doubt_points.length ? '取消全选' : '全选'}
              </button>
            </div>
          </div>

          <div className="space-y-3">
            {doubt_points.map((point) => (
              <DoubtPointCard
                key={point.id}
                point={point}
                selected={selectedIds.includes(point.id)}
                onToggle={() => togglePoint(point.id)}
              />
            ))}
          </div>
        </div>

        {/* 改进建议 */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">改进建议</h2>
          <ul className="space-y-2">
            {suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                <span className="text-blue-500 mt-0.5">{i + 1}.</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* 开始面试按钮 */}
        <div className="text-center pt-4">
          <button
            onClick={handleStartInterview}
            disabled={selectedIds.length === 0}
            className="rounded-xl bg-blue-600 px-10 py-3 text-white font-medium text-lg hover:bg-blue-700 transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            开始模拟面试 →
          </button>
          {selectedIds.length === 0 && (
            <p className="text-sm text-gray-400 mt-2">请至少选择一个存疑点</p>
          )}
        </div>
      </div>
    </div>
  );
}

/** 整体评估卡片 */
function OverallAssessmentCard({ overall }: { overall: OverallAssessment }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">整体评估</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricBar label="简历完整度" value={overall.completeness} suffix="%" />
        <MetricLabel label="技术亮点" value={DEPTH_LABELS[overall.tech_depth] || overall.tech_depth} />
        <MetricLabel label="经验匹配度" value={MATCH_LABELS[overall.match_level] || overall.match_level} />
        <MetricLabel label="存疑点" value={`${overall.doubt_count} 个`} />
      </div>
      <p className="mt-4 text-sm text-amber-600 bg-amber-50 rounded-lg px-4 py-2">
        发现 {overall.doubt_count} 个存疑点，建议面试中重点关注
      </p>
    </div>
  );
}

/** 进度条指标 */
function MetricBar({ label, value, suffix = '' }: { label: string; value: number; suffix?: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-gray-200 rounded-full h-2">
          <div
            className="h-full bg-blue-500 rounded-full transition-all"
            style={{ width: `${Math.min(value, 100)}%` }}
          />
        </div>
        <span className="text-sm font-medium text-gray-700">{value}{suffix}</span>
      </div>
    </div>
  );
}

/** 文字指标 */
function MetricLabel({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-sm font-medium text-gray-700">{value}</p>
    </div>
  );
}

/** 存疑点卡片 */
function DoubtPointCard({
  point,
  selected,
  onToggle,
}: {
  point: DoubtPoint;
  selected: boolean;
  onToggle: () => void;
}) {
  const style = PRIORITY_STYLES[point.priority] || PRIORITY_STYLES.low;

  return (
    <div
      className={`rounded-xl border-2 p-4 cursor-pointer transition-all ${
        selected ? 'border-blue-400 bg-blue-50/50' : style.bg
      } hover:shadow-sm`}
      onClick={onToggle}
    >
      <div className="flex items-start gap-3">
        {/* 勾选框 */}
        <div className={`mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition ${
          selected ? 'bg-blue-500 border-blue-500' : 'border-gray-300'
        }`}>
          {selected && (
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
            </svg>
          )}
        </div>

        <div className="flex-1 min-w-0">
          {/* 标题行 */}
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${style.badge}`}>
              {style.label}
            </span>
            <span className="text-sm font-medium text-gray-800 truncate">{point.reason}</span>
          </div>

          {/* 原文引用 */}
          <p className="text-xs text-gray-500 mt-1 line-clamp-2">
            "{point.source_text}"
          </p>

          {/* 追问问题预览 */}
          {point.probe_questions?.length > 0 && (
            <p className="text-xs text-gray-400 mt-2">
              {point.probe_questions.length} 个追问问题
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
