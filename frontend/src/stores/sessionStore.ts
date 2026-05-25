import { create } from 'zustand';

/** 会话状态类型 */
export type SessionStatus = 'idle' | 'uploading' | 'parsing' | 'diagnosing' | 'interviewing' | 'reporting' | 'done' | 'error';

interface SessionState {
  /** 当前会话 ID */
  sessionId: string | null;
  /** 当前会话状态 */
  status: SessionStatus;
  /** 进度百分比 0-100 */
  progress: number;

  // Actions
  setSessionId: (id: string | null) => void;
  setStatus: (status: SessionStatus) => void;
  setProgress: (progress: number) => void;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  status: 'idle' as SessionStatus,
  progress: 0,
};

/**
 * 全局会话状态管理
 * 使用 Zustand 管理当前会话的 ID、状态和进度
 */
export const useSessionStore = create<SessionState>((set) => ({
  ...initialState,

  setSessionId: (id) => set({ sessionId: id }),
  setStatus: (status) => set({ status }),
  setProgress: (progress) => set({ progress }),
  reset: () => set(initialState),
}));
