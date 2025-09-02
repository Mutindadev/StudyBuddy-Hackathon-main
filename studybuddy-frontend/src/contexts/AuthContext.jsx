import React, { createContext, useContext, useState, useEffect } from "react";
import { toast } from "sonner";

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
};

const API_BASE_URL = import.meta.env.VITE_API_URL;

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [loading, setLoading] = useState(true);

  // Helper for API calls (robust: normalizes urls, handles 401, JSON vs non-JSON, 204)
  const apiCall = async (endpoint, options = {}) => {
    // Normalize base URL (remove trailing slash)
    const base = (API_BASE_URL || "").replace(/\/+$/, "");

    // Normalize endpoint to always start with a single leading slash
    let ep = String(endpoint || "");
    if (!ep.startsWith("/")) ep = "/" + ep;

    // Final URL: if no base provided, use endpoint as absolute path
    const url = base ? `${base}${ep}` : ep;

    const config = {
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      // 401: invalid/expired token -> clear auth and throw
      if (response.status === 401) {
        localStorage.removeItem("token");
        setToken(null);
        setUser(null);
        throw new Error("Invalid token. Please log in again.");
      }

      // 204 No Content -> return null (caller should handle)
      if (response.status === 204) return null;

      // Check content-type to decide how to parse
      const contentType = (
        response.headers.get("content-type") || ""
      ).toLowerCase();

      if (contentType.includes("application/json")) {
        const data = await response.json();
        if (!response.ok) {
          throw new Error(
            data?.error || `HTTP error! status: ${response.status}`
          );
        }
        return data;
      } else {
        // Non-JSON response: read text and surface useful message or return text on OK
        const text = await response.text();
        if (!response.ok) {
          throw new Error(text || `HTTP error! status: ${response.status}`);
        }
        return text;
      }
    } catch (error) {
      console.error("API call failed:", error);
      throw error;
    }
  };

  // Verify token on load
  useEffect(() => {
    const verifyToken = async () => {
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const data = await apiCall("/api/auth/verify-token", {
          method: "POST",
        });

        if (!data?.user) {
          // invalid or empty response -> clear auth
          localStorage.removeItem("token");
          setToken(null);
          setUser(null);
          throw new Error("Please log in again.");
        }

        const verifiedUser = Array.isArray(data.user)
          ? data.user[0]
          : data.user;
        setUser(verifiedUser);
      } catch (error) {
        console.error("Token verification failed:", error);
        // Ensure invalid token is removed and state cleared
        localStorage.removeItem("token");
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    verifyToken();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const login = async (email, password) => {
    try {
      const data = await apiCall("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      const loggedInUser = Array.isArray(data?.user) ? data.user[0] : data.user;
      setToken(data.token);
      setUser(loggedInUser);
      localStorage.setItem("token", data.token);
      toast.success("Login successful!");
      return { success: true };
    } catch (error) {
      toast.error(error.message);
      return { success: false, error: error.message };
    }
  };

  const register = async (userData) => {
    try {
      const data = await apiCall("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(userData),
      });

      const newUser = Array.isArray(data?.user) ? data.user[0] : data.user;
      setToken(data.token);
      setUser(newUser);
      localStorage.setItem("token", data.token);
      toast.success("Registration successful!");
      return { success: true };
    } catch (error) {
      toast.error(error.message);
      return { success: false, error: error.message };
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("token");
    toast.success("Logged out successfully");
  };

  const updateUser = (userData) => {
    setUser((prev) => ({ ...prev, ...userData }));
  };

  const value = {
    user,
    token,
    loading,
    login,
    register,
    logout,
    updateUser,
    apiCall,
    isAuthenticated: !!token && !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
