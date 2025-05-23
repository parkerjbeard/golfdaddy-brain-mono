import { useState, useEffect } from 'react';

interface TokenManager {
  getToken: () => string | null;
  setToken: (token: string | null) => void;
  removeToken: () => void;
  isTokenExpired: (token: string) => boolean;
  getTokenExpirationTime: (token: string) => number | null;
}

const TOKEN_STORAGE_KEY = 'golf_daddy_auth_token';
const TOKEN_REFRESH_THRESHOLD = 5 * 60 * 1000; // 5 minutes before expiration

export const useAuthToken = (): TokenManager => {
  const [token, setTokenState] = useState<string | null>(() => {
    // Initialize from localStorage on mount
    try {
      return localStorage.getItem(TOKEN_STORAGE_KEY);
    } catch (error) {
      console.warn('Failed to read token from localStorage:', error);
      return null;
    }
  });

  // Parse JWT payload to extract expiration
  const parseJWT = (token: string) => {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('Error parsing JWT token:', error);
      return null;
    }
  };

  const isTokenExpired = (token: string): boolean => {
    const payload = parseJWT(token);
    if (!payload || !payload.exp) {
      return true;
    }
    
    const expirationTime = payload.exp * 1000; // Convert to milliseconds
    const currentTime = Date.now();
    
    return currentTime >= expirationTime;
  };

  const getTokenExpirationTime = (token: string): number | null => {
    const payload = parseJWT(token);
    if (!payload || !payload.exp) {
      return null;
    }
    
    return payload.exp * 1000; // Convert to milliseconds
  };

  const shouldRefreshToken = (token: string): boolean => {
    const expirationTime = getTokenExpirationTime(token);
    if (!expirationTime) {
      return false;
    }
    
    const currentTime = Date.now();
    return (expirationTime - currentTime) <= TOKEN_REFRESH_THRESHOLD;
  };

  const setToken = (newToken: string | null) => {
    setTokenState(newToken);
    
    if (newToken) {
      try {
        localStorage.setItem(TOKEN_STORAGE_KEY, newToken);
      } catch (error) {
        console.warn('Failed to save token to localStorage:', error);
      }
    } else {
      try {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      } catch (error) {
        console.warn('Failed to remove token from localStorage:', error);
      }
    }
  };

  const getToken = (): string | null => {
    return token;
  };

  const removeToken = () => {
    setToken(null);
  };

  // Effect to check token expiration periodically
  useEffect(() => {
    if (!token) return;

    const checkTokenExpiration = () => {
      if (isTokenExpired(token)) {
        console.warn('Token has expired, removing from storage');
        removeToken();
        return;
      }

      if (shouldRefreshToken(token)) {
        console.info('Token should be refreshed soon');
        // Emit a custom event that the auth system can listen to
        window.dispatchEvent(new CustomEvent('token-refresh-needed'));
      }
    };

    // Check immediately
    checkTokenExpiration();

    // Set up periodic checking (every minute)
    const intervalId = setInterval(checkTokenExpiration, 60 * 1000);

    return () => clearInterval(intervalId);
  }, [token]);

  return {
    getToken,
    setToken,
    removeToken,
    isTokenExpired,
    getTokenExpirationTime,
  };
};