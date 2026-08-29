import axios, { type AxiosRequestConfig } from "axios";
import { apiBaseUrl } from "@/constants";

const api = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

// Custom flag consumed by the request interceptor to bypass auth/refresh logic.
type RequestConfig = AxiosRequestConfig & { skipInterceptor?: boolean };

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

// A 401 on any of these must NOT trigger a token refresh or a redirect: they
// are the credentials/verification endpoints themselves, so a rejection here
// is a normal business failure (wrong password, bad code, unverified email)
// that the page must render inline — not a session expiry. Trying to refresh
// on them caused a full reload to /login that swallowed the error message.
const NO_REFRESH_ENDPOINTS = [
  "/auth/login",
  "/auth/pin/login",
  "/auth/register",
  "/auth/logout",
  "/auth/email-verify",
  "/auth/email-verify-request",
  "/auth/request-password-reset",
  "/auth/password-reset",
  "/auth/pin/setup-request",
  "/auth/pin/setup-confirm",
];

const isNoRefreshEndpoint = (url: string | undefined) =>
  Boolean(url && NO_REFRESH_ENDPOINTS.some((endpoint) => url.includes(endpoint)));

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token || "");
    }
  });

  isRefreshing = false;
  failedQueue = [];
};

const refreshAccessToken = () => {
  if (typeof window === "undefined") {
    return Promise.reject("No window object");
  }

  const refreshToken = localStorage.getItem("refreshToken");

  if (!refreshToken) {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("expiresAt");
    window.location.href = "/login";
    return Promise.reject("No refresh token available");
  }

  return api
    .post("/auth/refresh-token", { refresh: refreshToken }, {
      skipInterceptor: true, // Prevent infinite loop
    } as RequestConfig)
    .then((response) => {
      // The response interceptor unwraps body data, so the resolved value is
      // the payload itself: { access, refresh }.
      const newAccessToken = (response as unknown as { access: string }).access;
      const SESSION_DURATION = 12 * 60 * 60 * 1000;
      const newExpiresAt = Date.now() + SESSION_DURATION;

      localStorage.setItem("accessToken", newAccessToken);
      localStorage.setItem("expiresAt", newExpiresAt.toString());

      return newAccessToken;
    })
    .catch((error: unknown) => {
      // Refresh token is invalid, logout user
      localStorage.removeItem("accessToken");
      localStorage.removeItem("refreshToken");
      localStorage.removeItem("expiresAt");
      window.location.href = "/login";
      return Promise.reject(error);
    });
};

api.interceptors.request.use(
  (config) => {
    // Skip interceptor if already refreshing
    if ((config as RequestConfig).skipInterceptor) {
      return config;
    }

    // FormData must not inherit the JSON default above. Removing the header
    // lets the browser provide multipart/form-data together with its required
    // boundary, allowing Django REST Framework to populate request.FILES.
    if (typeof FormData !== "undefined" && config.data instanceof FormData) {
      config.headers.delete("Content-Type");
    }

    // Client-side execution check
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("accessToken");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const originalRequest = error.config;

    // Check if error is 401 (Unauthorized) and not already retried
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !isNoRefreshEndpoint(originalRequest.url) &&
      typeof window !== "undefined"
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      return refreshAccessToken()
        .then((newToken) => {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          processQueue(null, newToken);
          return api(originalRequest);
        })
        .catch((err) => {
          processQueue(err, null);
          return Promise.reject(error.response?.data || error.message);
        });
    }

    // Handle error logging or global error states here
    return Promise.reject(error.response?.data || error.message);
  },
);

export default api;
