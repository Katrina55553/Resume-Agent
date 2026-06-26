import { create } from 'zustand';
import api from '../utils/api';

// 错误码定义（与后端 app/core/errors.py 保持一致）
const ERROR_CODES = {
  // 会话相关
  SESSION_NOT_FOUND: '1100',
  INTERVIEW_NOT_STARTED: '1400',
  INTERVIEW_ALREADY_COMPLETED: '1401',
  INTERVIEW_NO_POINTS: '1402',
  // WebSocket 相关
  WS_INVALID_MESSAGE: '1600',
  WS_EMPTY_ANSWER: '1601',
  // LLM 相关
  LLM_UNAVAILABLE: '1500',
  LLM_TIMEOUT: '1501',
} as const;

// 错误码对应的友好提示
const ERROR_MESSAGES: Record<string, string> = {
  [ERROR_CODES.SESSION_NOT_FOUND]: '会话不存在，请重新上传简历',
  [ERROR_CODES.INTERVIEW_NOT_STARTED]: '面试未开始，请先启动面试',
  [ERROR_CODES.INTERVIEW_ALREADY_COMPLETED]: '面试已结束',
  [ERROR_CODES.INTERVIEW_NO_POINTS]: '没有存疑点，无法开始面试',
  [ERROR_CODES.WS_INVALID_MESSAGE]: '消息格式无效',
  [ERROR_CODES.WS_EMPTY_ANSWER]: '回答内容不能为空',
  [ERROR_CODES.LLM_UNAVAILABLE]: 'AI 服务暂时不可用，请稍后重试',
  [ERROR_CODES.LLM_TIMEOUT]: 'AI 响应超时，请稍后重试',
};

/** 根据错误码获取友好提示 */
function getErrorMessage(code: string | undefined, fallback: string): string {
  if (code && ERROR_MESSAGES[code]) {
    return ERROR_MESSAGES[code];
  }
  return fallback;
}

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
  thinking: boolean;
  selectedPointIds: string[];

  // Actions
  setSelectedPointIds: (ids: string[]) => void;
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
function mapPointList(pointList: Record<string, unknown>[] | undefined, fallback: PointState[]): PointState[] {
  if (pointList && Array.isArray(pointList)) {
    return pointList.map((p) => ({
      id: p.id as string,
      source_text: (p.source_text as string) || '',
      priority: (p.priority as PointState['priority']) || 'low',
      status: (p.status as PointState['status']) || 'pending',
    }));
  }
  return fallback;
}

/** 将 point_states 字典合并到现有数组 */
function mergePointStates(existing: PointState[], states: Record<string, string> | undefined): PointState[] {
  if (!states) return existing;
  return existing.map(p => ({ ...p, status: (states[p.id] as PointState['status']) || p.status }));
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
  thinking: false,
  selectedPointIds: [],

  setSelectedPointIds: (ids: string[]) => set({ selectedPointIds: ids }),

  startInterview: async (sessionId: string) => {
    // 清除所有旧状态，避免上一次面试的残留数据闪现
    set({
      status: 'loading',
      error: null,
      sessionId,
      messages: [],
      pointStates: [],
      currentPointId: null,
      currentRound: 1,
      progress: 0,
      isComplete: false,
      report: null,
      wsConnected: false,
    });
    try {
      // 1. REST 调用创建面试状态，传递选中的存疑点 ID
      const { selectedPointIds } = get();
      console.log('[startInterview] sending selected_point_ids:', selectedPointIds);
      const res = await api.post(`/sessions/${sessionId}/interview/start`, {
        selected_point_ids: selectedPointIds,
      });
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
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: { message?: string } } }; message?: string };
      // 400 = 面试已存在，尝试 resume
      if (e.response?.status === 400) {
        await get().resumeInterview(sessionId);
        return;
      }
      const msg = e.response?.data?.detail?.message || e.message || '启动面试失败';
      set({ status: 'error', error: msg });
    }
  },

  resumeInterview: async (sessionId: string) => {
    // 清除旧状态，避免上一次面试的残留数据闪现
    set({
      status: 'loading',
      error: null,
      sessionId,
      messages: [],
      isComplete: false,
      report: null,
    });
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
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: { message?: string } } }; message?: string };
      const msg = e.response?.data?.detail?.message || e.message || '恢复面试失败';
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
      let streamingContent = '';

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
            case 'question_start':
              // 流式开始：清空流式内容，退出思考状态
              streamingContent = '';
              set({ thinking: false });
              break;

            case 'chunk':
              // 流式 chunk：累积内容
              streamingContent += msg.content || '';
              break;

            case 'question':
              {
                const msgs = [...get().messages];
                // 检查最后一条是否是 assistant 且内容为空（流式占位）
                if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant' && msgs[msgs.length - 1].content === '') {
                  // 替换占位消息
                  msgs[msgs.length - 1] = {
                    ...msgs[msgs.length - 1],
                    content: msg.content,
                    point_id: msg.point_id,
                  };
                } else if (streamingContent && msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
                  // 有流式内容且最后一条是 assistant，替换（避免重复）
                  msgs[msgs.length - 1] = {
                    ...msgs[msgs.length - 1],
                    content: msg.content,
                    point_id: msg.point_id,
                  };
                } else {
                  // 追加新 assistant 消息（用户回答后最后一条是 user，必须追加）
                  msgs.push({
                    role: 'assistant',
                    content: msg.content,
                    point_id: msg.point_id,
                  });
                }
                set({
                  messages: msgs,
                  currentPointId: msg.point_id || get().currentPointId,
                  currentRound: msg.round || get().currentRound,
                  thinking: false,
                });
                streamingContent = '';  // 重置
              }
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
                thinking: false,
              });
              socket.close(1000);
              break;

            case 'error': {
              const errorMsg = getErrorMessage(msg.code, msg.error || '未知错误');
              set({
                messages: [...get().messages, {
                  role: 'assistant',
                  content: `[系统] ${errorMsg}`,
                }],
                error: errorMsg,
                thinking: false,
              });
              break;
            }
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

    // 先在 UI 显示用户消息，并标记"思考中"
    set({ messages: [...messages, { role: 'user', content }], thinking: true });

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
    set({ thinking: true });
    const payload = JSON.stringify({ type: 'skip' });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
    } else {
      messageQueue.push(payload);
    }
  },

  rephraseQuestion: () => {
    set({ thinking: true });
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
      const res = await api.post(`/sessions/${sessionId}/interview/end`, {}, { timeout: 120000 });
      const data = res.data.data || res.data;
      set({
        isComplete: true,
        status: 'complete',
        report: data.report || null,
        progress: 1,
      });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: { message?: string } } }; message?: string };
      const msg = e.response?.data?.detail?.message || e.message || '结束面试失败';
      console.error('[结束面试] API 错误:', msg);
      set({ error: msg, status: 'error' });
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
      // 保留 selectedPointIds：它是用户在 DiagnosePage 勾选的"输入参数"，
      // 不是面试运行态。reset 在 InterviewPage 挂载时会被调用，
      // 若清空会导致 startInterview 读到空数组发给后端。
      wsConnected: false,
      thinking: false,
    });
  },
}));
