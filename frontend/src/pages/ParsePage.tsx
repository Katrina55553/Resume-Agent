import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../utils/api';

interface ResumeData {
  name?: string;
  phone?: string;
  email?: string;
  summary?: string;
  raw_text?: string;
  work_experience: Array<{
    company: string;
    position: string;
    start_date?: string;
    end_date?: string;
    description?: string;
    achievements: string[];
  }>;
  education: Array<{
    school: string;
    degree: string;
    major: string;
    start_date?: string;
    end_date?: string;
  }>;
  projects: Array<{
    name: string;
    role?: string;
    description?: string;
    technologies: string[];
    achievements: string[];
  }>;
  skills: Array<{
    category: string;
    skills: string[];
  }>;
}

/**
 * 步骤1：解析确认页
 * 左侧简历预览（暂用原始文本），右侧可编辑结构化卡片
 * 用户确认/修正后触发诊断
 */
export default function ParsePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<ResumeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载解析结果
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    api.get(`/sessions/${id}/parse`)
      .then((res) => {
        if (!cancelled) {
          setData(res.data.data.parsed_data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.response?.data?.detail?.message || '加载解析结果失败');
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [id]);

  // 确认解析结果，触发诊断
  const handleConfirm = useCallback(async () => {
    if (!id || !data) return;
    setSaving(true);
    try {
      // 先保存修正
      await api.put(`/sessions/${id}/parse`, { parsed_data: data });
      // 触发诊断
      await api.post(`/sessions/${id}/diagnose`);
      navigate(`/session/${id}/diagnose`);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: { message?: string } } } };
      setError(e.response?.data?.detail?.message || '操作失败');
    } finally {
      setSaving(false);
    }
  }, [id, data, navigate]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500">加载解析结果...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error || '无解析数据'}</p>
          <button onClick={() => navigate('/')} className="text-blue-500 underline">
            返回首页
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航 */}
      <div className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <button
          onClick={() => navigate('/')}
          className="text-gray-500 hover:text-gray-700 flex items-center gap-1"
        >
          ← 重新上传
        </button>
        <span className="text-sm text-gray-400">步骤 1/4 · 解析确认</span>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* 左侧：简历原文预览 */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4 text-gray-700">简历原文</h2>
            <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600 whitespace-pre-wrap max-h-[600px] overflow-y-auto">
              {data.raw_text || data.summary || '（原文预览暂不可用）'}
            </div>
          </div>

          {/* 右侧：可编辑结构化卡片 */}
          <div className="space-y-6">
            {/* 基本信息 */}
            <EditableCard title="基本信息">
              <EditableField label="姓名" value={data.name || ''} onChange={(v) => setData({ ...data, name: v })} />
              <EditableField label="邮箱" value={data.email || ''} onChange={(v) => setData({ ...data, email: v })} />
              <EditableField label="电话" value={data.phone || ''} onChange={(v) => setData({ ...data, phone: v })} />
              <EditableField label="简介" value={data.summary || ''} onChange={(v) => setData({ ...data, summary: v })} multiline />
            </EditableCard>

            {/* 技能标签 */}
            <EditableCard title="技能标签">
              <div className="flex flex-wrap gap-2">
                {data.skills?.flatMap((s) => s.skills).map((skill, i) => (
                  <span key={i} className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-sm px-3 py-1 rounded-full">
                    {skill}
                    <button
                      onClick={() => {
                        const newSkills = data.skills.map((s) => ({
                          ...s,
                          skills: s.skills.filter((_, j) => !(j === 0 && s === data.skills[0] && skill === s.skills[0])),
                        }));
                        setData({ ...data, skills: newSkills });
                      }}
                      className="text-blue-400 hover:text-blue-600 ml-1"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </EditableCard>

            {/* 工作经历 */}
            {data.work_experience?.map((exp, i) => (
              <EditableCard key={i} title={`${exp.company} · ${exp.position}`}>
                <EditableField label="公司" value={exp.company} onChange={(v) => {
                  const updated = [...data.work_experience];
                  updated[i] = { ...updated[i], company: v };
                  setData({ ...data, work_experience: updated });
                }} />
                <EditableField label="职位" value={exp.position} onChange={(v) => {
                  const updated = [...data.work_experience];
                  updated[i] = { ...updated[i], position: v };
                  setData({ ...data, work_experience: updated });
                }} />
                <EditableField label="描述" value={exp.description || ''} onChange={(v) => {
                  const updated = [...data.work_experience];
                  updated[i] = { ...updated[i], description: v };
                  setData({ ...data, work_experience: updated });
                }} multiline />
                <div className="mt-2">
                  <p className="text-xs text-gray-500 mb-1">成果：</p>
                  {exp.achievements?.map((ach, j) => (
                    <div key={j} className="flex items-center gap-2 mb-1">
                      <span className="text-gray-400">·</span>
                      <input
                        className="flex-1 text-sm border-b border-transparent hover:border-gray-300 focus:border-blue-500 outline-none py-0.5 bg-transparent"
                        value={ach}
                        onChange={(e) => {
                          const updated = [...data.work_experience];
                          const achievements = [...updated[i].achievements];
                          achievements[j] = e.target.value;
                          updated[i] = { ...updated[i], achievements };
                          setData({ ...data, work_experience: updated });
                        }}
                      />
                    </div>
                  ))}
                </div>
              </EditableCard>
            ))}

            {/* 项目经历 */}
            {data.projects?.map((proj, i) => (
              <EditableCard key={i} title={`项目：${proj.name}`}>
                <EditableField label="项目名" value={proj.name} onChange={(v) => {
                  const updated = [...data.projects];
                  updated[i] = { ...updated[i], name: v };
                  setData({ ...data, projects: updated });
                }} />
                <EditableField label="角色" value={proj.role || ''} onChange={(v) => {
                  const updated = [...data.projects];
                  updated[i] = { ...updated[i], role: v };
                  setData({ ...data, projects: updated });
                }} />
                <EditableField label="描述" value={proj.description || ''} onChange={(v) => {
                  const updated = [...data.projects];
                  updated[i] = { ...updated[i], description: v };
                  setData({ ...data, projects: updated });
                }} multiline />
                <div className="mt-2">
                  <p className="text-xs text-gray-500 mb-1">技术栈：</p>
                  <div className="flex flex-wrap gap-1">
                    {proj.technologies?.map((tech, j) => (
                      <span key={j} className="bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded">
                        {tech}
                      </span>
                    ))}
                  </div>
                </div>
              </EditableCard>
            ))}

            {/* 教育经历 */}
            {data.education?.map((edu, i) => (
              <EditableCard key={i} title={`${edu.school} · ${edu.degree}`}>
                <EditableField label="学校" value={edu.school} onChange={(v) => {
                  const updated = [...data.education];
                  updated[i] = { ...updated[i], school: v };
                  setData({ ...data, education: updated });
                }} />
                <EditableField label="学位" value={edu.degree} onChange={(v) => {
                  const updated = [...data.education];
                  updated[i] = { ...updated[i], degree: v };
                  setData({ ...data, education: updated });
                }} />
                <EditableField label="专业" value={edu.major} onChange={(v) => {
                  const updated = [...data.education];
                  updated[i] = { ...updated[i], major: v };
                  setData({ ...data, education: updated });
                }} />
              </EditableCard>
            ))}
          </div>
        </div>

        {/* 确认按钮 */}
        <div className="mt-8 text-center">
          <button
            onClick={handleConfirm}
            disabled={saving}
            className="rounded-xl bg-blue-600 px-10 py-3 text-white font-medium text-lg hover:bg-blue-700 transition disabled:opacity-50"
          >
            {saving ? '保存中...' : '确认，开始诊断 →'}
          </button>
        </div>
      </div>
    </div>
  );
}

/** 可编辑卡片容器 */
function EditableCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

/** 可编辑字段 */
function EditableField({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
}) {
  const Component = multiline ? 'textarea' : 'input';
  return (
    <div className="flex items-start gap-3">
      <span className="text-xs text-gray-400 w-12 shrink-0 pt-1.5">{label}</span>
      <Component
        className="flex-1 text-sm border border-transparent hover:border-gray-200 focus:border-blue-500 rounded px-2 py-1 outline-none bg-transparent resize-none"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={multiline ? 3 : undefined}
      />
    </div>
  );
}
