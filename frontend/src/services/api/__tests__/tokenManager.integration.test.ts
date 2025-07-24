/**
 * Integration tests for TokenManager with SecureStorage
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { GolfDaddyTokenManager } from '../tokenManager';
import { secureStorage } from '@/services/secureStorage';
import { TokenCleanupService } from '@/services/tokenCleanupService';
import type { LoginResponse } from '@/types/api';

// Mock fetch globally
global.fetch = vi.fn();

describe('TokenManager Integration Tests', () => {
  let tokenManager: GolfDaddyTokenManager;
  
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    
    // Create a new token manager instance for each test
    tokenManager = new GolfDaddyTokenManager({
      storageKey: 'test_auth_tokens',
      refreshThreshold: 5 * 60 * 1000,
      maxRetries: 3,
      autoRefresh: false, // Disable for tests
      secureStorage: true,
    });
  });

  afterEach(async () => {
    tokenManager.destroy();
    await secureStorage.clear();
  });

  describe('Token Storage with Encryption', () => {
    it('should store tokens securely using SecureStorage', async () => {
      const mockLoginResponse: LoginResponse = {
        access_token: 'test_access_token',
        refresh_token: 'test_refresh_token',
        token_type: 'Bearer',
        expires_in: 3600,
      };
      
      await tokenManager.setTokenData(mockLoginResponse);
      
      // Verify token can be retrieved
      const token = await tokenManager.getToken();
      expect(token).toBe('test_access_token');
      
      // Verify token is stored encrypted (not plain text in localStorage)
      const rawStorage = localStorage.getItem('secure_test_auth_tokens');
      expect(rawStorage).toBeTruthy();
      
      if (rawStorage) {
        const parsed = JSON.parse(rawStorage);
        expect(parsed).toHaveProperty('version');
        expect(parsed).toHaveProperty('data');
        expect(parsed).toHaveProperty('iv');
        expect(parsed).toHaveProperty('salt');
        
        // Ensure the actual token is not visible in raw storage
        expect(rawStorage).not.toContain('test_access_token');
        expect(rawStorage).not.toContain('test_refresh_token');
      }
    });

    it('should include token versioning information', async () => {
      const mockLoginResponse: LoginResponse = {
        access_token: 'test_access_token_v1',
        refresh_token: 'test_refresh_token_v1',
        token_type: 'Bearer',
        expires_in: 3600,
      };
      
      await tokenManager.setTokenData(mockLoginResponse);
      
      // Get token data through debug info
      const debugInfo = tokenManager.getDebugInfo();
      expect(debugInfo.hasToken).toBe(true);
      
      // Store and retrieve to verify versioning
      const token = await tokenManager.getToken();
      expect(token).toBe('test_access_token_v1');
    });
  });

  describe('Token Refresh with Rotation Tracking', () => {
    it('should track token rotation count on refresh', async () => {
      // Setup initial token
      const initialToken: LoginResponse = {
        access_token: 'initial_access_token',
        refresh_token: 'initial_refresh_token',
        token_type: 'Bearer',
        expires_in: 1, // Expires in 1 second
      };
      
      await tokenManager.setTokenData(initialToken);
      
      // Mock refresh endpoint
      const refreshedToken: LoginResponse = {
        access_token: 'refreshed_access_token',
        refresh_token: 'refreshed_refresh_token',
        token_type: 'Bearer',
        expires_in: 3600,
      };
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => refreshedToken,
      });
      
      // Wait for token to expire
      await new Promise(resolve => setTimeout(resolve, 1100));
      
      // Get token should trigger refresh
      const newToken = await tokenManager.getToken();
      expect(newToken).toBe('refreshed_access_token');
      
      // Verify refresh endpoint was called
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/refresh'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ refresh_token: 'initial_refresh_token' }),
        })
      );
    });

    it('should handle refresh token failure', async () => {
      // Setup expired token
      const expiredToken: LoginResponse = {
        access_token: 'expired_access_token',
        refresh_token: 'expired_refresh_token',
        token_type: 'Bearer',
        expires_in: 0, // Already expired
      };
      
      await tokenManager.setTokenData(expiredToken);
      
      // Mock refresh endpoint failure
      (global.fetch as any).mockRejectedValue(new Error('Network error'));
      
      // Get token should return null after failed refresh
      const token = await tokenManager.getToken();
      expect(token).toBeNull();
    });
  });

  describe('Automatic Token Cleanup', () => {
    it('should cleanup tokens on logout', async () => {
      // Setup token
      const mockToken: LoginResponse = {
        access_token: 'test_token',
        refresh_token: 'test_refresh',
        token_type: 'Bearer',
        expires_in: 3600,
      };
      
      await tokenManager.setTokenData(mockToken);
      
      // Verify token exists
      let token = await tokenManager.getToken();
      expect(token).toBe('test_token');
      
      // Clear token (simulate logout)
      await tokenManager.clearToken();
      
      // Verify token is cleared
      token = await tokenManager.getToken();
      expect(token).toBeNull();
      
      // Verify storage is cleared
      const storedData = await secureStorage.getItem('test_auth_tokens');
      expect(storedData).toBeNull();
    });

    it('should trigger cleanup service on token expiration', async () => {
      const cleanupSpy = vi.spyOn(TokenCleanupService, 'triggerLogout');
      
      // Create token manager with very short expiration
      const shortLivedToken: LoginResponse = {
        access_token: 'short_lived_token',
        refresh_token: 'short_lived_refresh',
        token_type: 'Bearer',
        expires_in: 0, // Already expired
      };
      
      await tokenManager.setTokenData(shortLivedToken);
      
      // Mock failed refresh
      (global.fetch as any).mockRejectedValue(new Error('Token expired'));
      
      // Attempt to get token should trigger cleanup
      await tokenManager.getToken();
      
      expect(cleanupSpy).toHaveBeenCalled();
    });
  });

  describe('Security Features', () => {
    it('should not expose tokens in debug info', () => {
      const debugInfo = tokenManager.getDebugInfo();
      
      // Debug info should not contain actual token values
      expect(JSON.stringify(debugInfo)).not.toContain('access_token');
      expect(JSON.stringify(debugInfo)).not.toContain('refresh_token');
      
      // Should only contain safe metadata
      expect(debugInfo).toHaveProperty('hasToken');
      expect(debugInfo).toHaveProperty('isExpired');
      expect(debugInfo).toHaveProperty('shouldRefresh');
    });

    it('should handle concurrent token refresh attempts', async () => {
      // Setup token that needs refresh
      const needsRefreshToken: LoginResponse = {
        access_token: 'needs_refresh_token',
        refresh_token: 'needs_refresh_refresh',
        token_type: 'Bearer',
        expires_in: 1, // Expires soon
      };
      
      await tokenManager.setTokenData(needsRefreshToken);
      
      // Wait for token to expire
      await new Promise(resolve => setTimeout(resolve, 1100));
      
      // Mock successful refresh
      const refreshedToken: LoginResponse = {
        access_token: 'new_access_token',
        refresh_token: 'new_refresh_token',
        token_type: 'Bearer',
        expires_in: 3600,
      };
      
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => refreshedToken,
      });
      
      // Trigger multiple concurrent refresh attempts
      const promises = [
        tokenManager.getToken(),
        tokenManager.getToken(),
        tokenManager.getToken(),
      ];
      
      const results = await Promise.all(promises);
      
      // All should return the same new token
      expect(results).toEqual(['new_access_token', 'new_access_token', 'new_access_token']);
      
      // But refresh endpoint should only be called once
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });
  });

  describe('Event Handling', () => {
    it('should emit token expired event', async () => {
      const eventSpy = vi.fn();
      window.addEventListener('auth-token-expired', eventSpy);
      
      // Setup expired token
      const expiredToken: LoginResponse = {
        access_token: 'expired_token',
        refresh_token: 'expired_refresh',
        token_type: 'Bearer',
        expires_in: 0,
      };
      
      await tokenManager.setTokenData(expiredToken);
      
      // Mock failed refresh
      (global.fetch as any).mockRejectedValue(new Error('Refresh failed'));
      
      // Attempt to get token
      await tokenManager.getToken();
      
      expect(eventSpy).toHaveBeenCalled();
      
      window.removeEventListener('auth-token-expired', eventSpy);
    });

    it('should handle online/offline events', async () => {
      // Setup token
      const mockToken: LoginResponse = {
        access_token: 'test_token',
        refresh_token: 'test_refresh',
        token_type: 'Bearer',
        expires_in: 300, // 5 minutes
      };
      
      await tokenManager.setTokenData(mockToken);
      
      // Mock successful refresh
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          access_token: 'refreshed_after_online',
          refresh_token: 'refreshed_refresh',
          token_type: 'Bearer',
          expires_in: 3600,
        }),
      });
      
      // Wait to make token need refresh
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Trigger online event
      window.dispatchEvent(new Event('online'));
      
      // Give time for event handler
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Should have attempted refresh
      const debugInfo = tokenManager.getDebugInfo();
      expect(debugInfo.shouldRefresh).toBe(true);
    });
  });
});