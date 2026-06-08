import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Markdown from 'react-markdown';
import { useInterviewStore, type ChatMessage } from '../stores/interviewStore';

const PRIORITY_COLORS: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-yellow-500',
  low: 'bg-green-500',
};

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  pending: { text: '待追问', color: 'text-gray-400' },
  active: { text: '追问中', color: 'text-blue-600' },
  resolved: { text: '已完成', color: 'text-green-600' },
  skipped: { text: '已跳过', color: 'text-gray-400' },
};

/**
 * 步骤3：模拟面试页（WebSocket 实时通信）
 */
export default function InterviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const {
    messages, pointStates, currentPointId, currentRound,
    progress, isComplete, report, status, error, wsConnected,
    startInterview, sendAnswer, skipQuestion, endInterview,
  } = useInterviewStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

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

  // 面试完成后跳转
  useEffect(() => {
    if (isComplete && report) {
      const timer = setTimeout(() => navigate(`/session/${id}/report`), 2000);
      return () => clearTimeout(timer);
    }
  }, [isComplete, report, id, navigate]);

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
    if (!confirm('确定要结束面试吗？未回答的存疑点将被跳过。')) return;
    await endInterview();
  }, [endInterview]);

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500">正在准备面试...</p>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
          <button onClick={() => navigate('/')} className="text-blue-500 underline">返回首页</button>
        </div>
      </div>
    );
  }

  const currentPoint = pointStates.find((p) => p.id === currentPointId);

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 顶部导航 */}
      <div className="bg-white border-b px-6 py-3 flex items-center justify-between shrink-0">
        <button onClick={() => navigate(`/session/${id}/diagnose`)} className="text-gray-500 hover:text-gray-700">
          ← 返回诊断
        </button>
        <div className="flex items-center gap-3">
          {/* WebSocket 连接状态 */}
          <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-400'}`}
            title={wsConnected ? '实时连接中' : '连接断开'} />
          <span className="text-sm text-gray-400">步骤 3/4 · 模拟面试</span>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* 左侧：对话区 */}
        <div className="flex-1 flex flex-col">
          {/* 进度条 */}
          <div className="px-6 pt-4 pb-2 shrink-0">
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500">面试进度</span>
              <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${Math.round(progress * 100)}%` }} />
              </div>
              <span className="text-xs text-gray-500">{Math.round(progress * 100)}%</span>
            </div>
          </div>

          {/* 消息列表 */}
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {messages.map((msg, i) => (
              <MessageBubble key={i} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* 输入区 */}
          {!isComplete && (
            <div className="border-t bg-white px-6 py-4 shrink-0">
              {currentPoint && (
                <div className="mb-3 flex items-center gap-2 text-xs text-gray-500">
                  <span className={`w-2 h-2 rounded-full ${PRIORITY_COLORS[currentPoint.priority]}`} />
                  当前存疑点：{currentPoint.source_text.slice(0, 30)}...
                  <span className="text-gray-400">追问轮次 {currentRound}/3</span>
                </div>
              )}
              <div className="flex gap-3">
                <textarea
                  className="flex-1 border rounded-xl px-4 py-3 text-sm resize-none outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
                  rows={2}
                  placeholder="输入你的回答..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={!wsConnected}
                />
                <div className="flex flex-col gap-2">
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || !wsConnected}
                    className="px-5 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-40 transition"
                  >
                    发送
                  </button>
                  <div className="flex gap-1">
                    <button
                      onClick={handleSkip}
                      disabled={!wsConnected}
                      className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700 border rounded"
                    >
                      跳过
                    </button>
                    <button
                      onClick={handleEndInterview}
                      className="px-2 py-1 text-xs text-red-500 hover:text-red-700 border border-red-300 rounded"
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
            <div className="border-t bg-green-50 px-6 py-4 text-center">
              <p className="text-green-700 font-medium">面试完成！正在生成评估报告...</p>
            </div>
          )}
        </div>

        {/* 右侧：状态面板 */}
        <div className="w-72 border-l bg-white p-5 overflow-y-auto shrink-0 hidden lg:block">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">面试状态</h3>

          {currentPoint && (
            <div className="mb-5 p-3 bg-blue-50 rounded-lg border border-blue-100">
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-2 h-2 rounded-full ${PRIORITY_COLORS[currentPoint.priority]}`} />
                <span className="text-xs font-medium text-blue-700">当前存疑点</span>
              </div>
              <p className="text-xs text-gray-600 line-clamp-3">{currentPoint.source_text}</p>
              <p className="text-xs text-gray-400 mt-1">追问轮次 {currentRound}/3</p>
            </div>
          )}

          <div className="space-y-2">
            {pointStates.map((point) => {
              const label = STATUS_LABELS[point.status] || STATUS_LABELS.pending;
              return (
                <div
                  key={point.id}
                  className={`flex items-center gap-2 p-2 rounded text-xs ${
                    point.id === currentPointId ? 'bg-blue-50' : ''
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full ${PRIORITY_COLORS[point.priority]}`} />
                  <span className="flex-1 truncate text-gray-600">{point.source_text.slice(0, 20)}</span>
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
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[75%] ${isUser ? 'order-2' : 'order-1'}`}>
        <div className={`text-xs text-gray-400 mb-1 ${isUser ? 'text-right' : ''}`}>
          {isUser ? '你' : '面试官'}
        </div>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? 'bg-blue-600 text-white rounded-br-md whitespace-pre-wrap'
              : 'bg-white border text-gray-700 rounded-bl-md shadow-sm prose prose-sm max-w-none'
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
