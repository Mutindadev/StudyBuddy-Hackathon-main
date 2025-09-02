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

  // Helper for API calls
  const apiCall = async (endpoint, options = {}) => {
    const url = `${API_BASE_URL}${endpoint}`;
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

      // Handle 401 separately
      if (response.status === 401) {
        localStorage.removeItem("token");
        setToken(null);
        setUser(null);
        throw new Error("Invalid token. Please log in again.");
      }

      // Try parsing JSON safely
      let data = null;
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        data = await response.json();
      }

      if (!response.ok) {
        throw new Error(
          data?.error || `HTTP error! status: ${response.status}`
        );
      }

      return data;
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
        const data = await apiCall("/api/uth/verify-token", {
          method: "POST",
        });
        if (!data?.user) {
          localStorage.removeItem("token");
          setToken(null);
          setUser(null);
          throw new Error("Invalid token. Please log in again.");
        }

        const verifiedUser = Array.isArray(data.user)
          ? data.user[0]
          : data.user;
        setUser(verifiedUser);
      } catch (error) {
        console.error("Token verification failed:", error);
      } finally {
        setLoading(false);
      }
    };

    verifyToken();
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
