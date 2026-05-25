import axios from 'axios';

/**
 * Axios 实例封装
 * baseURL 指向 /api，由 Vite 开发服务器代理到后端
 */
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：可在此添加 token 等认证信息
api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// 响应拦截器：统一处理错误
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.status, error.message);
    return Promise.reject(error);
  },
);

export default api;
