import { create } from 'zustand';
import api from '../utils/api';

/** 会话状态类型 */
export type SessionStatus = 'idle' | 'uploading' | 'parsing' | 'parsed' | 'failed' | 'error';

interface SessionState {
  /** 当前会话 ID */
  sessionId: string | null;
  /** 当前会话状态 */
  status: SessionStatus;
  /** 进度百分比 0-1 */
  progress: number;
  /** 错误信息 */
  error: string | null;
  /** 上传的文件名 */
  fileName: string | null;
  /** 轮询定时器 ID */
  _pollTimer: ReturnType<typeof setInterval> | null;

  // Actions
  setSessionId: (id: string | null) => void;
  setStatus: (status: SessionStatus) => void;
  setProgress: (progress: number) => void;
  setError: (error: string | null) => void;
  uploadFile: (file: File) => Promise<string>;
  startPolling: (sessionId: string) => void;
  stopPolling: () => void;
  reset: () => void;
}

const initialState = {
  sessionId: null as string | null,
  status: 'idle' as SessionStatus,
  progress: 0,
  error: null as string | null,
  fileName: null as string | null,
  _pollTimer: null as ReturnType<typeof setInterval> | null,
};

/**
 * 全局会话状态管理
 * 管理文件上传、解析进度轮询
 */
export const useSessionStore = create<SessionState>((set, get) => ({
  ...initialState,

  setSessionId: (id) => set({ sessionId: id }),
  setStatus: (status) => set({ status }),
  setProgress: (progress) => set({ progress }),
  setError: (error) => set({ error }),

  /**
   * 上传文件到后端
   * 返回 session_id 供后续轮询
   */
  uploadFile: async (file: File) => {
    set({ status: 'uploading', error: null, fileName: file.name, progress: 0 });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/sessions', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const { session_id, status } = res.data.data;
      set({ sessionId: session_id, status: status || 'parsing', progress: 0.1 });
      return session_id;
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: { message?: string } } }; message?: string };
      const msg = e.response?.data?.detail?.message || e.message || '上传失败';
      set({ status: 'failed', error: msg });
      throw err;
    }
  },

  /**
   * 启动轮询，每秒查询解析进度
   * 当 status 变为 parsed 或 failed 时停止
   */
  startPolling: (sessionId: string) => {
    const { _pollTimer } = get();
    if (_pollTimer) clearInterval(_pollTimer);

    const timer = setInterval(async () => {
      try {
        const res = await api.get(`/sessions/${sessionId}/status`);
        const { status, progress, error } = res.data.data;

        set({ status, progress: progress ?? 0 });

        if (status === 'parsed' || status === 'failed') {
          clearInterval(timer);
          set({ _pollTimer: null });
          if (status === 'failed') {
            set({ error: error || '解析失败' });
          }
        }
      } catch {
        // 网络错误不停止轮询，等下次重试
      }
    }, 1000);

    set({ _pollTimer: timer });
  },

  /**
   * 停止轮询
   */
  stopPolling: () => {
    const { _pollTimer } = get();
    if (_pollTimer) {
      clearInterval(_pollTimer);
      set({ _pollTimer: null });
    }
  },

  reset: () => {
    const { _pollTimer } = get();
    if (_pollTimer) clearInterval(_pollTimer);
    set(initialState);
  },
}));
