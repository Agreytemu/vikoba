import Spinner from "@/components/Spinner";
import { useRefreshToken } from "@/hooks/api/auth";
import { AuthResponse } from "@/services/auth";
import api from "@/lib/api";
import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
  useCallback,
} from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useRef } from "react";
import { toast } from "react-toastify";

// Routes that render without requiring authentication (marketing/landing).
const PUBLIC_PATHS = ["/", "/landing"];

// A money app: when the PWA/app is closed or backgrounded for this long, the
// session locks and the next visit lands on the sign-in page (not the portal).
const IDLE_LIMIT_MS = 5 * 60 * 1000; // 5 minutes
const LAST_ACTIVE_KEY = "vk_last_active";
const HIDDEN_SINCE_KEY = "vk_hidden_since";

interface AuthContextType {
  isAuthenticated: boolean;
  login: (data: AuthResponse) => void;
  logout: () => void;
  isLoading: boolean;
}
// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextType | undefined>(
  undefined,
);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const navigate = useNavigate();
  const location = useLocation();
  const { mutate: generateRefreshToken } = useRefreshToken();

  const SESSION_DURATION = 12 * 60 * 60 * 1000; // session expires in 12 hours

  // Guards against the logout race: a refresh request that was already in
  // flight can resolve AFTER logout ran and silently re-store tokens. When the
  // user has logged out this flag stays true, so a late onSuccess is ignored.
  const loggedOutRef = useRef(false);

  const clearStoredSession = useCallback(() => {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("expiresAt");
    localStorage.removeItem(LAST_ACTIVE_KEY);
    sessionStorage.removeItem(HIDDEN_SINCE_KEY);
  }, []);

  // Local logout is the source of truth: it must happen immediately and the
  // server session is ended separately (best-effort) by the caller.
  const logout = useCallback(() => {
    loggedOutRef.current = true;
    clearStoredSession();
    setIsAuthenticated(false);
    navigate("/login");
  }, [clearStoredSession, navigate]);

  const forceLock = useCallback(
    (message?: string) => {
      if (loggedOutRef.current) return;
      loggedOutRef.current = true;
      clearStoredSession();
      setIsAuthenticated(false);
      if (message) toast.info(message, { autoClose: 4000 });
      navigate("/login");
    },
    [clearStoredSession, navigate],
  );

  // Watch for the app being closed / sent to the background. A `visibilitychange`
  // to hidden records the timestamp; returning after the idle limit locks the
  // session. `pagehide` stamps last activity so the very next fresh open of the
  // PWA checks the gap in the mount effect below.
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden) {
        sessionStorage.setItem(HIDDEN_SINCE_KEY, String(Date.now()));
        return;
      }
      const hiddenSince = Number(sessionStorage.getItem(HIDDEN_SINCE_KEY) || 0);
      localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
      if (hiddenSince && Date.now() - hiddenSince > IDLE_LIMIT_MS) {
        forceLock("Security lock: the app was left closed too long. Please sign in again.");
      }
    };
    const handlePageHide = () => {
      localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
    };
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("pagehide", handlePageHide);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("pagehide", handlePageHide);
    };
  }, [forceLock]);

  useEffect(() => {
    const accessToken = localStorage.getItem("accessToken");
    const refreshToken = localStorage.getItem("refreshToken");
    const accessExpiresAt = Number(localStorage.getItem("expiresAt") || 0);

    // Returning to a freshly opened app after it was closed for longer than the
    // idle limit: the session is treated as locked, straight back to sign-in.
    const now = Date.now();
    const lastActive = Number(localStorage.getItem(LAST_ACTIVE_KEY) || 0);
    if (lastActive > 0 && now - lastActive > IDLE_LIMIT_MS) {
      clearStoredSession();
      setIsLoading(false);
      setIsAuthenticated(false);
      navigate("/login");
      toast.info("Session locked for security. Please sign in again.", { autoClose: 4000 });
      return;
    }
    localStorage.setItem(LAST_ACTIVE_KEY, String(now));

    if (!refreshToken) {
      setIsLoading(false);
      // Public routes (landing/marketing) are reachable without auth.
      if (!PUBLIC_PATHS.includes(location.pathname)) {
        logout();
        navigate("/login");
      }
      return;
    }

    // 1 Access token present AND not expired locally -> authenticate now, then
    //    verify it against the backend in the background. A tampered token is
    //    rejected there: the response interceptor refreshes the access token
    //    on a 401 and, if that refresh also fails, signs the user out.
    if (accessToken && accessExpiresAt && now < accessExpiresAt) {
      setIsAuthenticated(true);
      setIsLoading(false);
      api
        .get("/auth/me")
        .then(() => {
          // Valid session confirmed; nothing else to do here.
        })
        .catch(() => {
          // The interceptor already handled 401 -> refresh -> logout. Signs of
          // a network failure are intentionally ignored so an offline device
          // does not sign the user out on its own.
        });
      // Schedule an automatic sign-out at the moment the session expires, so
      // an idle tab cannot stay on the portal past `expiresAt`.
      const remaining = accessExpiresAt - now;
      const timer = setTimeout(() => {
        forceLock("Your session expired. Please sign in again.");
      }, Math.max(remaining, 0));
      // Only navigate to dashboard if user is on a public/auth page. If they
      // arrived from an emailed invitation, send them back to the invite page
      // (which auto-accepts once logged in); otherwise go to the dashboard.
      if (
        !PUBLIC_PATHS.includes(location.pathname) &&
        (location.pathname === "/login" || location.pathname === "/register")
      ) {
        const fromPath = (location.state as { from?: string } | null)?.from;
        navigate(fromPath && fromPath.startsWith("/") ? fromPath : "/");
      }
      return () => clearTimeout(timer);
    }

    // 2 Access token missing or expired -> refresh it now.
    generateRefreshToken(
      { refresh: refreshToken },
      {
        onSuccess: (data) => {
          if (loggedOutRef.current) return;
          const newExpiresAt = Date.now() + SESSION_DURATION;
          localStorage.setItem("accessToken", data.access);
          localStorage.setItem("expiresAt", newExpiresAt.toString());
          setIsAuthenticated(true);
          setIsLoading(false);
        },
        onError: () => {
          setIsLoading(false);
          logout(); // Logout user when refresh token is invalid
        },
      },
    );
  // Only re-evaluate this guard when the auth flag flips (login/logout).
    // Re-running on every navigation would trigger token refreshes or
    // /auth/me requests on each route change, so location is deliberately
    // not part of the dependency array.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, clearStoredSession, forceLock, logout]);

  const login = (data: AuthResponse) => {
    loggedOutRef.current = false;
    const expiresAt = Date.now() + SESSION_DURATION;
    localStorage.setItem("accessToken", data.access);
    localStorage.setItem("refreshToken", data.refresh || "");
    localStorage.setItem("expiresAt", expiresAt.toString());
    localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
    setIsAuthenticated(true);
  };

  if (isLoading) {
    return (
      <div className="w-full h-screen flex items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const Auth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};