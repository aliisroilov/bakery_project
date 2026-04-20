/**
 * Axios client with JWT auth.
 *
 * - Stores access + refresh tokens in localStorage.
 * - On 401, tries to refresh once, then logs out if refresh also fails.
 * - All requests go to VITE_API_BASE (default http://localhost:8001/api/v1).
 */
import axios, {
  AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

const API_BASE =
  import.meta.env.VITE_API_BASE ?? "http://localhost:8001/api/v1";

const STORAGE = {
  ACCESS: "bakery.access",
  REFRESH: "bakery.refresh",
} as const;

export const tokens = {
  get access() {
    return localStorage.getItem(STORAGE.ACCESS);
  },
  get refresh() {
    return localStorage.getItem(STORAGE.REFRESH);
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(STORAGE.ACCESS, access);
    if (refresh) localStorage.setItem(STORAGE.REFRESH, refresh);
  },
  clear() {
    localStorage.removeItem(STORAGE.ACCESS);
    localStorage.removeItem(STORAGE.REFRESH);
  },
};

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const t = tokens.access;
  if (t && config.headers) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

// Minimal refresh-on-401 flow.
let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccess(): Promise<string | null> {
  const refresh = tokens.refresh;
  if (!refresh) return null;
  try {
    const res = await axios.post(`${API_BASE}/auth/refresh/`, { refresh });
    const newAccess = res.data.access as string;
    const newRefresh = res.data.refresh as string | undefined;
    tokens.set(newAccess, newRefresh);
    return newAccess;
  } catch {
    tokens.clear();
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };
    if (
      error.response?.status === 401 &&
      original &&
      !original._retry &&
      !original.url?.includes("/auth/")
    ) {
      original._retry = true;
      refreshInFlight ??= refreshAccess().finally(() => {
        refreshInFlight = null;
      });
      const newToken = await refreshInFlight;
      if (newToken) {
        original.headers = {
          ...original.headers,
          Authorization: `Bearer ${newToken}`,
        };
        return api(original);
      }
      // Refresh failed — redirect to login.
      if (typeof window !== "undefined") window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);
