/**
 * sessionStore 单元测试
 *
 * 覆盖：上传、轮询、状态切换、错误处理、reset。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../utils/api'
import { useSessionStore } from './sessionStore'

// mock axios 实例
vi.mock('../utils/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

const mockApi = api as unknown as { post: ReturnType<typeof vi.fn>; get: ReturnType<typeof vi.fn> }

describe('sessionStore', () => {
  beforeEach(() => {
    useSessionStore.getState().reset()
    useSessionStore.setState({ _pollTimer: null })
    mockApi.post.mockReset()
    mockApi.get.mockReset()
  })

  afterEach(() => {
    useSessionStore.getState().stopPolling()
  })

  describe('初始状态', () => {
    it('应有正确的初始状态', () => {
      const s = useSessionStore.getState()
      expect(s.sessionId).toBeNull()
      expect(s.status).toBe('idle')
      expect(s.progress).toBe(0)
      expect(s.error).toBeNull()
      expect(s.fileName).toBeNull()
    })
  })

  describe('setters', () => {
    it('setSessionId', () => {
      useSessionStore.getState().setSessionId('abc')
      expect(useSessionStore.getState().sessionId).toBe('abc')
    })

    it('setStatus', () => {
      useSessionStore.getState().setStatus('parsing')
      expect(useSessionStore.getState().status).toBe('parsing')
    })

    it('setProgress', () => {
      useSessionStore.getState().setProgress(0.5)
      expect(useSessionStore.getState().progress).toBe(0.5)
    })

    it('setError', () => {
      useSessionStore.getState().setError('出错了')
      expect(useSessionStore.getState().error).toBe('出错了')
    })
  })

  describe('uploadFile', () => {
    it('上传成功后设置 sessionId 和 parsing 状态', async () => {
      mockApi.post.mockResolvedValueOnce({
        data: { data: { session_id: 'sess-1', status: 'parsing' } },
      })

      const id = await useSessionStore.getState().uploadFile(new File(['x'], 'r.pdf'))

      expect(id).toBe('sess-1')
      const s = useSessionStore.getState()
      expect(s.sessionId).toBe('sess-1')
      expect(s.status).toBe('parsing')
      expect(s.fileName).toBe('r.pdf')
      expect(s.progress).toBe(0.1)
    })

    it('上传成功但响应缺 status 时默认 parsing', async () => {
      mockApi.post.mockResolvedValueOnce({
        data: { data: { session_id: 'sess-2' } },
      })
      await useSessionStore.getState().uploadFile(new File(['x'], 'r.pdf'))
      expect(useSessionStore.getState().status).toBe('parsing')
    })

    it('上传失败时设置 failed 状态并抛出', async () => {
      const err = new Error('network')
      ;(err as { response?: { data?: { detail?: { message?: string } } } }).response = {
        data: { detail: { message: '文件太大' } },
      }
      mockApi.post.mockRejectedValueOnce(err)

      await expect(
        useSessionStore.getState().uploadFile(new File(['x'], 'r.pdf')),
      ).rejects.toThrow()

      const s = useSessionStore.getState()
      expect(s.status).toBe('failed')
      expect(s.error).toBe('文件太大')
    })

    it('上传失败无 message 时使用默认文案', async () => {
      mockApi.post.mockRejectedValueOnce(new Error('boom'))
      await expect(
        useSessionStore.getState().uploadFile(new File(['x'], 'r.pdf')),
      ).rejects.toThrow()
      expect(useSessionStore.getState().error).toBe('boom')
    })

    it('上传失败无任何信息时使用默认文案', async () => {
      mockApi.post.mockRejectedValueOnce({})
      await expect(
        useSessionStore.getState().uploadFile(new File(['x'], 'r.pdf')),
      ).rejects.toThrow()
      expect(useSessionStore.getState().error).toBe('上传失败')
    })

    it('上传开始时清空旧 error', async () => {
      useSessionStore.getState().setError('旧错误')
      mockApi.post.mockResolvedValueOnce({
        data: { data: { session_id: 's', status: 'parsing' } },
      })
      await useSessionStore.getState().uploadFile(new File(['x'], 'r.pdf'))
      expect(useSessionStore.getState().error).toBeNull()
    })
  })

  describe('startPolling', () => {
    it('收到 parsed 状态时停止轮询', async () => {
      vi.useFakeTimers()
      try {
        mockApi.get.mockResolvedValueOnce({
          data: { data: { status: 'parsing', progress: 0.5 } },
        })
        mockApi.get.mockResolvedValueOnce({
          data: { data: { status: 'parsed', progress: 1 } },
        })

        useSessionStore.getState().startPolling('sess-1')

        // 第一次 tick
        await vi.advanceTimersByTimeAsync(1000)
        expect(useSessionStore.getState().status).toBe('parsing')

        // 第二次 tick
        await vi.advanceTimersByTimeAsync(1000)
        expect(useSessionStore.getState().status).toBe('parsed')
        expect(useSessionStore.getState().progress).toBe(1)
        expect(useSessionStore.getState()._pollTimer).toBeNull()
      } finally {
        vi.useRealTimers()
      }
    })

    it('收到 failed 状态时停止轮询并设置 error', async () => {
      vi.useFakeTimers()
      try {
        mockApi.get.mockResolvedValueOnce({
          data: { data: { status: 'failed', error: '解析失败原因' } },
        })

        useSessionStore.getState().startPolling('sess-1')
        await vi.advanceTimersByTimeAsync(1000)

        expect(useSessionStore.getState().status).toBe('failed')
        expect(useSessionStore.getState().error).toBe('解析失败原因')
        expect(useSessionStore.getState()._pollTimer).toBeNull()
      } finally {
        vi.useRealTimers()
      }
    })

    it('failed 状态无 error 字段时使用默认文案', async () => {
      vi.useFakeTimers()
      try {
        mockApi.get.mockResolvedValueOnce({
          data: { data: { status: 'failed' } },
        })
        useSessionStore.getState().startPolling('sess-1')
        await vi.advanceTimersByTimeAsync(1000)
        expect(useSessionStore.getState().error).toBe('解析失败')
      } finally {
        vi.useRealTimers()
      }
    })

    it('网络错误不停止轮询', async () => {
      vi.useFakeTimers()
      try {
        mockApi.get.mockRejectedValueOnce(new Error('network'))
        mockApi.get.mockResolvedValueOnce({
          data: { data: { status: 'parsed', progress: 1 } },
        })

        useSessionStore.getState().startPolling('sess-1')

        await vi.advanceTimersByTimeAsync(1000)
        // 网络错误后仍可继续
        expect(useSessionStore.getState()._pollTimer).not.toBeNull()

        await vi.advanceTimersByTimeAsync(1000)
        expect(useSessionStore.getState().status).toBe('parsed')
      } finally {
        vi.useRealTimers()
      }
    })

    it('progress 缺失时默认为 0', async () => {
      vi.useFakeTimers()
      try {
        mockApi.get.mockResolvedValueOnce({
          data: { data: { status: 'parsing' } },
        })
        useSessionStore.getState().startPolling('sess-1')
        await vi.advanceTimersByTimeAsync(1000)
        expect(useSessionStore.getState().progress).toBe(0)
      } finally {
        vi.useRealTimers()
      }
    })

    it('重复调用 startPolling 清理旧定时器', () => {
      vi.useFakeTimers()
      try {
        mockApi.get.mockResolvedValue({
          data: { data: { status: 'parsing', progress: 0 } },
        })
        useSessionStore.getState().startPolling('sess-1')
        const firstTimer = useSessionStore.getState()._pollTimer
        useSessionStore.getState().startPolling('sess-2')
        const secondTimer = useSessionStore.getState()._pollTimer
        expect(firstTimer).not.toBe(secondTimer)
      } finally {
        vi.useRealTimers()
      }
    })
  })

  describe('stopPolling', () => {
    it('停止轮询后 _pollTimer 为 null', () => {
      vi.useFakeTimers()
      try {
        mockApi.get.mockResolvedValue({
          data: { data: { status: 'parsing', progress: 0 } },
        })
        useSessionStore.getState().startPolling('sess-1')
        expect(useSessionStore.getState()._pollTimer).not.toBeNull()

        useSessionStore.getState().stopPolling()
        expect(useSessionStore.getState()._pollTimer).toBeNull()
      } finally {
        vi.useRealTimers()
      }
    })

    it('未启动轮询时调用不报错', () => {
      expect(() => useSessionStore.getState().stopPolling()).not.toThrow()
    })
  })

  describe('reset', () => {
    it('重置所有状态', () => {
      useSessionStore.setState({
        sessionId: 'x',
        status: 'parsing',
        progress: 0.5,
        error: 'err',
        fileName: 'f.pdf',
      })
      useSessionStore.getState().reset()
      const s = useSessionStore.getState()
      expect(s.sessionId).toBeNull()
      expect(s.status).toBe('idle')
      expect(s.progress).toBe(0)
      expect(s.error).toBeNull()
      expect(s.fileName).toBeNull()
    })

    it('reset 时清理轮询定时器', () => {
      vi.useFakeTimers()
      try {
        mockApi.get.mockResolvedValue({
          data: { data: { status: 'parsing', progress: 0 } },
        })
        useSessionStore.getState().startPolling('sess-1')
        useSessionStore.getState().reset()
        expect(useSessionStore.getState()._pollTimer).toBeNull()
      } finally {
        vi.useRealTimers()
      }
    })
  })
})
