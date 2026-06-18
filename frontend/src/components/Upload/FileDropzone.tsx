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
          p-12 text-center transition-all duration-300
          ${isDragging
            ? 'border-accent bg-accent-light/40 scale-[1.02]'
            : 'border-border-strong hover:border-accent hover:bg-paper-dark/50'
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
          <div className={`w-14 h-14 rounded-xl flex items-center justify-center transition-colors ${
            isDragging ? 'bg-accent text-white' : 'bg-accent-light text-accent'
          }`}>
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
            </svg>
          </div>
          <div>
            <p className="text-lg font-medium text-ink">
              {isDragging ? '松开即可上传' : '拖拽简历到此处'}
            </p>
            <p className="text-sm text-ink-light mt-1">
              或 <span className="text-accent underline">点击选择文件</span>
            </p>
          </div>

          <p className="text-xs text-ink-muted">
            支持 PDF / Word / TXT，最大 {MAX_SIZE_MB}MB
          </p>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mt-3 rounded-lg bg-priority-high-bg border border-priority-high/20 px-4 py-3 text-sm text-priority-high">
          {error}
        </div>
      )}
    </div>
  );
}
