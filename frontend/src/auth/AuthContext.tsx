import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError } from "../api/client";
import type { User } from "../api/types";

type AuthStatus = "loading" | "authenticated" | "anonymous" | "error";

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  error: string | null;
  acceptUser: (user: User) => void;
  clearSession: () => void;
  logout: () => Promise<void>;
  retry: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setStatus("loading");
    setError(null);

    void api
      .me(controller.signal)
      .then((currentUser) => {
        setUser(currentUser);
        setStatus("authenticated");
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        setUser(null);
        if (reason instanceof ApiError && reason.status === 401) {
          setStatus("anonymous");
          return;
        }
        setError(
          reason instanceof Error
            ? reason.message
            : "Unable to verify your session.",
        );
        setStatus("error");
      });

    return () => controller.abort();
  }, [attempt]);

  const acceptUser = useCallback((nextUser: User) => {
    setUser(nextUser);
    setError(null);
    setStatus("authenticated");
  }, []);

  const clearSession = useCallback(() => {
    setUser(null);
    setError(null);
    setStatus("anonymous");
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    clearSession();
  }, [clearSession]);

  const retry = useCallback(() => {
    setAttempt((value) => value + 1);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      error,
      acceptUser,
      clearSession,
      logout,
      retry,
    }),
    [acceptUser, clearSession, error, logout, retry, status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
