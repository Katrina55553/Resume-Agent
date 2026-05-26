import { create } from 'zustand';
import api from '../utils/api';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  point_id?: string;
}

export interface PointState {
  id: string;
  source_text: string;
  priority: 'high' | 'medium' | 'low';
  status: 'pending' | 'active' | 'resolved' | 'skipped';
}

export interface InterviewReport {
  overall_score: number;
  total_points: number;
  resolved_points: number;
  skipped_points: number;
  point_feedbacks: Array<{
    point_id: string;
    source_text: string;
    score: number;
    status: string;
    feedback: string;
  }>;
  suggestions: string[];
  summary: string;
}

interface InterviewState {
  sessionId: string | null;
  messages: ChatMessage[];
  pointStates: PointState[];
  currentPointId: string | null;
  currentRound: number;
  progress: number;
  isComplete: boolean;
  report: InterviewReport | null;
  status: 'idle' | 'loading' | 'active' | 'complete' | 'error';
  error: string | null;

  // Actions
  startInterview: (sessionId: string) => Promise<void>;
  sendAnswer: (content: string) => Promise<void>;
  skipQuestion: () => Promise<void>;
  rephraseQuestion: () => Promise<void>;
  resumeInterview: (sessionId: string) => Promise<void>;
  reset: () => void;
}

/** 将后端返回的 point_list 映射为 PointState[] */
function mapPointList(pointList: any[] | undefined, fallback: PointState[]): PointState[] {
  if (pointList && Array.isArray(pointList)) {
    return pointList.map((p: any) => ({
      id: p.id,
      source_text: p.source_text || '',
      priority: p.priority || 'low',
      status: p.status || 'pending',
    }));
  }
  return fallback;
}

/** 将 point_states 字典合并到现有数组 */
function mergePointStates(existing: PointState[], states: Record<string, string> | undefined): PointState[] {
  if (!states) return existing;
  return existing.map(p => ({ ...p, status: (states[p.id] as any) || p.status }));
}

export const useInterviewStore = create<InterviewState>((set, get) => ({
  sessionId: null,
  messages: [],
  pointStates: [],
  currentPointId: null,
  currentRound: 1,
  progress: 0,
  isComplete: false,
  report: null,
  status: 'idle',
  error: null,

  startInterview: async (sessionId: string) => {
    set({ status: 'loading', error: null, sessionId });
    try {
      const res = await api.post(`/sessions/${sessionId}/interview/start`);
      const data = res.data.data || res.data;

      set({
        status: 'active',
        messages: [{ role: 'assistant', content: data.first_question }],
        pointStates: mapPointList(data.point_list, []),
        currentPointId: data.point_id,
        currentRound: 1,
        progress: 0,
      });
    } catch (err: any) {
      // 如果是 400（面试已存在），尝试 resume
      if (err.response?.status === 400) {
        try {
          const resumeRes = await api.get(`/sessions/${sessionId}/interview/resume`);
          const rData = resumeRes.data.data || resumeRes.data;
          set({
            status: rData.is_complete ? 'complete' : 'active',
            messages: rData.messages || [],
            pointStates: mapPointList(rData.point_list, []),
            currentPointId: rData.current_point_id,
            currentRound: rData.current_round || 1,
            progress: rData.progress || 0,
            isComplete: rData.is_complete || false,
            report: rData.report || null,
          });
          return;
        } catch {
          // resume 也失败了，走正常错误处理
        }
      }
      const msg = err.response?.data?.detail?.message || err.message || '启动面试失败';
      set({ status: 'error', error: msg });
    }
  },

  sendAnswer: async (content: string) => {
    const { sessionId, messages, pointStates } = get();
    if (!sessionId) return;

    // 先添加用户消息到 UI
    set({
      messages: [...messages, { role: 'user', content }],
    });

    try {
      const res = await api.post(`/sessions/${sessionId}/interview/respond`, {
        content,
      });
      const data = res.data.data || res.data;

      if (data.decision === 'report') {
        set({
          isComplete: true,
          status: 'complete',
          report: data.report,
          progress: 1,
        });
      } else {
        const updatedStates = mergePointStates(pointStates, data.point_states);
        set({
          messages: [...get().messages, { role: 'assistant', content: data.question }],
          pointStates: updatedStates,
          currentPointId: data.point_id,
          currentRound: data.round || get().currentRound,
          progress: data.progress || get().progress,
        });
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail?.message || err.message || '提交回答失败';
      // 不中断面试，在聊天中显示错误提示
      set({
        messages: [...get().messages, { role: 'assistant', content: `[系统] 回答提交失败：${msg}，请重试。` }],
        error: msg,
      });
    }
  },

  skipQuestion: async () => {
    const { sessionId, messages, pointStates } = get();
    if (!sessionId) return;

    try {
      const res = await api.post(`/sessions/${sessionId}/interview/skip`);
      const data = res.data.data || res.data;

      if (data.decision === 'report') {
        set({
          isComplete: true,
          status: 'complete',
          report: data.report,
          progress: 1,
        });
      } else {
        const updatedStates = mergePointStates(pointStates, data.point_states);
        set({
          messages: [...messages, { role: 'assistant', content: `[跳过] ${data.question}` }],
          pointStates: updatedStates,
          currentPointId: data.point_id,
          currentRound: 1,
          progress: data.progress || get().progress,
        });
      }
    } catch (err: any) {
      set({ error: err.message || '跳过失败' });
    }
  },

  rephraseQuestion: async () => {
    const { sessionId, messages } = get();
    if (!sessionId) return;

    try {
      const res = await api.post(`/sessions/${sessionId}/interview/rephrase`);
      const data = res.data.data || res.data;

      set({
        messages: [...messages, { role: 'assistant', content: data.question }],
      });
    } catch (err: any) {
      set({ error: err.message || '换问法失败' });
    }
  },

  resumeInterview: async (sessionId: string) => {
    set({ status: 'loading', error: null, sessionId });
    try {
      const res = await api.get(`/sessions/${sessionId}/interview/resume`);
      const data = res.data.data || res.data;

      set({
        status: data.is_complete ? 'complete' : 'active',
        messages: data.messages || [],
        pointStates: mapPointList(data.point_list, []),
        currentPointId: data.current_point_id,
        currentRound: data.current_round || 1,
        progress: data.progress || 0,
        isComplete: data.is_complete || false,
        report: data.report || null,
      });
    } catch (err: any) {
      set({ status: 'error', error: err.message || '恢复面试失败' });
    }
  },

  reset: () => set({
    sessionId: null,
    messages: [],
    pointStates: [],
    currentPointId: null,
    currentRound: 1,
    progress: 0,
    isComplete: false,
    report: null,
    status: 'idle',
    error: null,
  }),
}));
