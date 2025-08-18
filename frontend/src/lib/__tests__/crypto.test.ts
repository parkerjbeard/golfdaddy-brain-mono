/**
 * Unit tests for Crypto utilities
 */

import { describe, it, expect, beforeEach, vi, Mock } from 'vitest';
import { CryptoUtils, cryptoUtils } from '../crypto';

describe('CryptoUtils', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset the singleton instance
    cryptoUtils.clearMasterKey();
  });

  describe('isSupported', () => {
    it('should return true when Web Crypto API is available', () => {
      expect(CryptoUtils.isSupported()).toBe(true);
    });

    it('should return false when Web Crypto API is not available', () => {
      const originalCrypto = window.crypto;
      // @ts-ignore - Temporarily remove crypto
      delete window.crypto;
      
      expect(CryptoUtils.isSupported()).toBe(false);
      
      // Restore
      window.crypto = originalCrypto;
    });
  });

  describe('encrypt and decrypt', () => {
    it('should encrypt and decrypt data successfully', async () => {
      const plaintext = 'This is a secret message';
      
      // Mock the crypto.subtle methods
      const encryptedData = new ArrayBuffer(32);
      const mockIv = new Uint8Array(12);
      const mockSalt = new Uint8Array(16);
      
      (window.crypto.getRandomValues as Mock) = vi.fn((array: Uint8Array) => {
        if (array.length === 12) {
          array.set(mockIv);
        } else if (array.length === 16) {
          array.set(mockSalt);
        }
        return array;
      });
      
      (window.crypto.subtle.importKey as Mock) = vi.fn().mockResolvedValue('mockPasswordKey');
      (window.crypto.subtle.deriveKey as Mock) = vi.fn().mockResolvedValue('mockDerivedKey');
      (window.crypto.subtle.encrypt as Mock) = vi.fn().mockResolvedValue(encryptedData);
      (window.crypto.subtle.decrypt as Mock) = vi.fn().mockResolvedValue(
        new TextEncoder().encode(plaintext).buffer
      );
      
      // Encrypt
      const encrypted = await cryptoUtils.encrypt(plaintext);
      
      expect(encrypted).toHaveProperty('version', 1);
      expect(encrypted).toHaveProperty('data');
      expect(encrypted).toHaveProperty('iv');
      expect(encrypted).toHaveProperty('salt');
      
      // Verify encryption was called
      expect(window.crypto.subtle.encrypt).toHaveBeenCalledWith(
        {
          name: 'AES-GCM',
          iv: mockIv,
        },
        'mockDerivedKey',
        expect.any(Uint8Array)
      );
      
      // Decrypt
      const decrypted = await cryptoUtils.decrypt(encrypted);
      
      expect(decrypted).toBe(plaintext);
      
      // Verify decrypt was called
      expect(window.crypto.subtle.decrypt).toHaveBeenCalled();
    });

    it('should throw error when encryption fails', async () => {
      (window.crypto.subtle.encrypt as Mock) = vi.fn().mockRejectedValue(new Error('Encryption failed'));
      
      await expect(cryptoUtils.encrypt('test')).rejects.toThrow('Failed to encrypt data');
    });

    it('should throw error when decryption fails', async () => {
      (window.crypto.subtle.decrypt as Mock) = vi.fn().mockRejectedValue(new Error('Decryption failed'));
      
      const fakeEncryptedData = {
        version: 1,
        data: 'ZmFrZURhdGE=', // base64 encoded 'fakeData'
        iv: 'ZmFrZUl2', // base64 encoded 'fakeIv'
        salt: 'ZmFrZVNhbHQ=', // base64 encoded 'fakeSalt'
      };
      
      await expect(cryptoUtils.decrypt(fakeEncryptedData)).rejects.toThrow(
        'Failed to decrypt data - data may be corrupted or tampered with'
      );
    });

    it('should throw error for unsupported encryption version', async () => {
      const invalidVersionData = {
        version: 2, // Unsupported version
        data: 'ZmFrZURhdGE=',
        iv: 'ZmFrZUl2',
        salt: 'ZmFrZVNhbHQ=',
      };
      
      await expect(cryptoUtils.decrypt(invalidVersionData)).rejects.toThrow(
        'Unsupported encryption version: 2'
      );
    });

    it('should throw error when Web Crypto API is not supported', async () => {
      const originalCrypto = window.crypto;
      // @ts-ignore - Temporarily remove crypto
      delete window.crypto;
      
      await expect(cryptoUtils.encrypt('test')).rejects.toThrow(
        'Web Crypto API is not supported in this browser'
      );
      
      // Restore
      window.crypto = originalCrypto;
    });
  });

  describe('generateSecureRandom', () => {
    it('should generate random string of specified length', () => {
      const length = 32;
      const random1 = cryptoUtils.generateSecureRandom(length);
      const random2 = cryptoUtils.generateSecureRandom(length);
      
      expect(random1).toHaveLength(length * 2); // Hex encoding doubles length
      expect(random2).toHaveLength(length * 2);
      expect(random1).not.toBe(random2); // Should be different
      expect(random1).toMatch(/^[0-9a-f]+$/); // Should be hex
    });

    it('should use default length when not specified', () => {
      const random = cryptoUtils.generateSecureRandom();
      expect(random).toHaveLength(64); // Default 32 bytes = 64 hex chars
    });
  });

  describe('clearMasterKey', () => {
    it('should clear the master key', async () => {
      // First encrypt something to ensure a key is generated
      (window.crypto.subtle.importKey as Mock) = vi.fn().mockResolvedValue('mockKey');
      (window.crypto.subtle.deriveKey as Mock) = vi.fn().mockResolvedValue('mockDerivedKey');
      (window.crypto.subtle.encrypt as Mock) = vi.fn().mockResolvedValue(new ArrayBuffer(32));
      
      await cryptoUtils.encrypt('test');
      
      // Clear the key
      cryptoUtils.clearMasterKey();
      
      // Next encryption should generate a new key
      await cryptoUtils.encrypt('test2');
      
      // Verify key generation was called again
      expect(window.crypto.subtle.deriveKey).toHaveBeenCalledTimes(2);
    });
  });

  describe('browser fingerprint', () => {
    it('should generate consistent fingerprint', async () => {
      // Mock the crypto.subtle methods for consistent results
      let deriveKeyCalls = 0;
      (window.crypto.subtle.importKey as Mock) = vi.fn().mockResolvedValue('mockPasswordKey');
      (window.crypto.subtle.deriveKey as Mock) = vi.fn().mockImplementation(() => {
        deriveKeyCalls++;
        return Promise.resolve(`mockDerivedKey${deriveKeyCalls}`);
      });
      (window.crypto.subtle.encrypt as Mock) = vi.fn().mockResolvedValue(new ArrayBuffer(32));
      
      // Encrypt twice to test key consistency
      await cryptoUtils.encrypt('test1');
      await cryptoUtils.encrypt('test2');
      
      // Should only derive key once (reused for second encryption)
      expect(deriveKeyCalls).toBe(1);
    });
  });

  describe('ArrayBuffer conversions', () => {
    it('should correctly convert between ArrayBuffer and Base64', () => {
      const originalText = 'Hello, World!';
      const encoder = new TextEncoder();
      const originalBuffer = encoder.encode(originalText).buffer;
      
      // Use the private methods through the public API
      // We'll test this indirectly through encrypt/decrypt
      const mockEncryptedData = new Uint8Array([1, 2, 3, 4, 5]);
      (window.crypto.subtle.encrypt as Mock) = vi.fn().mockResolvedValue(mockEncryptedData.buffer);
      
      cryptoUtils.encrypt(originalText).then(encrypted => {
        // Check that the data is base64 encoded
        expect(encrypted.data).toMatch(/^[A-Za-z0-9+/]*={0,2}$/);
        
        // Decode and verify
        const decoded = atob(encrypted.data);
        const bytes = new Uint8Array(decoded.length);
        for (let i = 0; i < decoded.length; i++) {
          bytes[i] = decoded.charCodeAt(i);
        }
        
        expect(Array.from(bytes)).toEqual([1, 2, 3, 4, 5]);
      });
    });
  });
});