import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

/**
 * Centalized Axios instance for API communication.
 */
export const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

/**
 * Request Interceptor: Inject JWT token into every request.
 */
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('quantara_token');
    if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

/**
 * Response Interceptor: Handle global errors (e.g., 401 Unauthorized).
 */
api.interceptors.response.use((response) => {
    return response;
}, (error) => {
    if (error.response?.status === 401) {
        // Session expired or unauthorized
        localStorage.removeItem('quantara_token');
        localStorage.removeItem('quantara_user');

        // Redirect if not already on login page
        if (!window.location.pathname.includes('/login')) {
            window.location.href = '/login';
        }
    }
    return Promise.reject(error);
});

export default api;
