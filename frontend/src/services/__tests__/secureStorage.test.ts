/**
 * Unit tests for SecureStorage service
 */

import { describe, it, expect, beforeEach, afterEach, vi, Mock } from 'vitest';
import { SecureStorage, secureStorage } from '../secureStorage';
import { cryptoUtils } from '@/lib/crypto';

// Mock the crypto utils
vi.mock('@/lib/crypto', () => ({
  cryptoUtils: {
    encrypt: vi.fn(),
    decrypt: vi.fn(),
    clearMasterKey: vi.fn(),
  },
  CryptoUtils: {
    isSupported: vi.fn(() => true),
  },
}));

describe('SecureStorage', () => {
  let storage: SecureStorage;
  
  beforeEach(() => {
    // Clear all mocks
    vi.clearAllMocks();
    localStorage.clear();
    
    // Create a new instance for each test
    storage = SecureStorage.getInstance({
      prefix: 'test_',
      autoCleanup: false, // Disable auto cleanup for tests
    });
    
    // Setup default mock behavior
    (cryptoUtils.encrypt as Mock).mockResolvedValue({
      version: 1,
      data: 'encrypted_data',
      iv: 'test_iv',
      salt: 'test_salt',
    });
    
    (cryptoUtils.decrypt as Mock).mockResolvedValue('decrypted_data');
  });

  afterEach(() => {
    storage.stopAutoCleanup();
  });

  describe('setItem', () => {
    it('should encrypt and store data', async () => {
      const testData = { key: 'value' };
      
      await storage.setItem('testKey', testData);
      
      expect(cryptoUtils.encrypt).toHaveBeenCalledWith(JSON.stringify({
        data: testData,
        metadata: expect.objectContaining({
          version: 1,
          createdAt: expect.any(Number),
          updatedAt: expect.any(Number),
        }),
      }));
      
      const storedData = localStorage.getItem('test_testKey');
      expect(storedData).toBeTruthy();
    });

    it('should set expiration time when provided', async () => {
      const testData = 'test';
      const expiresIn = 5000; // 5 seconds
      
      await storage.setItem('testKey', testData, { expiresIn });
      
      expect(cryptoUtils.encrypt).toHaveBeenCalledWith(expect.stringContaining('expiresAt'));
      
      const encryptedCall = (cryptoUtils.encrypt as Mock).mock.calls[0][0];
      const parsedData = JSON.parse(encryptedCall);
      expect(parsedData.metadata.expiresAt).toBeGreaterThan(Date.now());
    });

    it('should add tags when provided', async () => {
      const testData = 'test';
      const tags = ['auth', 'token'];
      
      await storage.setItem('testKey', testData, { tags });
      
      const encryptedCall = (cryptoUtils.encrypt as Mock).mock.calls[0][0];
      const parsedData = JSON.parse(encryptedCall);
      expect(parsedData.metadata.tags).toEqual(tags);
    });

    it('should fallback to plain storage when encryption fails and fallback is enabled', async () => {
      // Create storage with fallback enabled
      const fallbackStorage = SecureStorage.getInstance({
        prefix: 'fallback_',
        fallbackToPlain: true,
        autoCleanup: false,
      });
      
      (cryptoUtils.encrypt as Mock).mockRejectedValue(new Error('Encryption failed'));
      
      await fallbackStorage.setItem('testKey', 'testData');
      
      const storedData = localStorage.getItem('fallback_testKey');
      expect(storedData).toBeTruthy();
      
      const parsed = JSON.parse(storedData!);
      expect(parsed.data).toBe('testData');
      
      fallbackStorage.stopAutoCleanup();
    });

    it('should throw error when encryption fails and fallback is disabled', async () => {
      (cryptoUtils.encrypt as Mock).mockRejectedValue(new Error('Encryption failed'));
      
      await expect(storage.setItem('testKey', 'testData')).rejects.toThrow();
    });
  });

  describe('getItem', () => {
    it('should decrypt and return stored data', async () => {
      // Store encrypted data
      const encryptedData = {
        version: 1,
        data: 'encrypted_data',
        iv: 'test_iv',
        salt: 'test_salt',
      };
      localStorage.setItem('test_testKey', JSON.stringify(encryptedData));
      
      // Mock decrypt to return the expected data
      const expectedData = { key: 'value' };
      (cryptoUtils.decrypt as Mock).mockResolvedValue(JSON.stringify({
        data: expectedData,
        metadata: {
          version: 1,
          createdAt: Date.now(),
          updatedAt: Date.now(),
        },
      }));
      
      const result = await storage.getItem('testKey');
      
      expect(cryptoUtils.decrypt).toHaveBeenCalledWith(encryptedData);
      expect(result).toEqual(expectedData);
    });

    it('should return null for non-existent keys', async () => {
      const result = await storage.getItem('nonExistentKey');
      expect(result).toBeNull();
    });

    it('should remove expired items and return null', async () => {
      // Store encrypted data with expired timestamp
      const encryptedData = {
        version: 1,
        data: 'encrypted_data',
        iv: 'test_iv',
        salt: 'test_salt',
      };
      localStorage.setItem('test_testKey', JSON.stringify(encryptedData));
      
      // Mock decrypt to return expired data
      (cryptoUtils.decrypt as Mock).mockResolvedValue(JSON.stringify({
        data: 'testData',
        metadata: {
          version: 1,
          createdAt: Date.now() - 10000,
          updatedAt: Date.now() - 10000,
          expiresAt: Date.now() - 1000, // Expired 1 second ago
        },
      }));
      
      const result = await storage.getItem('testKey');
      
      expect(result).toBeNull();
      expect(localStorage.getItem('test_testKey')).toBeNull();
    });

    it('should handle plain data when encrypted data parsing fails', async () => {
      // Store plain data (simulating fallback mode)
      const plainData = {
        data: 'testData',
        metadata: {
          version: 1,
          createdAt: Date.now(),
          updatedAt: Date.now(),
        },
      };
      localStorage.setItem('test_testKey', JSON.stringify(plainData));
      
      const result = await storage.getItem('testKey');
      
      expect(result).toBe('testData');
    });
  });

  describe('removeItem', () => {
    it('should remove item from storage', async () => {
      localStorage.setItem('test_testKey', 'someData');
      
      await storage.removeItem('testKey');
      
      expect(localStorage.getItem('test_testKey')).toBeNull();
    });
  });

  describe('clear', () => {
    it('should remove all items with the storage prefix', async () => {
      localStorage.setItem('test_key1', 'data1');
      localStorage.setItem('test_key2', 'data2');
      localStorage.setItem('other_key', 'data3'); // Different prefix
      
      await storage.clear();
      
      expect(localStorage.getItem('test_key1')).toBeNull();
      expect(localStorage.getItem('test_key2')).toBeNull();
      expect(localStorage.getItem('other_key')).toBe('data3'); // Should remain
      expect(cryptoUtils.clearMasterKey).toHaveBeenCalled();
    });
  });

  describe('keys', () => {
    it('should return all keys with the storage prefix', async () => {
      localStorage.setItem('test_key1', 'data1');
      localStorage.setItem('test_key2', 'data2');
      localStorage.setItem('other_key', 'data3'); // Different prefix
      
      const keys = await storage.keys();
      
      expect(keys).toContain('key1');
      expect(keys).toContain('key2');
      expect(keys).not.toContain('other_key');
    });
  });

  describe('getItemsByTag', () => {
    it('should return items with specific tag', async () => {
      // Store items with tags
      const item1 = {
        version: 1,
        data: 'encrypted_data1',
        iv: 'test_iv',
        salt: 'test_salt',
      };
      const item2 = {
        version: 1,
        data: 'encrypted_data2',
        iv: 'test_iv',
        salt: 'test_salt',
      };
      
      localStorage.setItem('test_auth1', JSON.stringify(item1));
      localStorage.setItem('test_auth2', JSON.stringify(item2));
      
      // Mock decrypt to return data with tags
      (cryptoUtils.decrypt as Mock)
        .mockResolvedValueOnce(JSON.stringify({
          data: 'authData1',
          metadata: {
            version: 1,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            tags: ['auth', 'token'],
          },
        }))
        .mockResolvedValueOnce(JSON.stringify({
          data: 'authData2',
          metadata: {
            version: 1,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            tags: ['auth', 'profile'],
          },
        }));
      
      const items = await storage.getItemsByTag('auth');
      
      expect(Object.keys(items)).toHaveLength(2);
      expect(items.auth1).toBe('authData1');
      expect(items.auth2).toBe('authData2');
    });
  });

  describe('removeItemsByTag', () => {
    it('should remove items with specific tag', async () => {
      // Store items with tags
      const item1 = {
        version: 1,
        data: 'encrypted_data1',
        iv: 'test_iv',
        salt: 'test_salt',
      };
      const item2 = {
        version: 1,
        data: 'encrypted_data2',
        iv: 'test_iv',
        salt: 'test_salt',
      };
      
      localStorage.setItem('test_auth1', JSON.stringify(item1));
      localStorage.setItem('test_other', JSON.stringify(item2));
      
      // Mock decrypt to return data with tags
      (cryptoUtils.decrypt as Mock)
        .mockResolvedValueOnce(JSON.stringify({
          data: 'authData1',
          metadata: {
            version: 1,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            tags: ['auth', 'token'],
          },
        }))
        .mockResolvedValueOnce(JSON.stringify({
          data: 'otherData',
          metadata: {
            version: 1,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            tags: ['other'],
          },
        }));
      
      await storage.removeItemsByTag('auth');
      
      expect(localStorage.getItem('test_auth1')).toBeNull();
      expect(localStorage.getItem('test_other')).toBeTruthy();
    });
  });

  describe('getSize', () => {
    it('should calculate total storage size', async () => {
      localStorage.setItem('test_key1', 'x'.repeat(100));
      localStorage.setItem('test_key2', 'y'.repeat(200));
      localStorage.setItem('other_key', 'z'.repeat(300)); // Different prefix
      
      const size = await storage.getSize();
      
      expect(size).toBe(300); // 100 + 200
    });
  });

  describe('auto cleanup', () => {
    it('should cleanup expired items automatically', async () => {
      vi.useFakeTimers();
      
      // Create storage with auto cleanup
      const autoCleanupStorage = SecureStorage.getInstance({
        prefix: 'auto_',
        autoCleanup: true,
        cleanupInterval: 1000, // 1 second for testing
      });
      
      // Store expired item
      const expiredData = {
        version: 1,
        data: 'encrypted_data',
        iv: 'test_iv',
        salt: 'test_salt',
      };
      localStorage.setItem('auto_expired', JSON.stringify(expiredData));
      
      // Mock decrypt to return expired data
      (cryptoUtils.decrypt as Mock).mockResolvedValue(JSON.stringify({
        data: 'testData',
        metadata: {
          version: 1,
          createdAt: Date.now() - 10000,
          updatedAt: Date.now() - 10000,
          expiresAt: Date.now() - 1000, // Expired
        },
      }));
      
      // Advance time to trigger cleanup
      vi.advanceTimersByTime(1100);
      
      // Wait for cleanup to process
      await vi.runOnlyPendingTimersAsync();
      
      expect(localStorage.getItem('auto_expired')).toBeNull();
      
      autoCleanupStorage.stopAutoCleanup();
      vi.useRealTimers();
    });
  });
});