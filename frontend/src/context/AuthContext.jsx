import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

const API_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8001";

const AuthContext = createContext(null);

function normalizeUser(payload) {
  if (!payload) {
    return null;
  }

  return (
    payload.user ||
    payload.data?.user ||
    payload.profile ||
    payload.data ||
    null
  );
}

async function parseResponse(response) {
  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message =
      data?.detail ||
      data?.message ||
      data?.error ||
      "Authentication request failed.";

    const error = new Error(message);
    error.status = response.status;
    error.data = data;

    throw error;
  }

  return data;
}

export function AuthProvider({
  children,
}) {
  const [user, setUser] =
    useState(null);

  const [isLoading, setIsLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  const isAuthenticated = Boolean(user);

  const logout = useCallback(
    async () => {
      try {
        await fetch(
          `${API_URL}/api/auth/logout`,
          {
            method: "POST",
            credentials: "include",
          }
        );
      } catch {
        // The in-memory auth state is still cleared below.
      } finally {
        setUser(null);
        setError("");
      }
    },
    []
  );

  const loadCurrentUser =
    useCallback(
      async () => {
        try {
          setIsLoading(true);
          setError("");

          const response =
            await fetch(
              `${API_URL}/api/auth/me`,
              {
                method: "GET",
                credentials: "include",
              }
            );

          const data =
            await parseResponse(response);

          const currentUser =
            normalizeUser(data);

          if (!currentUser) {
            throw new Error(
              "Authenticated user profile could not be loaded."
            );
          }

          setUser(currentUser);
        } catch (requestError) {
          setUser(null);

          if (requestError?.status !== 401) {
            setError(
              requestError?.message ||
                "Unable to verify the authentication session."
            );
          }
        } finally {
          setIsLoading(false);
        }
      },
      []
    );

  useEffect(() => {
    loadCurrentUser();
  }, [loadCurrentUser]);

  const login = useCallback(
    async ({
      email,
      password,
      rememberMe = false,
    }) => {
      setError("");

      try {
        setIsLoading(true);

        const response =
          await fetch(
            `${API_URL}/api/auth/login`,
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              credentials: "include",
              body: JSON.stringify({
                email,
                password,
                remember_me:
                  rememberMe,
              }),
            }
          );

        const data =
          await parseResponse(response);

        const authenticatedUser =
          normalizeUser(data);

        if (authenticatedUser) {
          setUser(authenticatedUser);
        } else {
          const meResponse =
            await fetch(
              `${API_URL}/api/auth/me`,
              {
                method: "GET",
                credentials: "include",
              }
            );

          const meData =
            await parseResponse(
              meResponse
            );

          const currentUser =
            normalizeUser(meData);

          if (!currentUser) {
            throw new Error(
              "Unable to load the authenticated user."
            );
          }

          setUser(currentUser);
        }

        return {
          success: true,
          user: authenticatedUser,
          data,
        };
      } catch (requestError) {
        setUser(null);

        const message =
          requestError?.message ||
          "Invalid email or password.";

        setError(message);

        return {
          success: false,
          error: message,
          status:
            requestError?.status ||
            null,
        };
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const register = useCallback(
    async ({
      email,
      password,
    }) => {
      setError("");

      try {
        setIsLoading(true);

        const response =
          await fetch(
            `${API_URL}/api/auth/register`,
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              credentials: "include",
              body: JSON.stringify({
                email,
                password,
              }),
            }
          );

        const data =
          await parseResponse(response);

        const registeredUser =
          normalizeUser(data);

        if (registeredUser) {
          setUser(registeredUser);
        } else {
          await loadCurrentUser();
        }

        return {
          success: true,
          user: registeredUser,
          data,
        };
      } catch (requestError) {
        const message =
          requestError?.message ||
          "Unable to create the account.";

        setError(message);

        return {
          success: false,
          error: message,
          status:
            requestError?.status ||
            null,
        };
      } finally {
        setIsLoading(false);
      }
    },
    [loadCurrentUser]
  );

  const clearError =
    useCallback(() => {
      setError("");
    }, []);

  const value =
    useMemo(
      () => ({
        user,
        isAuthenticated,
        isLoading,
        error,
        login,
        register,
        logout,
        clearError,
        refreshUser:
          loadCurrentUser,
      }),
      [
        user,
        isAuthenticated,
        isLoading,
        error,
        login,
        register,
        logout,
        clearError,
        loadCurrentUser,
      ]
    );

  return (
    <AuthContext.Provider
      value={value}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context =
    useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider."
    );
  }

  return context;
}

export default AuthContext;
