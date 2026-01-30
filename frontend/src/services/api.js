/**
 * API Client - Centralized API communication
 */
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Token expired, try to refresh
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });
          
          const { access_token, refresh_token: newRefreshToken } = response.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', newRefreshToken);
          
          // Retry original request
          error.config.headers.Authorization = `Bearer ${access_token}`;
          return apiClient.request(error.config);
        } catch (refreshError) {
          // Refresh failed, clear tokens and redirect to login
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
          return Promise.reject(refreshError);
        }
      } else {
        // No refresh token, redirect to login
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: (username, password) =>
    apiClient.post('/auth/login', { username, password }),
  
  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    return Promise.resolve();
  },
  
  register: (data) =>
    apiClient.post('/auth/register', data),
  
  getCurrentUser: () =>
    apiClient.get('/auth/me'),
  
  updateProfile: (data) =>
    apiClient.put('/auth/me', data),
  
  changePassword: (data) =>
    apiClient.post('/auth/change-password', data),
};

// Projects API
export const projectsAPI = {
  list: (params) =>
    apiClient.get('/projects', { params }),
  
  get: (id) =>
    apiClient.get(`/projects/${id}`),
  
  create: (data) =>
    apiClient.post('/projects', data),
  
  update: (id, data) =>
    apiClient.put(`/projects/${id}`, data),
  
  delete: (id) =>
    apiClient.delete(`/projects/${id}`),
};

// Connections API
export const connectionsAPI = {
  list: (projectId) =>
    apiClient.get(`/projects/${projectId}/connections`),
  
  create: (projectId, data) =>
    apiClient.post(`/projects/${projectId}/connections`, data),
  
  test: (projectId, connectionId) =>
    apiClient.post(`/projects/${projectId}/connections/${connectionId}/test`),
  
  delete: (projectId, connectionId) =>
    apiClient.delete(`/projects/${projectId}/connections/${connectionId}`),
};

// Runs API
export const runsAPI = {
  list: (projectId, params) =>
    apiClient.get(`/projects/${projectId}/runs`, { params }),
  
  get: (runId) =>
    apiClient.get(`/runs/${runId}`),
  
  create: (projectId, data) =>
    apiClient.post(`/projects/${projectId}/runs`, data),
  
  cancel: (runId) =>
    apiClient.post(`/runs/${runId}/cancel`),
  
  getCheckpoint: (runId) =>
    apiClient.get(`/runs/${runId}/checkpoint`),
  
  resume: (runId) =>
    apiClient.post(`/runs/${runId}/resume`),
  
  clearCheckpoint: (runId) =>
    apiClient.delete(`/runs/${runId}/checkpoint`),
  getProgress: (runId) =>
    apiClient.get(`/runs/${runId}/progress`),
};

// Events API
export const eventsAPI = {
  list: (runId, params) =>
    apiClient.get(`/runs/${runId}/events`, { params }),
};

// Artifacts API
export const artifactsAPI = {
  list: (runId) =>
    apiClient.get(`/runs/${runId}/artifacts`),
  
  get: (runId, artifactPath) =>
    apiClient.get(`/runs/${runId}/artifacts/${artifactPath}`),
  
  download: (runId, artifactPath) =>
    apiClient.get(`/runs/${runId}/artifacts/${artifactPath}/download`, {
      responseType: 'blob',
    }),
};

export default apiClient;
