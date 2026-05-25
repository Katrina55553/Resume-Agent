import { useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSessionStore } from '../stores/sessionStore';
import FileDropzone from '../components/Upload/FileDropzone';
import UploadProgress from '../components/Upload/UploadProgress';

/**
 * 首页 — 上传简历
 * 文件选择 → 上传 → 轮询进度 → 自动跳转到解析确认页
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

  // 解析完成，自动跳转
  useEffect(() => {
    if (status === 'parsed' && sessionId) {
      const timer = setTimeout(() => {
        navigate(`/session/${sessionId}/parse`);
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [status, sessionId, navigate]);

  // 组件卸载时停止轮询
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

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-lg">
        {/* 标题 */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">
            AI 简历诊断 + 模拟面试
          </h1>
          <p className="text-gray-500">
            上传你的简历，开始智能诊断与模拟面试
          </p>
        </div>

        {/* 上传区域 / 进度条 */}
        {isBusy || status === 'failed' ? (
          <UploadProgress
            fileName={fileName || ''}
            progress={progress}
            status={status}
            error={error}
            onRetry={status === 'failed' ? handleRetry : undefined}
          />
        ) : status === 'parsed' ? (
          <div className="text-center rounded-2xl bg-green-50 border border-green-200 p-8">
            <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
              </svg>
            </div>
            <p className="text-green-700 font-medium">解析完成，正在跳转...</p>
          </div>
        ) : (
          <FileDropzone
            onFileSelected={handleFileSelected}
            disabled={false}
          />
        )}

      </div>
    </div>
  );
}
