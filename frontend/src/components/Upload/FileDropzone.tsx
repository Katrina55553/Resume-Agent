import { useCallback, useState, useRef } from 'react';

interface FileDropzoneProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

const ACCEPTED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
  'text/plain',
];

const ACCEPTED_EXTENSIONS = '.pdf,.docx,.doc,.txt';
const MAX_SIZE_MB = 10;

/**
 * 拖拽上传组件
 * 支持拖拽和点击选择文件，校验类型和大小
 */
export default function FileDropzone({ onFileSelected, disabled }: FileDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback((file: File): string | null => {
    if (!ACCEPTED_TYPES.includes(file.type) && !file.name.match(/\.(pdf|docx?|txt)$/i)) {
      return '不支持的文件类型，请上传 PDF、Word 或 TXT 文件';
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      return `文件大小超过 ${MAX_SIZE_MB}MB 限制`;
    }
    if (file.size === 0) {
      return '文件为空';
    }
    return null;
  }, []);

  const handleFile = useCallback((file: File) => {
    setError(null);
    const err = validateFile(file);
    if (err) {
      setError(err);
      return;
    }
    onFileSelected(file);
  }, [validateFile, onFileSelected]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [disabled, handleFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleClick = useCallback(() => {
    if (!disabled) inputRef.current?.click();
  }, [disabled]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    // 重置 input 以便重复选择同一文件
    e.target.value = '';
  }, [handleFile]);

  return (
    <div>
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        className={`
          relative cursor-pointer rounded-2xl border-2 border-dashed
          p-12 text-center transition-all duration-200
          ${isDragging
            ? 'border-blue-500 bg-blue-50 scale-[1.02]'
            : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
          }
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          onChange={handleChange}
          className="hidden"
        />

        <div className="flex flex-col items-center gap-4">
          {/* 上传图标 */}
          <div className={`
            w-16 h-16 rounded-full flex items-center justify-center
            ${isDragging ? 'bg-blue-100' : 'bg-gray-100'}
          `}>
            <svg className="w-8 h-8 text-blue-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m6.75 12-3-3m0 0-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
          </div>

          <div>
            <p className="text-lg font-medium text-gray-700">
              {isDragging ? '松开即可上传' : '拖拽简历到此处'}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              或 <span className="text-blue-500 underline">点击选择文件</span>
            </p>
          </div>

          <p className="text-xs text-gray-400">
            支持 PDF / Word / TXT，最大 {MAX_SIZE_MB}MB
          </p>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mt-3 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}
    </div>
  );
}
