import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "./auth";
import ProtectedRoute from "./components/ProtectedRoute";
import AboutPage from "./pages/AboutPage";
import ContactPage from "./pages/ContactPage";
import DashboardPage from "./pages/DashboardPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";

function NavLink({ to, label }: { to: string; label: string }) {
  const location = useLocation();
  const active = location.pathname === to;
  return (
    <Link className={`site-link ${active ? "site-link-active" : ""}`} to={to}>
      {label}
    </Link>
  );
}

function SiteHeader() {
  const { user, logout } = useAuth();
  return (
    <header className="site-header">
      <Link to="/" className="brand">TradeIQ</Link>
      <nav className="site-nav">
        <NavLink to="/" label="Home" />
        <NavLink to="/about" label="About" />
        <NavLink to="/contact" label="Contact" />
        <NavLink to="/dashboard" label="Dashboard" />
      </nav>
      <div className="site-auth">
        {user ? (
          <>
            <span className="user-chip">{user.full_name || user.username}</span>
            <button className="btn-ghost" onClick={logout}>Logout</button>
          </>
        ) : (
          <>
            <Link className="btn-ghost" to="/login">Login</Link>
            <Link className="btn-primary" to="/register">Sign Up</Link>
          </>
        )}
      </div>
    </header>
  );
}

export default function App() {
  return (
    <>
      <SiteHeader />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/dashboard"
          element={(
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          )}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
