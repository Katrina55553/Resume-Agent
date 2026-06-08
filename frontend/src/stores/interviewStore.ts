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
  endInterview: () => Promise<void>;
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
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let messageQueue: string[] = [];  // 断连期间缓存的消息

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
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    const MAX_RETRIES = 5;
    let retryCount = 0;

    const connect = () => {
      const socket = new WebSocket(getWsUrl(sessionId));
      ws = socket;

      socket.onopen = () => {
        console.log('[WS] 面试连接已建立');
        retryCount = 0;
        set({ wsConnected: true, error: null });
        socket.send(JSON.stringify({ type: 'start' }));

        // 发送断连期间缓存的消息
        while (messageQueue.length > 0) {
          const msg = messageQueue.shift()!;
          console.log('[WS] 发送缓存消息');
          socket.send(msg);
        }
      };

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const { pointStates } = get();

          switch (msg.type) {
            case 'question':
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
              set({
                pointStates: mergePointStates(pointStates, msg.point_states),
                progress: msg.progress ?? get().progress,
              });
              break;

            case 'complete':
              set({
                isComplete: true,
                status: 'complete',
                report: msg.report || null,
                progress: 1,
              });
              socket.close(1000);
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

      socket.onclose = (event) => {
        console.log('[WS] 连接关闭', event.code);
        set({ wsConnected: false });
        ws = null;

        // 非正常关闭且面试未完成时自动重连
        const { isComplete } = get();
        if (!isComplete && event.code !== 1000) {
          if (retryCount < MAX_RETRIES) {
            const delay = Math.min(1000 * Math.pow(2, retryCount), 16000);
            retryCount++;
            console.log(`[WS] ${delay / 1000}s 后重连 (${retryCount}/${MAX_RETRIES})`);
            reconnectTimer = setTimeout(connect, delay);
          } else {
            set({ error: '连接断开，请刷新页面重试' });
          }
        }
      };

      socket.onerror = () => {
        set({ wsConnected: false });
      };
    };

    connect();
  },

  sendAnswer: (content: string) => {
    const { sessionId, messages } = get();
    if (!sessionId) return;

    // 先在 UI 显示用户消息
    set({ messages: [...messages, { role: 'user', content }] });

    const payload = JSON.stringify({ type: 'answer', content });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
    } else {
      // 断连时缓存消息
      console.log('[WS] 连接断开，消息已缓存');
      messageQueue.push(payload);
    }
  },

  skipQuestion: () => {
    const payload = JSON.stringify({ type: 'skip' });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
    } else {
      messageQueue.push(payload);
    }
  },

  rephraseQuestion: () => {
    const payload = JSON.stringify({ type: 'rephrase' });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
    } else {
      messageQueue.push(payload);
    }
  },

  endInterview: async () => {
    const { sessionId } = get();
    if (!sessionId) return;

    // 关闭 WebSocket
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws) {
      ws.close(1000);
      ws = null;
    }

    try {
      const res = await api.post(`/sessions/${sessionId}/interview/end`);
      const data = res.data.data || res.data;
      // 无论 report 是否为空，都标记完成并跳转
      set({
        isComplete: true,
        status: 'complete',
        report: data.report || null,
        progress: 1,
      });
    } catch (err: any) {
      // 即使 API 失败，也标记完成并跳转（避免卡死）
      console.error('[结束面试] API 错误:', err);
      set({
        isComplete: true,
        status: 'complete',
        report: null,
        progress: 1,
      });
    }
  },

  disconnect: () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    messageQueue = [];
    if (ws) {
      ws.close(1000);  // 正常关闭，不触发重连
      ws = null;
    }
    set({ wsConnected: false });
  },

  reset: () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    messageQueue = [];
    if (ws) {
      ws.close(1000);
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
