interface UploadProgressProps {
  fileName: string;
  progress: number;
  status: string;
  error?: string | null;
  onRetry?: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  uploading: '正在上传...',
  parsing: '正在解析简历...',
  parsed: '解析完成',
  failed: '解析失败',
};

/**
 * 上传进度条组件
 * 显示文件名、进度百分比、状态文案
 */
export default function UploadProgress({ fileName, progress, status, error, onRetry }: UploadProgressProps) {
  const percent = Math.min(Math.round(progress * 100), 100);
  const label = STATUS_LABELS[status] || status;

  return (
    <div className="w-full max-w-md mx-auto">
      {/* 文件名 */}
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center shrink-0">
          <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
          </svg>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-800 truncate">{fileName}</p>
          <p className="text-xs text-gray-500">{label}</p>
        </div>
        <span className="text-sm font-semibold text-blue-600">{percent}%</span>
      </div>

      {/* 进度条 */}
      <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            status === 'failed' ? 'bg-red-500' : 'bg-blue-600'
          }`}
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* 错误信息 + 重试 */}
      {status === 'failed' && (
        <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-4">
          <p className="text-sm text-red-600 mb-2">{error || '解析失败，请重试'}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="text-sm text-red-700 font-medium underline hover:no-underline"
            >
              重新上传
            </button>
          )}
        </div>
      )}
    </div>
  );
}
