import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Markdown from 'react-markdown';
import { useInterviewStore, type ChatMessage } from '../stores/interviewStore';
import { useVoiceChat } from '../hooks/useVoiceChat';

const PRIORITY_COLORS: Record<string, string> = {
  high: 'bg-priority-high',
  medium: 'bg-priority-medium',
  low: 'bg-priority-low',
};

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  pending: { text: '待追问', color: 'text-ink-muted' },
  active: { text: '追问中', color: 'text-accent' },
  resolved: { text: '已完成', color: 'text-priority-low' },
  skipped: { text: '已跳过', color: 'text-ink-muted' },
};

/**
 * 步骤3：模拟面试页（WebSocket 实时通信）
 */
export default function InterviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const {
    messages, pointStates, currentPointId, currentRound,
    progress, isComplete, status, error, wsConnected, thinking,
    startInterview, sendAnswer, skipQuestion, endInterview, reset,
  } = useInterviewStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const prevMsgCountRef = useRef(0);
  const sessionIdRef = useRef<string | null>(null);

  const voice = useVoiceChat({
    onResult: (text) => {
      // 语音识别完成后追加到输入框，不直接发送；后续说话继续追加
      setInput((prev) => {
        const trimmed = prev.trimEnd();
        if (!trimmed) return text;
        return trimmed + ' ' + text;
      });
    },
  });

  // session_id 变化时重置 store（防止旧面试状态残留）
  useEffect(() => {
    if (id && sessionIdRef.current !== id) {
      sessionIdRef.current = id;
      reset();
    }
  }, [id, reset]);

  // 启动面试
  useEffect(() => {
    if (id && status === 'idle') {
      startInterview(id);
    }
  }, [id, status, startInterview]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 面试完成后跳转报告页
  useEffect(() => {
    if (isComplete) {
      const timer = setTimeout(() => navigate(`/session/${id}/report`), 2000);
      return () => clearTimeout(timer);
    }
  }, [isComplete, id, navigate]);

  // 语音模式下自动朗读 AI 新消息
  useEffect(() => {
    if (!voice.voiceEnabled) return;
    if (messages.length <= prevMsgCountRef.current) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.role === 'assistant') {
      voice.speak(lastMsg.content);
    }
    prevMsgCountRef.current = messages.length;
  }, [messages, voice]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || !wsConnected) return;
    setInput('');
    sendAnswer(text);
  }, [input, wsConnected, sendAnswer]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const handleSkip = useCallback(() => {
    if (!wsConnected) return;
    skipQuestion();
  }, [wsConnected, skipQuestion]);

  const handleEndInterview = useCallback(async () => {
    const ok = window.confirm('确定要结束面试吗？\n\n未回答的存疑点将被跳过，系统会根据已有回答生成评估报告。');
    if (!ok) return;
    await endInterview();
  }, [endInterview]);

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper bg-noise">
        <div className="text-center animate-fade-up relative z-10">
          <div className="w-12 h-12 border-[3px] border-accent-light border-t-accent rounded-full animate-spin mx-auto mb-5" />
          <p className="text-ink font-display text-lg">正在准备面试...</p>
          <p className="text-ink-muted text-sm mt-1">AI 面试官正在审阅你的简历</p>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper bg-noise p-6">
        <div className="paper-card rounded-2xl p-8 max-w-md text-center animate-scale-in relative z-10">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-priority-high-bg flex items-center justify-center">
            <span className="text-priority-high text-xl font-display">!</span>
          </div>
          <p className="text-ink font-display text-lg mb-2">面试启动失败</p>
          <p className="text-ink-light text-sm mb-5">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="px-5 py-2 bg-accent text-white text-sm rounded-lg hover:bg-accent-dark transition"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  const currentPoint = pointStates.find((p) => p.id === currentPointId);

  return (
    <div className="flex flex-col h-screen bg-paper bg-noise">
      {/* 顶部导航 */}
      <div className="bg-surface/80 backdrop-blur border-b border-border px-6 py-3 flex items-center justify-between shrink-0 relative z-10">
        <button
          onClick={() => navigate(`/session/${id}/diagnose`)}
          className="text-ink-light hover:text-ink text-sm transition flex items-center gap-1"
        >
          <span>←</span> 返回诊断
        </button>
        <div className="flex items-center gap-4">
          {/* 语音开关 */}
          {voice.isSupported ? (
            <button
              onClick={voice.toggleVoice}
              className={`px-3 py-1 text-xs rounded-full border transition ${
                voice.voiceEnabled
                  ? 'bg-accent-light border-accent text-accent-dark'
                  : 'border-border text-ink-muted hover:border-border-strong hover:text-ink-light'
              }`}
              title={voice.voiceEnabled ? '关闭语音模式' : '开启语音模式'}
            >
              🎙 {voice.voiceEnabled ? '语音模式' : '语音'}
            </button>
          ) : (
            <span className="text-xs text-ink-muted" title="语音功能需要通过 HTTPS 访问">
              🎙 语音不可用
            </span>
          )}
          {/* 连接状态指示器 */}
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              {wsConnected && (
                <span className="absolute inline-flex h-full w-full rounded-full bg-accent opacity-60 animate-ping" />
              )}
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  wsConnected ? 'bg-accent' : 'bg-priority-high'
                }`}
              />
            </span>
            <span className={`text-xs font-medium ${wsConnected ? 'text-accent' : 'text-priority-high'}`}>
              {wsConnected ? '已连接' : '已断开'}
            </span>
          </div>
          <div className="h-4 w-px bg-border" />
          <span className="text-xs text-ink-muted font-display">步骤 3/4 · 模拟面试</span>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* 左侧：对话区 */}
        <div className="flex-1 flex flex-col">
          {/* 进度条 */}
          <div className="px-6 pt-4 pb-2 shrink-0 relative z-10">
            <div className="flex items-center gap-3">
              <span className="text-xs text-ink-light font-medium">面试进度</span>
              <div className="flex-1 bg-border rounded-full h-1.5 overflow-hidden">
                <div
                  className="h-full bg-accent rounded-full transition-all duration-500"
                  style={{ width: `${Math.round(progress * 100)}%` }}
                />
              </div>
              <span className="text-xs text-ink-light font-medium tabular-nums">
                {Math.round(progress * 100)}%
              </span>
            </div>
          </div>

          {/* 消息列表 */}
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}
            {/* 面试官思考中 */}
            {thinking && (
              <div className="flex justify-start animate-fade-in">
                <div className="max-w-[75%]">
                  <div className="text-xs text-ink-muted mb-1">面试官</div>
                  <div className="paper-card rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-2">
                    <span className="text-sm text-ink-muted">思考中</span>
                    <span className="flex gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: '300ms' }} />
                    </span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* 输入区 */}
          {!isComplete && (
            <div className="border-t border-border bg-surface px-6 py-4 shrink-0 relative z-10">
              {currentPoint && (
                <div className="mb-3 flex items-center gap-2 text-xs text-ink-light">
                  <span className={`w-2 h-2 rounded-full ${PRIORITY_COLORS[currentPoint.priority]}`} />
                  <span>当前存疑点：{currentPoint.source_text.slice(0, 30)}...</span>
                  <span className="text-ink-muted">追问轮次 {currentRound}/3</span>
                </div>
              )}
              <div className="flex gap-3">
                <textarea
                  className="flex-1 border border-border rounded-xl px-4 py-3 text-sm resize-none outline-none transition focus:border-accent focus:ring-2 focus:ring-accent-light bg-paper text-ink placeholder:text-ink-muted"
                  rows={2}
                  placeholder={voice.voiceEnabled ? '点击麦克风说话，识别后显示在此处，可继续说话追加...' : '输入你的回答...'}
                  value={voice.voiceEnabled ? (input + voice.transcript) : input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={!wsConnected || thinking}
                />
                <div className="flex flex-col gap-2">
                  <div className="flex gap-2">
                    {voice.voiceEnabled && voice.isSupported && (
                      <button
                        onMouseDown={voice.startListening}
                        onMouseUp={voice.stopListening}
                        onTouchStart={voice.startListening}
                        onTouchEnd={voice.stopListening}
                        disabled={!wsConnected || voice.isSpeaking || thinking}
                        className={`px-4 py-2 text-white text-sm rounded-lg transition ${
                          voice.isListening
                            ? 'bg-priority-high animate-pulse'
                            : 'bg-accent hover:bg-accent-dark disabled:opacity-40'
                        }`}
                      >
                        {voice.isListening ? '录音中' : '🎤'}
                      </button>
                    )}
                    <button
                      onClick={handleSend}
                      disabled={!input.trim() || !wsConnected || thinking}
                      className="px-5 py-2 bg-accent text-white text-sm rounded-lg hover:bg-accent-dark disabled:opacity-40 disabled:cursor-not-allowed transition"
                    >
                      发送
                    </button>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={handleSkip}
                      disabled={!wsConnected || thinking}
                      className="px-2 py-1 text-xs text-ink-light hover:text-ink border border-border rounded transition disabled:opacity-40"
                    >
                      跳过
                    </button>
                    <button
                      onClick={handleEndInterview}
                      disabled={thinking}
                      className="px-2 py-1 text-xs text-priority-high hover:text-priority-high/80 border border-priority-high/30 rounded transition disabled:opacity-40"
                    >
                      结束面试
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 面试完成提示 */}
          {isComplete && (
            <div className="border-t border-border bg-accent-light px-6 py-4 text-center animate-fade-in relative z-10">
              <p className="text-accent-dark font-medium font-display">面试完成！正在生成评估报告...</p>
            </div>
          )}

          {/* 语音朗读中提示 */}
          {voice.isSpeaking && (
            <div className="border-t border-border bg-accent-light/50 px-6 py-2 flex items-center justify-center gap-2 relative z-10">
              <span className="w-2 h-2 bg-accent rounded-full animate-pulse" />
              <span className="text-xs text-accent-dark">AI 正在朗读...</span>
              <button onClick={voice.stopSpeaking} className="text-xs text-accent underline ml-2">
                停止
              </button>
            </div>
          )}
        </div>

        {/* 右侧：状态面板 */}
        <div className="w-72 border-l border-border bg-surface p-5 overflow-y-auto shrink-0 hidden lg:block relative z-10">
          <h3 className="text-sm font-display font-semibold text-ink mb-1">面试状态</h3>
          <div className="decor-line mb-4" />

          {currentPoint && (
            <div className="mb-5 p-3 bg-accent-light rounded-lg border border-accent/20">
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-2 h-2 rounded-full ${PRIORITY_COLORS[currentPoint.priority]}`} />
                <span className="text-xs font-medium text-accent-dark">当前存疑点</span>
              </div>
              <p className="text-xs text-ink-light line-clamp-3">{currentPoint.source_text}</p>
              <p className="text-xs text-ink-muted mt-1">追问轮次 {currentRound}/3</p>
            </div>
          )}

          <div className="space-y-1.5">
            {pointStates.map((point) => {
              const label = STATUS_LABELS[point.status] || STATUS_LABELS.pending;
              return (
                <div
                  key={point.id}
                  className={`flex items-center gap-2 p-2 rounded text-xs transition ${
                    point.id === currentPointId
                      ? 'bg-accent-light/60 border border-accent/20'
                      : 'hover:bg-paper-dark'
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full ${PRIORITY_COLORS[point.priority]}`} />
                  <span className="flex-1 truncate text-ink-light">{point.source_text.slice(0, 20)}</span>
                  <span className={label.color}>{label.text}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/** 消息气泡组件 */
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-up`}>
      <div className={`max-w-[75%] ${isUser ? 'order-2' : 'order-1'}`}>
        <div className={`text-xs text-ink-muted mb-1 ${isUser ? 'text-right' : ''}`}>
          {isUser ? '你' : '面试官'}
        </div>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? 'bg-accent text-white rounded-br-md whitespace-pre-wrap shadow-sm'
              : 'paper-card rounded-bl-md prose prose-sm max-w-none text-ink'
          }`}
        >
          {isUser ? (
            message.content
          ) : (
            <Markdown>{message.content}</Markdown>
          )}
        </div>
      </div>
    </div>
  );
}
