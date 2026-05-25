import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import ParsePage from './pages/ParsePage';
import DiagnosePage from './pages/DiagnosePage';
import InterviewPage from './pages/InterviewPage';
import ReportPage from './pages/ReportPage';

/**
 * 应用根组件
 * 配置 React Router 路由表
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/session/:id/parse" element={<ParsePage />} />
        <Route path="/session/:id/diagnose" element={<DiagnosePage />} />
        <Route path="/session/:id/interview" element={<InterviewPage />} />
        <Route path="/session/:id/report" element={<ReportPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
