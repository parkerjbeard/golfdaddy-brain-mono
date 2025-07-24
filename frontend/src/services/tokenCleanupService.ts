/**
 * Token cleanup service for automatic removal of authentication tokens on logout
 */

import { secureStorage } from './secureStorage';

/**
 * Token cleanup service to handle automatic cleanup of authentication data
 */
export class TokenCleanupService {
  private static instance: TokenCleanupService;
  private cleanupCallbacks: Array<() => Promise<void>> = [];

  private constructor() {
    // Register global event listeners
    this.registerEventListeners();
  }

  /**
   * Get singleton instance
   */
  static getInstance(): TokenCleanupService {
    if (!TokenCleanupService.instance) {
      TokenCleanupService.instance = new TokenCleanupService();
    }
    return TokenCleanupService.instance;
  }

  /**
   * Register a cleanup callback
   */
  registerCleanupCallback(callback: () => Promise<void>): void {
    this.cleanupCallbacks.push(callback);
  }

  /**
   * Remove a cleanup callback
   */
  unregisterCleanupCallback(callback: () => Promise<void>): void {
    this.cleanupCallbacks = this.cleanupCallbacks.filter(cb => cb !== callback);
  }

  /**
   * Perform complete authentication cleanup
   */
  async performCleanup(): Promise<void> {
    console.log('Performing authentication cleanup...');
    
    try {
      // Clear all auth-related items from secure storage
      await secureStorage.removeItemsByTag('auth');
      
      // Clear specific known auth keys
      const authKeys = [
        'golf_daddy_auth_tokens',
        'userProfile',
        'rememberMe',
        'token', // Legacy key
        'authToken', // Legacy key
      ];
      
      await Promise.all(
        authKeys.map(key => secureStorage.removeItem(key))
      );
      
      // Execute all registered cleanup callbacks
      await Promise.all(
        this.cleanupCallbacks.map(callback => 
          callback().catch(error => 
            console.error('Cleanup callback error:', error)
          )
        )
      );
      
      // Clear crypto master key
      const { cryptoUtils } = await import('@/lib/crypto');
      cryptoUtils.clearMasterKey();
      
      console.log('Authentication cleanup completed');
    } catch (error) {
      console.error('Error during authentication cleanup:', error);
      // Don't throw - we want cleanup to be best effort
    }
  }

  /**
   * Register event listeners for automatic cleanup
   */
  private registerEventListeners(): void {
    // Listen for custom logout event
    window.addEventListener('auth-logout', () => {
      // Don't await here to avoid blocking the event
      this.performCleanup().catch(error => 
        console.error('Error during auth-logout cleanup:', error)
      );
    });

    // Listen for storage clear event
    window.addEventListener('storage', (event) => {
      // If storage is cleared from another tab, cleanup here too
      if (event.key === null && event.newValue === null) {
        this.performCleanup().catch(error => 
          console.error('Error during storage cleanup:', error)
        );
      }
    });

    // Cleanup on token expiration
    window.addEventListener('auth-token-expired', () => {
      this.performCleanup().catch(error => 
        console.error('Error during token-expired cleanup:', error)
      );
    });
  }

  /**
   * Trigger logout event (to be called by auth services)
   */
  static triggerLogout(): void {
    window.dispatchEvent(new CustomEvent('auth-logout'));
  }
}

// Export singleton instance
export const tokenCleanupService = TokenCleanupService.getInstance();