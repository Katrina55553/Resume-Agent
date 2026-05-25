import { create } from 'zustand';
import api from '../utils/api';

export interface DoubtPoint {
  id: string;
  priority: 'high' | 'medium' | 'low';
  source_text: string;
  reason: string;
  probe_questions: string[];
}

export interface OverallAssessment {
  completeness: number;
  tech_depth: 'low' | 'medium' | 'high';
  match_level: 'low' | 'medium' | 'high';
  doubt_count: number;
}

export interface DiagnoseResult {
  overall: OverallAssessment;
  doubt_points: DoubtPoint[];
  suggestions: string[];
}

interface DiagnoseState {
  result: DiagnoseResult | null;
  selectedIds: string[];
  status: 'idle' | 'loading' | 'done' | 'error';
  error: string | null;

  fetchDiagnose: (sessionId: string) => Promise<void>;
  togglePoint: (id: string) => void;
  selectAll: () => void;
  deselectAll: () => void;
  reset: () => void;
}

export const useDiagnoseStore = create<DiagnoseState>((set, get) => ({
  result: null,
  selectedIds: [],
  status: 'idle',
  error: null,

  fetchDiagnose: async (sessionId: string) => {
    set({ status: 'loading', error: null });
    try {
      const res = await api.get(`/sessions/${sessionId}/diagnose`);
      const data = res.data.data;

      if (data.status === 'diagnosing') {
        // 还在诊断中，不更新结果
        return;
      }

      set({
        result: data.result,
        selectedIds: data.result?.doubt_points?.map((p: DoubtPoint) => p.id) || [],
        status: 'done',
      });
    } catch (err: any) {
      const msg = err.response?.data?.detail?.message || err.message || '获取诊断结果失败';
      set({ status: 'error', error: msg });
    }
  },

  togglePoint: (id: string) => {
    const { selectedIds } = get();
    set({
      selectedIds: selectedIds.includes(id)
        ? selectedIds.filter((x) => x !== id)
        : [...selectedIds, id],
    });
  },

  selectAll: () => {
    const { result } = get();
    if (result) {
      set({ selectedIds: result.doubt_points.map((p) => p.id) });
    }
  },

  deselectAll: () => set({ selectedIds: [] }),

  reset: () => set({ result: null, selectedIds: [], status: 'idle', error: null }),
}));
