import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

export default function ProtectedRoute({
  children,
}) {
  const {
    isAuthenticated,
    isLoading,
  } = useAuth();

  const location = useLocation();

  if (isLoading) {
    return (
      <main
        className="nova-auth-page"
        aria-busy="true"
        aria-label="Loading NOVA"
      >
        <div className="nova-auth-loading">
          <span className="nova-auth-loading-mark">
            NOVA
          </span>

          <span className="nova-auth-loader" />

          <span className="nova-auth-loading-text">
            VERIFYING SESSION
          </span>
        </div>
      </main>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location,
        }}
      />
    );
  }

  return children;
}