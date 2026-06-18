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

const STEPS = ['解析确认', '诊断存疑', '模拟面试', '评估报告'];

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
      <div className="min-h-screen bg-paper bg-noise flex items-center justify-center px-6">
        <div className="paper-card rounded-2xl px-12 py-14 text-center max-w-md w-full animate-scale-in">
          <div className="relative mx-auto mb-6 w-14 h-14">
            <span className="absolute inset-0 rounded-full bg-accent-light" style={{ animation: 'pulse-ring 1.6s ease-out infinite' }} />
            <span className="absolute inset-0 rounded-full border-[3px] border-accent/20" />
            <span className="absolute inset-0 rounded-full border-[3px] border-accent border-t-transparent animate-spin" />
          </div>
          <h3 className="font-display text-xl text-ink mb-2">正在解析简历</h3>
          <p className="text-sm text-ink-light">AI 正在提取结构化信息，请稍候…</p>
          <div className="decor-line mt-6" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-paper bg-noise flex items-center justify-center px-6">
        <div className="paper-card rounded-2xl px-12 py-14 text-center max-w-md w-full animate-scale-in">
          <div className="mx-auto mb-5 w-12 h-12 rounded-full bg-priority-high-bg flex items-center justify-center">
            <span className="text-priority-high text-2xl font-display">!</span>
          </div>
          <h3 className="font-display text-xl text-ink mb-2">无法继续</h3>
          <p className="text-sm text-ink-light mb-6">{error || '无解析数据'}</p>
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-accent-dark transition"
          >
            ← 返回首页
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-paper bg-noise">
      <div className="relative z-10">
        {/* 顶部导航 */}
        <div className="sticky top-0 z-20 px-6 pt-4">
          <div className="max-w-6xl mx-auto paper-card rounded-2xl px-5 py-3 flex items-center justify-between animate-fade-in">
            <button
              onClick={() => navigate('/')}
              className="text-ink-light hover:text-ink flex items-center gap-1.5 text-sm transition group"
            >
              <span className="transition-transform group-hover:-translate-x-0.5">←</span>
              重新上传
            </button>

            {/* 步骤指示器 */}
            <div className="flex items-center gap-2">
              {STEPS.map((label, i) => {
                const idx = i + 1;
                const active = idx === 1;
                const done = idx < 1;
                return (
                  <div key={label} className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={[
                          'w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-medium transition',
                          active
                            ? 'bg-accent text-white'
                            : done
                            ? 'bg-accent-light text-accent'
                            : 'bg-paper-dark text-ink-muted',
                        ].join(' ')}
                      >
                        {done ? '✓' : idx}
                      </span>
                      <span
                        className={[
                          'text-xs hidden sm:inline transition',
                          active ? 'text-ink font-medium' : 'text-ink-muted',
                        ].join(' ')}
                      >
                        {label}
                      </span>
                    </div>
                    {idx < STEPS.length && (
                      <span className="w-4 h-px bg-border-strong" />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="max-w-6xl mx-auto px-6 py-8">
          {/* 页面标题 */}
          <div className="mb-8 animate-fade-up">
            <p className="text-xs uppercase tracking-[0.2em] text-accent font-medium mb-2">Step 01 · Parse</p>
            <h1 className="font-display text-3xl sm:text-4xl text-ink leading-tight">
              解析确认 <span className="text-gradient">校对结构化结果</span>
            </h1>
            <p className="text-sm text-ink-light mt-2">
              左侧为简历原文，右侧为 AI 提取的结构化字段。请核对并修正后，进入下一步诊断。
            </p>
            <div className="decor-line mt-5" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 左侧：简历原文预览 */}
            <div className="paper-card rounded-2xl p-6 animate-fade-up lg:sticky lg:top-24 lg:self-start" style={{ animationDelay: '0.05s' }}>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-display text-lg text-ink flex items-center gap-2">
                  <span className="w-1 h-4 bg-accent rounded-full" />
                  简历原文
                </h2>
                <span className="text-[11px] uppercase tracking-wider text-ink-muted">Raw Text</span>
              </div>

              <div className="relative">
                {/* 引号装饰 */}
                <span
                  aria-hidden
                  className="font-display absolute -top-2 -left-1 text-5xl leading-none text-accent/20 select-none"
                >
                  “
                </span>
                <span
                  aria-hidden
                  className="font-display absolute -bottom-6 -right-1 text-5xl leading-none text-accent/20 select-none"
                >
                  ”
                </span>
                <div className="bg-paper-dark rounded-xl p-5 pl-8 text-sm text-ink-light whitespace-pre-wrap max-h-[600px] overflow-y-auto leading-relaxed font-display">
                  {data.raw_text || data.summary || '（原文预览暂不可用）'}
                </div>
              </div>
            </div>

            {/* 右侧：可编辑结构化卡片 */}
            <div className="space-y-5">
              {/* 基本信息 */}
              <EditableCard title="基本信息" index={0}>
                <EditableField label="姓名" value={data.name || ''} onChange={(v) => setData({ ...data, name: v })} />
                <EditableField label="邮箱" value={data.email || ''} onChange={(v) => setData({ ...data, email: v })} />
                <EditableField label="电话" value={data.phone || ''} onChange={(v) => setData({ ...data, phone: v })} />
                <EditableField label="简介" value={data.summary || ''} onChange={(v) => setData({ ...data, summary: v })} multiline />
              </EditableCard>

              {/* 技能标签 */}
              <EditableCard title="技能标签" index={1}>
                <div className="flex flex-wrap gap-2">
                  {data.skills?.flatMap((s) => s.skills).map((skill, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 bg-accent-light text-accent-dark text-sm px-3 py-1 rounded-full border border-accent/15"
                    >
                      {skill}
                      <button
                        onClick={() => {
                          const newSkills = data.skills.map((s) => ({
                            ...s,
                            skills: s.skills.filter((_, j) => !(j === 0 && s === data.skills[0] && skill === s.skills[0])),
                          }));
                          setData({ ...data, skills: newSkills });
                        }}
                        className="text-accent/60 hover:text-priority-high ml-1 transition"
                        aria-label={`移除 ${skill}`}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </EditableCard>

              {/* 工作经历 */}
              {data.work_experience?.map((exp, i) => (
                <EditableCard key={i} title={`${exp.company} · ${exp.position}`} index={2 + i} subtitle="工作经历">
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
                    <p className="text-[11px] uppercase tracking-wider text-ink-muted mb-1.5">成果</p>
                    {exp.achievements?.map((ach, j) => (
                      <div key={j} className="flex items-center gap-2 mb-1">
                        <span className="text-accent">·</span>
                        <input
                          className="flex-1 text-sm border-b border-transparent hover:border-border-strong focus:border-accent outline-none py-0.5 bg-transparent text-ink-light"
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
                <EditableCard key={i} title={`项目：${proj.name}`} index={2 + (data.work_experience?.length || 0) + i} subtitle="项目经历">
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
                    <p className="text-[11px] uppercase tracking-wider text-ink-muted mb-1.5">技术栈</p>
                    <div className="flex flex-wrap gap-1.5">
                      {proj.technologies?.map((tech, j) => (
                        <span key={j} className="bg-paper-dark text-ink-light text-xs px-2.5 py-1 rounded-md border border-border">
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>
                </EditableCard>
              ))}

              {/* 教育经历 */}
              {data.education?.map((edu, i) => (
                <EditableCard key={i} title={`${edu.school} · ${edu.degree}`} index={2 + (data.work_experience?.length || 0) + (data.projects?.length || 0) + i} subtitle="教育经历">
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
          <div className="mt-10 text-center animate-fade-up" style={{ animationDelay: '0.15s' }}>
            <div className="decor-line mb-8" />
            <button
              onClick={handleConfirm}
              disabled={saving}
              className="group inline-flex items-center gap-2 rounded-xl bg-accent px-10 py-3.5 text-white font-medium text-base hover:bg-accent-dark transition disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-accent/20"
            >
              {saving ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  保存中…
                </>
              ) : (
                <>
                  确认，开始诊断
                  <span className="transition-transform group-hover:translate-x-0.5">→</span>
                </>
              )}
            </button>
            <p className="text-xs text-ink-muted mt-3">确认后将进入 AI 诊断环节，识别简历中的存疑点</p>
          </div>
        </div>
      </div>
    </div>
  );
}

/** 可编辑卡片容器 */
function EditableCard({
  title,
  subtitle,
  index = 0,
  children,
}: {
  title: string;
  subtitle?: string;
  index?: number;
  children: React.ReactNode;
}) {
  return (
    <div
      className="paper-card rounded-2xl p-5 animate-fade-up hover:shadow-lg hover:shadow-ink/[0.06] transition-shadow"
      style={{ animationDelay: `${0.05 + index * 0.04}s` }}
    >
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="font-display text-base text-ink flex items-center gap-2">
          <span className="w-1 h-3.5 bg-accent/70 rounded-full" />
          {title}
        </h3>
        {subtitle && (
          <span className="text-[10px] uppercase tracking-wider text-ink-muted">{subtitle}</span>
        )}
      </div>
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
    <div className="flex items-start gap-3 group">
      <span className="text-[11px] uppercase tracking-wider text-ink-muted w-12 shrink-0 pt-2 font-medium">
        {label}
      </span>
      <Component
        className="flex-1 text-sm border border-border rounded-lg px-3 py-1.5 outline-none bg-paper-dark/50 hover:bg-paper-dark focus:bg-surface focus:border-accent focus:ring-2 focus:ring-accent/10 transition text-ink resize-none"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={multiline ? 3 : undefined}
      />
    </div>
  );
}
