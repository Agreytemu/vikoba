import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}


export const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString();
};

const formatFieldName = (field: string) =>
  field.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

const getSafeMessage = (value: unknown): string | null => {
  if (typeof value !== "string") return null;

  const message = value.replace(/\s+/g, " ").trim();
  // Never expose server debug output, stack traces, or database diagnostics.
  if (
    !message ||
    message.length > 500 ||
    /<(?:!doctype|html|head|body)\b|\b(?:traceback|stack trace|integrityerror|databaseerror|operationalerror|programmingerror|validationerror|unique constraint|foreign key constraint|sql(?:ite)?\s+(?:error|exception)|psycopg|django\.db)\b|\b(?:internal server error|bad gateway|service unavailable)\b/i.test(
      message,
    )
  ) {
    return null;
  }

  return message;
};

const isTimeoutError = (v: unknown) => {
  if (!v || typeof v !== "object") return false;
  const r = v as Record<string, unknown>;
  return r.code === "ECONNABORTED" || (typeof r.message === "string" && /timeout/i.test(r.message));
};
const isNetworkError = (v: unknown) => {
  if (!v || typeof v !== "object") return false;
  const r = v as Record<string, unknown>;
  return r.code === "ERR_NETWORK" || (typeof r.message === "string" && /Network Error/i.test(r.message));
};

/** Turns Django REST Framework validation responses into a toast-ready message. */
export const getApiErrorMessage = (
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string => {
  if (isTimeoutError(error)) {
    return "This is taking longer than expected. Please refresh your page, check your internet connection, and try again.";
  }
  if (isNetworkError(error) || (error && typeof error === "object" && "request" in (error as Record<string, unknown>) && !(error as Record<string, unknown>).response)) {
    return "Your internet connection seems unstable. Please check your connection, refresh the page, and try again.";
  }
  const directMessage = getSafeMessage(error);
  if (directMessage) return directMessage;
  if (typeof error === "string") {
    if (/Network Error/i.test(error)) return "Your internet connection seems unstable. Please check your connection, refresh the page, and try again.";
    if (/timeout/i.test(error)) return "This is taking longer than expected. Please refresh your page, check your internet connection, and try again.";
    return getSafeMessage(error) ?? fallback;
  }
  if (error instanceof Error) {
    if (/Network Error/i.test(error.message)) return "Your internet connection seems unstable. Please check your connection, refresh the page, and try again.";
    if (/timeout/i.test(error.message)) return "This is taking longer than expected. Please refresh your page, check your internet connection, and try again.";
    return getSafeMessage(error.message) ?? fallback;
  }
  if (!error || typeof error !== "object") return fallback;

  const response = error as Record<string, unknown>;
  if (typeof response.status === "number" && response.status >= 500) {
    return "Oops! Our server is having a tough moment. Please refresh your page and try again in a moment. If it keeps happening, check your internet connection.";
  }
  const detail = getSafeMessage(response.detail);
  if (detail) return detail;
  const message = getSafeMessage(response.message);
  if (message) return message;

  const messages = Object.entries(response).flatMap(([field, value]) => {
    const details = Array.isArray(value)
      ? value.map(String).join(" ")
      : typeof value === "string"
        ? value
        : value && typeof value === "object"
          ? getApiErrorMessage(value, "")
          : "";
    return details ? [`${formatFieldName(field)}: ${details}`] : [];
  });

  return getSafeMessage(messages.join(" ")) || fallback;
};
