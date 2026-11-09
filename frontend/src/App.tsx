import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { ErrorState, LoadingScreen } from "./components/Feedback";
import { AuthPage } from "./pages/AuthPage";
import { Workspace } from "./pages/Workspace";

export function App() {
  const { status, error, retry } = useAuth();

  if (status === "loading") {
    return <LoadingScreen />;
  }

  if (status === "error") {
    return (
      <main className="centered-page">
        <a className="brand" href="/">
          <span className="brand-mark">N</span>
          <span>Northstar</span>
        </a>
        <ErrorState
          message={error ?? "The service is temporarily unavailable."}
          onRetry={retry}
          title="We couldn't open your workspace"
        />
      </main>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route
        path="/"
        element={
          status === "authenticated" ? (
            <Workspace />
          ) : (
            <Navigate replace to="/login" />
          )
        }
      />
      <Route
        path="*"
        element={
          <Navigate
            replace
            to={status === "authenticated" ? "/" : "/login"}
          />
        }
      />
    </Routes>
  );
}
