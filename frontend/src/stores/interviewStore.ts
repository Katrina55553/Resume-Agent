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
  wsConnected: boolean;

  // Actions
  startInterview: (sessionId: string) => Promise<void>;
  sendAnswer: (content: string) => void;
  skipQuestion: () => void;
  rephraseQuestion: () => void;
  resumeInterview: (sessionId: string) => Promise<void>;
  _connectWs: (sessionId: string) => void;
  disconnect: () => void;
  reset: () => void;
}

/** 构建 WebSocket URL */
function getWsUrl(sessionId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws/interview/${sessionId}`;
}

/** 将后端 point_list 映射为 PointState[] */
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

let ws: WebSocket | null = null;

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
  wsConnected: false,

  startInterview: async (sessionId: string) => {
    set({ status: 'loading', error: null, sessionId });
    try {
      // 1. REST 调用创建面试状态
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

      // 2. 连接 WebSocket
      get()._connectWs(sessionId);
    } catch (err: any) {
      // 400 = 面试已存在，尝试 resume
      if (err.response?.status === 400) {
        await get().resumeInterview(sessionId);
        return;
      }
      const msg = err.response?.data?.detail?.message || err.message || '启动面试失败';
      set({ status: 'error', error: msg });
    }
  },

  resumeInterview: async (sessionId: string) => {
    set({ status: 'loading', error: null, sessionId });
    try {
      const res = await api.get(`/sessions/${sessionId}/interview/resume`);
      const data = res.data.data || res.data;

      // 最后一条 assistant 消息作为当前问题
      const messages: ChatMessage[] = data.messages || [];

      set({
        status: data.is_complete ? 'complete' : 'active',
        messages,
        pointStates: mapPointList(data.point_list, []),
        currentPointId: data.current_point_id,
        currentRound: data.current_round || 1,
        progress: data.progress || 0,
        isComplete: data.is_complete || false,
        report: data.report || null,
      });

      // 连接 WebSocket（未完成时）
      if (!data.is_complete) {
        get()._connectWs(sessionId);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail?.message || err.message || '恢复面试失败';
      set({ status: 'error', error: msg });
    }
  },

  _connectWs: (sessionId: string) => {
    // 关闭旧连接
    if (ws) {
      ws.close();
      ws = null;
    }

    const socket = new WebSocket(getWsUrl(sessionId));
    ws = socket;

    socket.onopen = () => {
      console.log('[WS] 面试连接已建立');
      set({ wsConnected: true });
      // 发送 start 消息获取当前问题
      socket.send(JSON.stringify({ type: 'start' }));
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const { pointStates } = get();

        switch (msg.type) {
          case 'question':
            // 收到新问题
            set({
              messages: [...get().messages, {
                role: 'assistant',
                content: msg.content,
                point_id: msg.point_id,
              }],
              currentPointId: msg.point_id || get().currentPointId,
              currentRound: msg.round || get().currentRound,
            });
            break;

          case 'status':
            // 状态更新（point_states、progress）
            set({
              pointStates: mergePointStates(pointStates, msg.point_states),
              progress: msg.progress ?? get().progress,
            });
            break;

          case 'complete':
            // 面试完成
            set({
              isComplete: true,
              status: 'complete',
              report: msg.report || null,
              progress: 1,
            });
            socket.close();
            break;

          case 'error':
            set({
              messages: [...get().messages, {
                role: 'assistant',
                content: `[系统] ${msg.error}`,
              }],
              error: msg.error,
            });
            break;
        }
      } catch {
        console.error('[WS] 消息解析失败:', event.data);
      }
    };

    socket.onclose = () => {
      console.log('[WS] 面试连接已关闭');
      set({ wsConnected: false });
      ws = null;
    };

    socket.onerror = () => {
      set({ wsConnected: false });
    };
  },

  sendAnswer: (content: string) => {
    const { sessionId, messages } = get();
    if (!sessionId || !ws || ws.readyState !== WebSocket.OPEN) return;

    // 先在 UI 显示用户消息
    set({ messages: [...messages, { role: 'user', content }] });

    // 通过 WebSocket 发送
    ws.send(JSON.stringify({ type: 'answer', content }));
  },

  skipQuestion: () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'skip' }));
  },

  rephraseQuestion: () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'rephrase' }));
  },

  disconnect: () => {
    if (ws) {
      ws.close();
      ws = null;
    }
    set({ wsConnected: false });
  },

  reset: () => {
    if (ws) {
      ws.close();
      ws = null;
    }
    set({
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
      wsConnected: false,
    });
  },
}));
