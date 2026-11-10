import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

/**
 * Centralized Axios instance for API communication.
 * Cookies are sent so the httpOnly refresh cookie reaches /auth/* (UI and API must be same-site).
 */
export const api = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true,
    headers: {
        'Content-Type': 'application/json',
    },
});

// The access token lives only in memory; the refresh token is an httpOnly cookie.
let accessToken: string | null = null;
export const setAccessToken = (token: string | null) => {
    accessToken = token;
};

// Tokens stored by older builds are readable by any script; drop them.
localStorage.removeItem('quantara_token');
localStorage.removeItem('quantara_refresh_token');

/**
 * Request Interceptor: Inject JWT token into every request.
 */
api.interceptors.request.use((config) => {
    if (accessToken && config.headers && !config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

// One shared refresh so a burst of 401s triggers a single /auth/refresh call.
let refreshInFlight: Promise<string> | null = null;

/** Trade the refresh cookie for a new access token. */
export function refreshAccessToken(): Promise<string> {
    refreshInFlight ??= axios
        .post<{ access_token: string }>(`${API_BASE_URL}/auth/refresh`, null, { withCredentials: true })
        .then(({ data }) => {
            accessToken = data.access_token;
            return data.access_token;
        })
        .finally(() => {
            refreshInFlight = null;
        });
    return refreshInFlight;
}

/**
 * Response Interceptor: on 401, refresh the access token once and replay the request;
 * if that fails, clear the session and send the user to login.
 */
api.interceptors.response.use((response) => {
    return response;
}, async (error) => {
    const original = error.config;
    const isAuthCall = original?.url?.startsWith('/auth/');
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
        original._retried = true;
        try {
            const token = await refreshAccessToken();
            original.headers.Authorization = `Bearer ${token}`;
            return api(original);
        } catch {
            // fall through to logout
        }
    }
    if (error.response?.status === 401 && !isAuthCall) {
        // Session expired or unauthorized
        accessToken = null;
        localStorage.removeItem('quantara_user');

        // Redirect if not already on login page
        if (!window.location.pathname.includes('/login')) {
            window.location.href = '/login';
        }
    }
    return Promise.reject(error);
});

/**
 * POST whose plain-text response is handed over piece by piece (axios can't stream in browsers).
 * Uses the same in-memory token, refreshing it once on a 401 like the axios interceptor.
 */
export async function postStream(path: string, body: unknown, onText: (chunk: string) => void): Promise<void> {
    const send = () => fetch(`${API_BASE_URL}${path}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
        body: JSON.stringify(body),
    });
    let resp = await send();
    if (resp.status === 401) {
        await refreshAccessToken();
        resp = await send();
    }
    if (!resp.ok || !resp.body) {
        const detail = await resp.json().then(d => d?.detail).catch(() => undefined);
        throw new Error(typeof detail === 'string' ? detail : `Request failed (${resp.status})`);
    }
    const reader = resp.body.pipeThrough(new TextDecoderStream()).getReader();
    for (;;) {
        const { value, done } = await reader.read();
        if (done) return;
        onText(value);
    }
}

/**
 * The listed ticker meant by a typed symbol or name ("ITC" -> "ITC.NS", "infosys" -> "INFY.NS");
 * null when nothing is listed under it, the input as typed if the lookup itself fails.
 */
export async function resolveTicker(text: string): Promise<string | null> {
    try {
        return (await api.get<{ ticker: string }>('/stocks/resolve', { params: { q: text.trim() } })).data.ticker;
    } catch (err) {
        return axios.isAxiosError(err) && err.response?.status === 404 ? null : text.trim().toUpperCase();
    }
}

/** The API's string `detail` message from a failed request, if there is one. */
export function apiErrorDetail(err: unknown): string | undefined {
    if (!axios.isAxiosError(err)) return undefined;
    const detail = err.response?.data?.detail;
    return typeof detail === 'string' ? detail : undefined;
}

export default api;
