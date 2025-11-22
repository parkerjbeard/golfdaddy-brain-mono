/**
 * Comprehensive token management with automatic refresh and secure storage
 */

// Lightweight interface previously imported from the removed enhanced API client
export interface TokenManager {
  getToken(): Promise<string | null>;
  refreshToken(): Promise<string | null>;
  clearToken(): Promise<void>;
  onTokenRefresh(callback: (token: string) => void): void;
  onTokenExpired(callback: () => void): void;
}

import { LoginResponse, RefreshTokenResponse } from '@/types/api';
import { secureStorage } from '@/services/secureStorage';
import { tokenCleanupService, TokenCleanupService } from '@/services/tokenCleanupService';

export interface TokenData {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
  expiresAt: number;
  version?: number; // Token version for rotation tracking
  issuedAt?: number; // When the token was issued
  rotationCount?: number; // Number of times this token has been rotated
}

export interface TokenManagerConfig {
  storageKey: string;
  refreshThreshold: number; // Refresh when this many minutes remain
  maxRetries: number;
  autoRefresh: boolean;
  secureStorage: boolean;
}

const DEFAULT_CONFIG: TokenManagerConfig = {
  storageKey: 'golf_daddy_auth_tokens',
  refreshThreshold: 5 * 60 * 1000, // 5 minutes in milliseconds
  maxRetries: 3,
  autoRefresh: true,
  secureStorage: true,
};

export class GolfDaddyTokenManager implements TokenManager {
  private config: TokenManagerConfig;
  private tokenData: TokenData | null = null;
  private refreshPromise: Promise<string | null> | null = null;
  private refreshCallbacks: Array<(token: string) => void> = [];
  private expiredCallbacks: Array<() => void> = [];
  private refreshTimer: NodeJS.Timeout | null = null;
  private tokenVersion = 1; // Current token version

  constructor(config?: Partial<TokenManagerConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    // Load token asynchronously on initialization
    this.initialize();
  }

  private async initialize(): Promise<void> {
    await this.loadTokenFromStorage();
    this.setupAutoRefresh();
  }

  // ========== PUBLIC METHODS ==========

  async getToken(): Promise<string | null> {
    if (!this.tokenData) {
      return null;
    }

    // Check if token is expired
    if (this.isTokenExpired()) {
      console.warn('Token is expired, attempting refresh...');
      return this.refreshToken();
    }

    // Check if token needs refresh soon
    if (this.shouldRefreshToken() && this.config.autoRefresh) {
      console.log('Token needs refresh, refreshing proactively...');
      // Start refresh but return current token immediately
      this.refreshToken();
    }

    return this.tokenData.accessToken;
  }

  async refreshToken(): Promise<string | null> {
    // Prevent multiple simultaneous refresh attempts
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    if (!this.tokenData?.refreshToken) {
      this.handleTokenExpired();
      return null;
    }

    this.refreshPromise = this.executeTokenRefresh();
    
    try {
      const token = await this.refreshPromise;
      return token;
    } finally {
      this.refreshPromise = null;
    }
  }

  async clearToken(): Promise<void> {
    this.tokenData = null;
    await this.clearStorage();
    this.clearRefreshTimer();
    
    // Notify callbacks
    this.expiredCallbacks.forEach(callback => callback());
  }

  async setTokenData(loginResponse: LoginResponse): Promise<void> {
    const now = Date.now();
    this.tokenData = {
      accessToken: loginResponse.access_token,
      refreshToken: loginResponse.refresh_token,
      tokenType: loginResponse.token_type,
      expiresIn: loginResponse.expires_in,
      expiresAt: now + (loginResponse.expires_in * 1000),
      version: this.tokenVersion,
      issuedAt: now,
      rotationCount: 0,
    };

    await this.saveTokenToStorage();
    this.setupAutoRefresh();
    
    // Notify callbacks
    this.refreshCallbacks.forEach(callback => callback(this.tokenData!.accessToken));
  }

  // Simple method for setting a token directly (useful for bypass mode)
  async setToken(token: string): Promise<void> {
    const now = Date.now();
    this.tokenData = {
      accessToken: token,
      refreshToken: token,
      tokenType: 'Bearer',
      expiresIn: 86400, // 24 hours
      expiresAt: now + (86400 * 1000),
      version: this.tokenVersion,
      issuedAt: now,
      rotationCount: 0,
    };
    await this.saveTokenToStorage();
  }

  onTokenRefresh(callback: (token: string) => void): void {
    this.refreshCallbacks.push(callback);
  }

  onTokenExpired(callback: () => void): void {
    this.expiredCallbacks.push(callback);
  }

  // ========== TOKEN VALIDATION ==========

  isTokenExpired(): boolean {
    if (!this.tokenData) return true;
    return Date.now() >= this.tokenData.expiresAt;
  }

  shouldRefreshToken(): boolean {
    if (!this.tokenData) return false;
    const timeUntilExpiry = this.tokenData.expiresAt - Date.now();
    return timeUntilExpiry <= this.config.refreshThreshold;
  }

  getTokenExpiry(): Date | null {
    if (!this.tokenData) return null;
    return new Date(this.tokenData.expiresAt);
  }

  getTimeUntilExpiry(): number {
    if (!this.tokenData) return 0;
    return Math.max(0, this.tokenData.expiresAt - Date.now());
  }

  // ========== REFRESH IMPLEMENTATION ==========

  private async executeTokenRefresh(): Promise<string | null> {
    if (!this.tokenData?.refreshToken) {
      this.handleTokenExpired();
      return null;
    }

    let attempt = 0;
    let lastError: Error | null = null;

    while (attempt < this.config.maxRetries) {
      try {
        const response = await this.callRefreshEndpoint(this.tokenData.refreshToken);
        
        // Update token data with rotation tracking
        const now = Date.now();
        const previousRotationCount = this.tokenData.rotationCount || 0;
        
        this.tokenData = {
          accessToken: response.access_token,
          refreshToken: response.refresh_token,
          tokenType: response.token_type,
          expiresIn: response.expires_in,
          expiresAt: now + (response.expires_in * 1000),
          version: this.tokenVersion,
          issuedAt: now,
          rotationCount: previousRotationCount + 1,
        };

        await this.saveTokenToStorage();
        this.setupAutoRefresh();
        
        // Notify callbacks
        this.refreshCallbacks.forEach(callback => callback(this.tokenData!.accessToken));
        
        console.log('Token refreshed successfully');
        return this.tokenData.accessToken;
      } catch (error) {
        lastError = error as Error;
        attempt++;
        
        console.warn(`Token refresh attempt ${attempt} failed:`, error);
        
        if (attempt < this.config.maxRetries) {
          // Wait before retry with exponential backoff
          const delay = Math.pow(2, attempt) * 1000;
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    console.error('All token refresh attempts failed:', lastError);
    this.handleTokenExpired();
    return null;
  }

  private async callRefreshEndpoint(refreshToken: string): Promise<RefreshTokenResponse> {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        refresh_token: refreshToken,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error?.message || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  // ========== AUTO REFRESH ==========

  private setupAutoRefresh(): void {
    this.clearRefreshTimer();
    
    if (!this.config.autoRefresh || !this.tokenData) {
      return;
    }

    const timeUntilRefresh = Math.max(
      0,
      this.tokenData.expiresAt - Date.now() - this.config.refreshThreshold
    );

    this.refreshTimer = setTimeout(() => {
      console.log('Auto-refreshing token...');
      this.refreshToken();
    }, timeUntilRefresh);
  }

  private clearRefreshTimer(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  // ========== STORAGE ==========

  private async saveTokenToStorage(): Promise<void> {
    if (!this.tokenData) return;

    try {
      if (this.config.secureStorage) {
        // Use secure storage with encryption
        await secureStorage.setItem(this.config.storageKey, this.tokenData, {
          expiresIn: this.tokenData.expiresIn * 1000, // Convert to milliseconds
          tags: ['auth', 'token'],
        });
      } else {
        // Fallback to regular localStorage (not recommended for production)
        console.warn('Using unencrypted localStorage for tokens. Enable secureStorage for production.');
        localStorage.setItem(this.config.storageKey, JSON.stringify(this.tokenData));
      }
    } catch (error) {
      console.error('Failed to save token to storage:', error);
      // If secure storage fails, don't fall back to insecure storage
      if (this.config.secureStorage) {
        throw error;
      }
    }
  }

  private async loadTokenFromStorage(): Promise<void> {
    try {
      let tokenData: TokenData | null = null;

      if (this.config.secureStorage) {
        // Try to load from secure storage
        tokenData = await secureStorage.getItem<TokenData>(this.config.storageKey);
      } else {
        // Fallback to regular localStorage
        const data = localStorage.getItem(this.config.storageKey);
        if (data) {
          tokenData = JSON.parse(data) as TokenData;
        }
      }

      if (!tokenData) return;
      
      // Validate token structure
      if (this.isValidTokenData(tokenData)) {
        this.tokenData = tokenData;
        
        // Check if token is already expired
        if (this.isTokenExpired()) {
          console.warn('Loaded token is expired, clearing storage');
          await this.clearToken();
        }
      } else {
        console.warn('Invalid token data in storage, clearing');
        await this.clearStorage();
      }
    } catch (error) {
      console.error('Failed to load token from storage:', error);
      await this.clearStorage();
    }
  }

  private async clearStorage(): Promise<void> {
    try {
      if (this.config.secureStorage) {
        await secureStorage.removeItem(this.config.storageKey);
      } else {
        localStorage.removeItem(this.config.storageKey);
      }
    } catch (error) {
      console.error('Failed to clear token storage:', error);
    }
  }

  private isValidTokenData(data: any): data is TokenData {
    return (
      data &&
      typeof data.accessToken === 'string' &&
      typeof data.refreshToken === 'string' &&
      typeof data.tokenType === 'string' &&
      typeof data.expiresIn === 'number' &&
      typeof data.expiresAt === 'number'
    );
  }

  // ========== EVENT HANDLING ==========

  private async handleTokenExpired(): Promise<void> {
    console.warn('Token expired, clearing authentication state');
    await this.clearToken();
    
    // Emit global event for other parts of the app
    window.dispatchEvent(new CustomEvent('auth-token-expired'));
    
    // Trigger token cleanup
    TokenCleanupService.triggerLogout();
  }

  // ========== DEBUG METHODS ==========

  getDebugInfo(): {
    hasToken: boolean;
    isExpired: boolean;
    shouldRefresh: boolean;
    expiresAt: string | null;
    timeUntilExpiry: string;
  } {
    return {
      hasToken: !!this.tokenData,
      isExpired: this.isTokenExpired(),
      shouldRefresh: this.shouldRefreshToken(),
      expiresAt: this.getTokenExpiry()?.toISOString() || null,
      timeUntilExpiry: `${Math.round(this.getTimeUntilExpiry() / 1000)}s`,
    };
  }

  // ========== CLEANUP ==========

  destroy(): void {
    this.clearRefreshTimer();
    this.refreshCallbacks = [];
    this.expiredCallbacks = [];
  }
}

// ========== SINGLETON INSTANCE ==========

export const tokenManager = new GolfDaddyTokenManager();

// Setup global event listeners
window.addEventListener('beforeunload', () => {
  tokenManager.destroy();
});

// Listen for online/offline events to handle token refresh
window.addEventListener('online', () => {
  if (tokenManager.shouldRefreshToken()) {
    console.log('Back online, checking token status...');
    tokenManager.refreshToken();
  }
});

export default tokenManager;
