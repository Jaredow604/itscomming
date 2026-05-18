import axios from 'axios';

/**
 * Axios instance pre-configured for the Django REST Framework backend.
 *
 * Base URL points to the local Django dev server.
 * In production, this would be swapped via environment variable.
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8001',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000, // 30s — models can take time on CPU
});

export default apiClient;
