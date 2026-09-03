// Single source of truth for the API base URL. Trailing slashes are stripped
// because other modules concatenate paths onto this value directly.
export const apiBaseUrl =
  (import.meta.env.VITE_API_URL as string | undefined)?.trim().replace(/\/+$/, "") ||
  "http://localhost:8000/api/v1";

export const mediaBaseUrl = apiBaseUrl.replace(/\/api\/v1\/?$/, "");

export const resolveMediaUrl = (path: string) => {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return `${mediaBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
};
