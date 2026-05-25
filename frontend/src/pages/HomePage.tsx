/**
 * 首页 — 上传简历入口
 */
export default function HomePage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">AI 简历诊断 + 模拟面试</h1>
        <p className="text-gray-500 mb-8">上传你的简历，开始智能诊断与模拟面试</p>
        <button
          type="button"
          className="rounded bg-blue-600 px-6 py-3 text-white hover:bg-blue-700 transition"
        >
          开始上传简历
        </button>
      </div>
    </div>
  );
}
