import { create } from 'zustand';
import api from '../utils/api';

export interface PointFeedback {
  point_id: string;
  source_text: string;
  score: number;
  status: string;
  feedback: string;
}

export interface InterviewReport {
  overall_score: number;
  total_points: number;
  resolved_points: number;
  skipped_points: number;
  point_feedbacks: PointFeedback[];
  suggestions: string[];
  summary: string;
}

interface ReportState {
  report: InterviewReport | null;
  status: 'idle' | 'loading' | 'done' | 'error';
  error: string | null;

  fetchReport: (sessionId: string) => Promise<void>;
  reset: () => void;
}

export const useReportStore = create<ReportState>((set) => ({
  report: null,
  status: 'idle',
  error: null,

  fetchReport: async (sessionId: string) => {
    set({ status: 'loading', error: null });
    try {
      const res = await api.get(`/sessions/${sessionId}/report`);
      const data = res.data.data;

      if (data.status === 'interviewing') {
        set({ status: 'idle' });
        return;
      }

      set({ report: data.report, status: 'done' });
    } catch (err: any) {
      const msg = err.response?.data?.detail?.message || err.message || '获取报告失败';
      set({ status: 'error', error: msg });
    }
  },

  reset: () => set({ report: null, status: 'idle', error: null }),
}));
