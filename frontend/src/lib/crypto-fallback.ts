/**
 * Development fallback for Web Crypto API
 * This provides a non-secure implementation for development environments
 */

import { EncryptedData } from './crypto';

export class CryptoFallback {
  async encrypt(plaintext: string): Promise<EncryptedData> {
    console.warn('Using fallback encryption (NOT SECURE) - for development only');
    
    // Simple base64 encoding for development
    const encoded = btoa(plaintext);
    
    return {
      version: 1,
      data: encoded,
      iv: 'dev_iv',
      salt: 'dev_salt',
    };
  }

  async decrypt(encryptedData: EncryptedData): Promise<string> {
    console.warn('Using fallback decryption (NOT SECURE) - for development only');
    
    try {
      // Simple base64 decoding for development
      return atob(encryptedData.data);
    } catch (error) {
      throw new Error('Failed to decrypt data with fallback');
    }
  }

  clearMasterKey(): void {
    // No-op in fallback
  }

  generateSecureRandom(length: number = 32): string {
    // Simple random for development
    return Array.from({ length }, () => 
      Math.floor(Math.random() * 16).toString(16)
    ).join('');
  }
}