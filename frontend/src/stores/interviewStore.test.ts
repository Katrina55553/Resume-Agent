/**
 * interviewStore 单元测试
 *
 * 重点覆盖：
 * 1. WebSocket 消息处理的三分支逻辑（修复的关键 bug）
 * 2. thinking 状态切换
 * 3. reset 清理旧状态
 * 4. startInterview/resumeInterview 清除残留数据
 * 5. sendAnswer/skipQuestion/rephraseQuestion 缓存机制
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../utils/api'
import { useInterviewStore } from './interviewStore'

// mock axios
vi.mock('../utils/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

const mockApi = api as unknown as { post: ReturnType<typeof vi.fn>; get: ReturnType<typeof vi.fn> }

/** 拿到 MockWebSocket 类（在 setup.ts 中注入） */
// MockWebSocket 在 setup.ts 中注入到 globalThis，测试通过 globalThis.WebSocket 访问

/** 模拟 WS 消息推送到 onmessage */
function emitWsMessage(socket: WebSocket, msg: unknown) {
  const handler = (socket as unknown as { onmessage: ((ev: MessageEvent) => void) | null }).onmessage
  handler?.(new MessageEvent('message', { data: JSON.stringify(msg) }))
}

/** 等待 WS 连接建立（onopen 异步触发） */
async function waitForOpen() {
  await new Promise(r => setTimeout(r, 10))
}

describe('interviewStore', () => {
  beforeEach(() => {
    useInterviewStore.getState().reset()
    mockApi.post.mockReset()
    mockApi.get.mockReset()
  })

  afterEach(() => {
    useInterviewStore.getState().disconnect()
  })

  describe('初始状态', () => {
    it('应有正确的初始状态', () => {
      const s = useInterviewStore.getState()
      expect(s.sessionId).toBeNull()
      expect(s.messages).toEqual([])
      expect(s.pointStates).toEqual([])
      expect(s.isComplete).toBe(false)
      expect(s.report).toBeNull()
      expect(s.status).toBe('idle')
      expect(s.thinking).toBe(false)
      expect(s.wsConnected).toBe(false)
    })
  })

  describe('setSelectedPointIds', () => {
    it('设置选中的存疑点 ID', () => {
      useInterviewStore.getState().setSelectedPointIds(['p1', 'p2'])
      expect(useInterviewStore.getState().selectedPointIds).toEqual(['p1', 'p2'])
    })
  })

  describe('reset', () => {
    it('清除运行态，但保留 selectedPointIds（输入参数）', () => {
      useInterviewStore.setState({
        sessionId: 'old',
        messages: [{ role: 'assistant', content: 'old' }],
        isComplete: true,
        report: { overall_score: 80 } as never,
        status: 'complete',
        thinking: true,
        selectedPointIds: ['p1', 'p2'],
      })
      useInterviewStore.getState().reset()
      const s = useInterviewStore.getState()
      expect(s.sessionId).toBeNull()
      expect(s.messages).toEqual([])
      expect(s.isComplete).toBe(false)
      expect(s.report).toBeNull()
      expect(s.status).toBe('idle')
      expect(s.thinking).toBe(false)
      // selectedPointIds 是用户在 DiagnosePage 勾选的"输入参数"，
      // reset 时必须保留，否则 InterviewPage 挂载触发 reset 后，
      // startInterview 会读到空数组发给后端。
      expect(s.selectedPointIds).toEqual(['p1', 'p2'])
    })
  })

  describe('startInterview', () => {
    it('成功启动后设置消息、存疑点、连接 WS', async () => {
      mockApi.post.mockResolvedValueOnce({
        data: {
          data: {
            first_question: '请介绍你的项目',
            point_list: [
              { id: 'p1', source_text: '项目1', priority: 'high', status: 'active' },
            ],
            point_id: 'p1',
          },
        },
      })

      await useInterviewStore.getState().startInterview('sess-1')

      const s = useInterviewStore.getState()
      expect(s.status).toBe('active')
      expect(s.sessionId).toBe('sess-1')
      expect(s.messages).toHaveLength(1)
      expect(s.messages[0]).toEqual({
        role: 'assistant',
        content: '请介绍你的项目',
      })
      expect(s.pointStates).toHaveLength(1)
      expect(s.pointStates[0].id).toBe('p1')
      expect(s.currentPointId).toBe('p1')
    })

    it('启动前清除旧状态（不闪现上次面试记录）', async () => {
      // 模拟上次面试残留
      useInterviewStore.setState({
        sessionId: 'old',
        messages: [{ role: 'assistant', content: '旧问题' }],
        isComplete: true,
        report: { overall_score: 50 } as never,
      })

      mockApi.post.mockResolvedValueOnce({
        data: {
          data: { first_question: '新问题', point_list: [], point_id: 'p1' },
        },
      })

      await useInterviewStore.getState().startInterview('new')

      const s = useInterviewStore.getState()
      expect(s.sessionId).toBe('new')
      // 旧消息应被清除
      expect(s.messages).toEqual([{ role: 'assistant', content: '新问题' }])
      expect(s.isComplete).toBe(false)
      expect(s.report).toBeNull()
    })

    it('400 错误时降级到 resumeInterview', async () => {
      const err = new Error('conflict')
      ;(err as { response?: { status?: number } }).response = { status: 400 }
      mockApi.post.mockRejectedValueOnce(err)
      mockApi.get.mockResolvedValueOnce({
        data: {
          data: {
            messages: [{ role: 'assistant', content: '已存在问题' }],
            point_list: [],
            is_complete: false,
          },
        },
      })

      await useInterviewStore.getState().startInterview('sess-1')

      const s = useInterviewStore.getState()
      expect(s.status).toBe('active')
      expect(s.messages).toEqual([{ role: 'assistant', content: '已存在问题' }])
      // resume 被调用
      expect(mockApi.get).toHaveBeenCalledWith('/sessions/sess-1/interview/resume')
    })

    it('其他错误时设置 error 状态', async () => {
      const err = new Error('boom')
      ;(err as { response?: { status?: number; data?: { detail?: { message?: string } } } }).response = {
        status: 500,
        data: { detail: { message: '服务器错误' } },
      }
      mockApi.post.mockRejectedValueOnce(err)

      await useInterviewStore.getState().startInterview('sess-1')

      const s = useInterviewStore.getState()
      expect(s.status).toBe('error')
      expect(s.error).toBe('服务器错误')
    })

    it('错误无 message 时使用默认文案', async () => {
      mockApi.post.mockRejectedValueOnce(new Error('network'))
      await useInterviewStore.getState().startInterview('sess-1')
      expect(useInterviewStore.getState().error).toBe('network')
    })
  })

  describe('resumeInterview', () => {
    it('恢复未完成的面试', async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          data: {
            messages: [{ role: 'assistant', content: 'Q1' }],
            point_list: [{ id: 'p1', source_text: 'x', priority: 'low', status: 'active' }],
            current_point_id: 'p1',
            current_round: 2,
            progress: 0.3,
            is_complete: false,
          },
        },
      })

      await useInterviewStore.getState().resumeInterview('sess-1')

      const s = useInterviewStore.getState()
      expect(s.status).toBe('active')
      expect(s.messages).toHaveLength(1)
      expect(s.currentRound).toBe(2)
      expect(s.progress).toBe(0.3)
      expect(s.isComplete).toBe(false)
    })

    it('恢复已完成的面试时设置 complete 状态', async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          data: {
            messages: [],
            point_list: [],
            is_complete: true,
            report: { overall_score: 90 },
          },
        },
      })

      await useInterviewStore.getState().resumeInterview('sess-1')

      const s = useInterviewStore.getState()
      expect(s.status).toBe('complete')
      expect(s.isComplete).toBe(true)
      expect(s.report).toEqual({ overall_score: 90 })
    })

    it('恢复前清除旧状态', async () => {
      useInterviewStore.setState({
        sessionId: 'old',
        messages: [{ role: 'assistant', content: '旧' }],
        isComplete: true,
        report: { overall_score: 50 } as never,
      })

      mockApi.get.mockResolvedValueOnce({
        data: {
          data: {
            messages: [{ role: 'assistant', content: '新' }],
            is_complete: false,
          },
        },
      })

      await useInterviewStore.getState().resumeInterview('new')

      const s = useInterviewStore.getState()
      expect(s.sessionId).toBe('new')
      expect(s.messages).toEqual([{ role: 'assistant', content: '新' }])
      expect(s.isComplete).toBe(false)
      expect(s.report).toBeNull()
    })

    it('恢复失败时设置 error', async () => {
      const err = new Error('not found')
      ;(err as { response?: { data?: { detail?: { message?: string } } } }).response = {
        data: { detail: { message: '会话不存在' } },
      }
      mockApi.get.mockRejectedValueOnce(err)

      await useInterviewStore.getState().resumeInterview('sess-1')

      expect(useInterviewStore.getState().status).toBe('error')
      expect(useInterviewStore.getState().error).toBe('会话不存在')
    })
  })

  describe('sendAnswer', () => {
    it('追加用户消息并设置 thinking', async () => {
      // 先建立 WS 连接
      mockApi.post.mockResolvedValueOnce({
        data: { data: { first_question: 'Q1', point_list: [], point_id: 'p1' } },
      })
      await useInterviewStore.getState().startInterview('sess-1')
      await waitForOpen()

      // 清空消息，仅测试 sendAnswer
      useInterviewStore.setState({ messages: [] })

      useInterviewStore.getState().sendAnswer('我的回答')

      const s = useInterviewStore.getState()
      expect(s.messages).toHaveLength(1)
      expect(s.messages[0]).toEqual({ role: 'user', content: '我的回答' })
      expect(s.thinking).toBe(true)
    })

    it('无 sessionId 时不执行', () => {
      useInterviewStore.getState().sendAnswer('test')
      expect(useInterviewStore.getState().messages).toEqual([])
    })

    it('WS 未连接时消息进入队列', async () => {
      useInterviewStore.setState({ sessionId: 'sess-1' })
      // 不调用 startInterview，WS 为 null
      useInterviewStore.getState().sendAnswer('queued')
      // 不抛异常即视为通过
      expect(useInterviewStore.getState().messages).toHaveLength(1)
      expect(useInterviewStore.getState().thinking).toBe(true)
    })
  })

  describe('skipQuestion / rephraseQuestion', () => {
    it('skipQuestion 设置 thinking', () => {
      useInterviewStore.getState().skipQuestion()
      expect(useInterviewStore.getState().thinking).toBe(true)
    })

    it('rephraseQuestion 设置 thinking', () => {
      useInterviewStore.getState().rephraseQuestion()
      expect(useInterviewStore.getState().thinking).toBe(true)
    })
  })

  describe('WebSocket 消息处理（关键三分支逻辑）', () => {
    /** 建立连接并返回 socket 实例 */
    async function setupWs(): Promise<WebSocket> {
      mockApi.post.mockResolvedValueOnce({
        data: { data: { first_question: 'Q1', point_list: [], point_id: 'p1' } },
      })
      await useInterviewStore.getState().startInterview('sess-1')
      await waitForOpen()
      // 通过内部 ws 变量拿到 socket 不容易，这里直接发消息触发 onmessage
      // 我们通过 spy WebSocket 构造函数拿实例
      return (globalThis.WebSocket as unknown as { _lastInstance?: WebSocket })._lastInstance!
    }

    it('question_start 退出 thinking', async () => {
      await setupWs()
      useInterviewStore.setState({ thinking: true })

      // 触发 onmessage
      const wsClient = (globalThis.WebSocket as unknown as { _lastInstance: WebSocket })._lastInstance
      emitWsMessage(wsClient!, { type: 'question_start' })

      expect(useInterviewStore.getState().thinking).toBe(false)
    })

    it('question 消息：最后是空 assistant 占位 → 替换', async () => {
      await setupWs()
      // 设置一个空占位
      useInterviewStore.setState({
        messages: [{ role: 'assistant', content: '' }],
      })

      const wsClient = (globalThis.WebSocket as unknown as { _lastInstance: WebSocket })._lastInstance
      emitWsMessage(wsClient!, {
        type: 'question',
        content: '新问题',
        point_id: 'p2',
        round: 1,
      })

      const s = useInterviewStore.getState()
      expect(s.messages).toHaveLength(1)
      expect(s.messages[0].content).toBe('新问题')
      expect(s.messages[0].point_id).toBe('p2')
      expect(s.thinking).toBe(false)
    })

    it('question 消息：用户回答后（最后是 user）→ 追加新 assistant 消息', async () => {
      // 这是修复的关键 bug：用户回答后最后一条是 user，必须追加而非替换
      await setupWs()
      useInterviewStore.setState({
        messages: [
          { role: 'assistant', content: 'Q1' },
          { role: 'user', content: '我的回答' },
        ],
      })

      const wsClient = (globalThis.WebSocket as unknown as { _lastInstance: WebSocket })._lastInstance
      emitWsMessage(wsClient!, {
        type: 'question',
        content: '追问问题',
        point_id: 'p1',
      })

      const s = useInterviewStore.getState()
      expect(s.messages).toHaveLength(3)
      expect(s.messages[2]).toEqual({
        role: 'assistant',
        content: '追问问题',
        point_id: 'p1',
      })
    })

    it('question 消息：有流式内容且最后是 assistant → 替换', async () => {
      await setupWs()
      useInterviewStore.setState({
        messages: [
          { role: 'user', content: '回答' },
          { role: 'assistant', content: '部分内容' },
        ],
      })

      const wsClient = (globalThis.WebSocket as unknown as { _lastInstance: WebSocket })._lastInstance
      // 先发 chunk 消息累积 streamingContent
      emitWsMessage(wsClient!, { type: 'chunk', content: '流式片段' })
      // 再发 question 消息
      emitWsMessage(wsClient!, {
        type: 'question',
        content: '完整内容',
        point_id: 'p1',
      })

      const s = useInterviewStore.getState()
      expect(s.messages).toHaveLength(2)
      expect(s.messages[1].content).toBe('完整内容')
    })

    it('status 消息更新 pointStates 和 progress', async () => {
      await setupWs()
      useInterviewStore.setState({
        pointStates: [
          { id: 'p1', source_text: 'x', priority: 'low', status: 'pending' },
          { id: 'p2', source_text: 'y', priority: 'low', status: 'pending' },
        ],
        progress: 0,
      })

      const wsClient = (globalThis.WebSocket as unknown as { _lastInstance: WebSocket })._lastInstance
      emitWsMessage(wsClient!, {
        type: 'status',
        point_states: { p1: 'resolved', p2: 'active' },
        progress: 0.5,
      })

      const s = useInterviewStore.getState()
      expect(s.pointStates[0].status).toBe('resolved')
      expect(s.pointStates[1].status).toBe('active')
      expect(s.progress).toBe(0.5)
    })

    it('complete 消息设置 isComplete 和 report', async () => {
      await setupWs()
      const report = {
        overall_score: 85,
        total_points: 2,
        resolved_points: 1,
        skipped_points: 0,
        point_feedbacks: [],
        suggestions: [],
        summary: '表现良好',
      }

      const wsClient = (globalThis.WebSocket as unknown as { _lastInstance: WebSocket })._lastInstance
      emitWsMessage(wsClient!, { type: 'complete', report })

      const s = useInterviewStore.getState()
      expect(s.isComplete).toBe(true)
      expect(s.status).toBe('complete')
      expect(s.report).toEqual(report)
      expect(s.progress).toBe(1)
      expect(s.thinking).toBe(false)
    })

    it('error 消息追加系统提示并设置 error', async () => {
      await setupWs()
      useInterviewStore.setState({ messages: [], thinking: true })

      const wsClient = (globalThis.WebSocket as unknown as { _lastInstance: WebSocket })._lastInstance
      emitWsMessage(wsClient!, {
        type: 'error',
        code: '1500',
        error: 'LLM 不可用',
      })

      const s = useInterviewStore.getState()
      expect(s.messages).toHaveLength(1)
      expect(s.messages[0].content).toContain('AI 服务暂时不可用')
      expect(s.error).toBe('AI 服务暂时不可用，请稍后重试')
      expect(s.thinking).toBe(false)
    })

    it('error 消息无 code 时使用 fallback', async () => {
      await setupWs()
      useInterviewStore.setState({ messages: [] })

      const wsClient = (globalThis.WebSocket as unknown as { _lastInstance: WebSocket })._lastInstance
      emitWsMessage(wsClient!, {
        type: 'error',
        error: '自定义错误',
      })

      expect(useInterviewStore.getState().error).toBe('自定义错误')
    })

    it('非法 JSON 消息不崩溃', async () => {
      await setupWs()
      const wsClient = (globalThis.WebSocket as unknown as { _lastInstance: WebSocket })._lastInstance
      const handler = (wsClient as unknown as { onmessage: ((ev: MessageEvent) => void) | null }).onmessage

      // 不应抛异常
      expect(() => {
        handler?.(new MessageEvent('message', { data: 'not json' }))
      }).not.toThrow()
    })
  })

  describe('endInterview', () => {
    it('成功结束后设置 complete 状态', async () => {
      useInterviewStore.setState({ sessionId: 'sess-1' })
      mockApi.post.mockResolvedValueOnce({
        data: {
          data: {
            report: {
              overall_score: 70,
              total_points: 1,
              resolved_points: 1,
              skipped_points: 0,
              point_feedbacks: [],
              suggestions: [],
              summary: 'ok',
            },
          },
        },
      })

      await useInterviewStore.getState().endInterview()

      const s = useInterviewStore.getState()
      expect(s.isComplete).toBe(true)
      expect(s.status).toBe('complete')
      expect(s.report?.overall_score).toBe(70)
      expect(s.progress).toBe(1)
    })

    it('无 sessionId 时不执行', async () => {
      await useInterviewStore.getState().endInterview()
      expect(mockApi.post).not.toHaveBeenCalled()
    })

    it('结束失败时设置 error', async () => {
      useInterviewStore.setState({ sessionId: 'sess-1' })
      const err = new Error('boom')
      ;(err as { response?: { data?: { detail?: { message?: string } } } }).response = {
        data: { detail: { message: '结束失败原因' } },
      }
      mockApi.post.mockRejectedValueOnce(err)

      await useInterviewStore.getState().endInterview()

      expect(useInterviewStore.getState().error).toBe('结束失败原因')
      expect(useInterviewStore.getState().status).toBe('error')
    })
  })

  describe('disconnect', () => {
    it('调用后 wsConnected 为 false', async () => {
      mockApi.post.mockResolvedValueOnce({
        data: { data: { first_question: 'Q', point_list: [], point_id: 'p1' } },
      })
      await useInterviewStore.getState().startInterview('sess-1')
      await waitForOpen()

      useInterviewStore.getState().disconnect()
      expect(useInterviewStore.getState().wsConnected).toBe(false)
    })
  })
})
