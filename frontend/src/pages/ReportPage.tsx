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
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500">正在生成评估报告...</p>
        </div>
      </div>
    );
  }

  if (status === 'error' || !report) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error || '报告加载失败'}</p>
          <button onClick={() => navigate('/')} className="text-blue-500 underline">返回首页</button>
        </div>
      </div>
    );
  }

  const resolvedCount = report.point_feedbacks?.filter((p) => p.status === 'resolved').length || 0;
  const partialCount = report.point_feedbacks?.filter((p) => p.status !== 'resolved' && p.status !== 'skipped').length || 0;
  const skippedCount = report.skipped_points || 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航 */}
      <div className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <button
          onClick={() => navigate(`/session/${id}/interview`)}
          className="text-gray-500 hover:text-gray-700"
        >
          ← 返回面试
        </button>
        <span className="text-sm text-gray-400">步骤 4/4 · 评估报告</span>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
        {/* 面试总结 */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">面试总结</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
            <div>
              <p className="text-xs text-gray-500 mb-1">面试完成度</p>
              <p className="text-lg font-bold text-gray-800">
                {report.total_points}/{report.total_points} 存疑点已追问
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">综合可信度</p>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-gray-200 rounded-full h-2.5">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${report.overall_score}%` }}
                  />
                </div>
                <span className="text-lg font-bold text-blue-600">{report.overall_score}%</span>
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">可信点</p>
              <p className="text-lg font-bold text-green-600">{resolvedCount} 个</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">存疑/跳过</p>
              <p className="text-lg font-bold text-amber-600">{partialCount + skippedCount} 个</p>
            </div>
          </div>
        </div>

        {/* 逐点反馈 */}
        <div>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">逐点反馈</h2>
          <div className="space-y-3">
            {report.point_feedbacks?.map((fb, i) => (
              <PointFeedbackCard key={i} feedback={fb} />
            ))}
          </div>
        </div>

        {/* 改进建议 */}
        {report.suggestions?.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">改进建议</h2>
            <ul className="space-y-3">
              {report.suggestions.map((s, i) => (
                <li key={i} className="flex items-start gap-3 text-sm text-gray-600">
                  <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-medium shrink-0">
                    {i + 1}
                  </span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 面试总结文字 */}
        {report.summary && (
          <div className="bg-blue-50 rounded-xl border border-blue-100 p-6">
            <h2 className="text-sm font-semibold text-blue-800 mb-2">面试官评语</h2>
            <p className="text-sm text-blue-700 leading-relaxed">{report.summary}</p>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex justify-center gap-4 pt-4">
          <button
            onClick={() => navigate(`/session/${id}/interview`)}
            className="rounded-xl border border-gray-300 px-8 py-3 text-gray-700 font-medium hover:bg-gray-50 transition"
          >
            重新面试
          </button>
          <button
            onClick={() => navigate('/')}
            className="rounded-xl bg-blue-600 px-8 py-3 text-white font-medium hover:bg-blue-700 transition"
          >
            上传新简历
          </button>
        </div>
      </div>
    </div>
  );
}

const STATUS_CONFIG: Record<string, { icon: string; color: string; label: string }> = {
  resolved: { icon: '✓', color: 'text-green-600 bg-green-50 border-green-200', label: '可信' },
  skipped: { icon: '—', color: 'text-gray-500 bg-gray-50 border-gray-200', label: '已跳过' },
};

/** 单个存疑点反馈卡片 */
function PointFeedbackCard({ feedback }: { feedback: PointFeedback }) {
  const [expanded, setExpanded] = useState(false);
  const config = STATUS_CONFIG[feedback.status] || {
    icon: '!',
    color: 'text-amber-600 bg-amber-50 border-amber-200',
    label: '部分可信',
  };

  return (
    <div className={`bg-white rounded-xl border shadow-sm overflow-hidden`}>
      {/* 卡头 */}
      <div
        className="flex items-center gap-3 p-4 cursor-pointer hover:bg-gray-50 transition"
        onClick={() => setExpanded(!expanded)}
      >
        {/* 状态图标 */}
        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border ${config.color}`}>
          {config.icon}
        </div>

        {/* 内容 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${config.color}`}>
              {config.label}
            </span>
            <span className="text-sm text-gray-800 truncate">{feedback.source_text.slice(0, 40)}</span>
          </div>
        </div>

        {/* 评分 */}
        <div className="text-right shrink-0">
          <span className="text-lg font-bold text-gray-700">{feedback.score}</span>
          <span className="text-xs text-gray-400 ml-0.5">分</span>
        </div>

        {/* 展开箭头 */}
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </div>

      {/* 展开内容 */}
      {expanded && (
        <div className="px-4 pb-4 pt-0 border-t">
          <div className="mt-3">
            <p className="text-xs text-gray-500 mb-1">简历原文</p>
            <p className="text-sm text-gray-600 bg-gray-50 rounded p-2">"{feedback.source_text}"</p>
          </div>
          <div className="mt-3">
            <p className="text-xs text-gray-500 mb-1">评估详情</p>
            <p className="text-sm text-gray-600">{feedback.feedback}</p>
          </div>
        </div>
      )}
    </div>
  );
}
