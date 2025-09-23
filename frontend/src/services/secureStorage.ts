/**
 * SecureStorage service that provides encrypted storage with localStorage-like API
 * Implements automatic encryption/decryption and token versioning
 */

import { cryptoUtils, CryptoUtils, EncryptedData } from '@/lib/crypto';

/**
 * Metadata for stored items
 */
interface StorageMetadata {
  version: number;
  createdAt: number;
  updatedAt: number;
  expiresAt?: number;
  tags?: string[]; // For categorizing items (e.g., ['auth', 'token'])
}

/**
 * Wrapper for stored data with metadata
 */
interface StorageItem<T = any> {
  data: T;
  metadata: StorageMetadata;
}

/**
 * Configuration for SecureStorage
 */
interface SecureStorageConfig {
  prefix?: string; // Prefix for all keys
  fallbackToPlain?: boolean; // Fallback to plain localStorage if encryption fails
  autoCleanup?: boolean; // Automatically cleanup expired items
  cleanupInterval?: number; // Cleanup interval in ms (default: 5 minutes)
}

/**
 * SecureStorage class providing encrypted storage
 */
export class SecureStorage {
  private static instance: SecureStorage;
  private config: Required<SecureStorageConfig>;
  private cleanupTimer?: NodeJS.Timeout;
  private currentVersion = 1;
  private isInitialized = false;

  private constructor(config: SecureStorageConfig = {}) {
    this.config = {
      prefix: config.prefix || 'secure_',
      fallbackToPlain: config.fallbackToPlain ?? false,
      autoCleanup: config.autoCleanup ?? true,
      cleanupInterval: config.cleanupInterval ?? 5 * 60 * 1000 // 5 minutes
    };

    const isTestEnv = import.meta.env.MODE === 'test' || (typeof process !== 'undefined' && process.env?.VITEST);

    // In development, enable fallback by default (but never during tests or when explicitly disabled)
    if (import.meta.env.DEV && !isTestEnv && config.fallbackToPlain === undefined) {
      console.warn('Development mode: Enabling fallback to plain storage');
      this.config.fallbackToPlain = true;
    }

    if (this.config.autoCleanup) {
      this.startAutoCleanup();
    }

    // Check for Web Crypto API support
    if (!CryptoUtils.isSupported()) {
      console.warn('Web Crypto API is not supported. SecureStorage will use fallback mode.');
    }
    
    this.isInitialized = true;
  }

  /**
   * Get singleton instance
   */
  static getInstance(config?: SecureStorageConfig): SecureStorage {
    if (!SecureStorage.instance) {
      SecureStorage.instance = new SecureStorage(config);
    }
    return SecureStorage.instance;
  }

  /**
   * Get the actual storage key with prefix
   */
  private getStorageKey(key: string): string {
    return `${this.config.prefix}${key}`;
  }

  /**
   * Set an item in secure storage
   */
  async setItem<T = any>(
    key: string,
    value: T,
    options: {
      expiresIn?: number; // Expiration time in milliseconds
      tags?: string[];
    } = {}
  ): Promise<void> {
    try {
      const now = Date.now();
      const storageItem: StorageItem<T> = {
        data: value,
        metadata: {
          version: this.currentVersion,
          createdAt: now,
          updatedAt: now,
          expiresAt: options.expiresIn ? now + options.expiresIn : undefined,
          tags: options.tags
        }
      };

      const serialized = JSON.stringify(storageItem);
      
      if (CryptoUtils.isSupported() && !this.config.fallbackToPlain) {
        try {
          const encrypted = await cryptoUtils.encrypt(serialized);
          localStorage.setItem(
            this.getStorageKey(key),
            JSON.stringify(encrypted)
          );
        } catch (encryptError) {
          console.error('Encryption failed:', encryptError);
          if (this.config.fallbackToPlain) {
            console.warn(`Falling back to plain storage for "${key}"`);
            localStorage.setItem(this.getStorageKey(key), serialized);
          } else {
            throw encryptError;
          }
        }
      } else {
        // Fallback to plain storage with warning
        if (!this.config.fallbackToPlain) {
          throw new Error('Encryption not supported and fallback is disabled');
        }
        console.warn(`Storing item "${key}" without encryption (fallback mode)`);
        localStorage.setItem(this.getStorageKey(key), serialized);
      }
    } catch (error) {
      console.error(`Failed to set secure item "${key}":`, error);
      throw error;
    }
  }

  /**
   * Get an item from secure storage
   */
  async getItem<T = any>(key: string): Promise<T | null> {
    try {
      const storageKey = this.getStorageKey(key);
      const rawData = localStorage.getItem(storageKey);
      
      if (!rawData) {
        return null;
      }

      let storageItem: StorageItem<T>;

      // Try to parse as encrypted data first
      try {
        const encrypted: EncryptedData = JSON.parse(rawData);
        
        if (encrypted.version && encrypted.data && encrypted.iv) {
          // This is encrypted data
          const decrypted = await cryptoUtils.decrypt(encrypted);
          storageItem = JSON.parse(decrypted);
        } else {
          // This might be plain data (fallback mode)
          storageItem = JSON.parse(rawData);
        }
      } catch {
        // Assume it's plain data
        storageItem = JSON.parse(rawData);
      }

      // Check if item has expired
      if (storageItem.metadata.expiresAt && storageItem.metadata.expiresAt < Date.now()) {
        await this.removeItem(key);
        return null;
      }

      // Handle version migration if needed
      if (storageItem.metadata.version < this.currentVersion) {
        storageItem = await this.migrateItem(key, storageItem);
      }

      return storageItem.data;
    } catch (error) {
      console.error(`Failed to get secure item "${key}":`, error);
      return null;
    }
  }

  /**
   * Remove an item from secure storage
   */
  async removeItem(key: string): Promise<void> {
    localStorage.removeItem(this.getStorageKey(key));
  }

  /**
   * Clear all secure storage items
   */
  async clear(): Promise<void> {
    const keysToRemove: string[] = [];
    
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(this.config.prefix)) {
        keysToRemove.push(key);
      }
    }

    keysToRemove.forEach(key => localStorage.removeItem(key));
    
    // Clear the crypto master key
    cryptoUtils.clearMasterKey();
  }

  /**
   * Get all keys in secure storage
   */
  async keys(): Promise<string[]> {
    const keys: string[] = [];
    const prefixLength = this.config.prefix.length;
    
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(this.config.prefix)) {
        keys.push(key.substring(prefixLength));
      }
    }
    
    return keys;
  }

  /**
   * Get items by tag
   */
  async getItemsByTag(tag: string): Promise<Record<string, any>> {
    const keys = await this.keys();
    const items: Record<string, any> = {};
    
    for (const key of keys) {
      const item = await this.getItem(key);
      const rawData = localStorage.getItem(this.getStorageKey(key));
      
      if (rawData) {
        try {
          let storageItem: StorageItem;
          
          // Parse the storage item to check tags
          const parsed = JSON.parse(rawData);
          if (parsed.version && parsed.data) {
            const decrypted = await cryptoUtils.decrypt(parsed);
            storageItem = JSON.parse(decrypted);
          } else {
            storageItem = parsed;
          }
          
          if (storageItem.metadata.tags?.includes(tag)) {
            items[key] = item;
          }
        } catch {
          // Skip invalid items
        }
      }
    }
    
    return items;
  }

  /**
   * Remove items by tag
   */
  async removeItemsByTag(tag: string): Promise<void> {
    const keys = await this.keys();
    
    for (const key of keys) {
      const rawData = localStorage.getItem(this.getStorageKey(key));
      
      if (rawData) {
        try {
          let storageItem: StorageItem;
          
          const parsed = JSON.parse(rawData);
          if (parsed.version && parsed.data) {
            const decrypted = await cryptoUtils.decrypt(parsed);
            storageItem = JSON.parse(decrypted);
          } else {
            storageItem = parsed;
          }
          
          if (storageItem.metadata.tags?.includes(tag)) {
            await this.removeItem(key);
          }
        } catch {
          // Skip invalid items
        }
      }
    }
  }

  /**
   * Migrate an item to the current version
   */
  private async migrateItem<T>(key: string, item: StorageItem<T>): Promise<StorageItem<T>> {
    // Implement version-specific migrations here
    console.log(`Migrating item "${key}" from version ${item.metadata.version} to ${this.currentVersion}`);
    
    // Update metadata
    item.metadata.version = this.currentVersion;
    item.metadata.updatedAt = Date.now();
    
    // Re-save the migrated item
    await this.setItem(key, item.data, {
      expiresIn: item.metadata.expiresAt ? item.metadata.expiresAt - Date.now() : undefined,
      tags: item.metadata.tags
    });
    
    return item;
  }

  /**
   * Cleanup expired items
   */
  private async cleanup(): Promise<void> {
    const keys = await this.keys();
    const now = Date.now();
    
    for (const key of keys) {
      try {
        const rawData = localStorage.getItem(this.getStorageKey(key));
        if (!rawData) continue;
        
        let storageItem: StorageItem;
        
        const parsed = JSON.parse(rawData);
        if (parsed.version && parsed.data) {
          const decrypted = await cryptoUtils.decrypt(parsed);
          storageItem = JSON.parse(decrypted);
        } else {
          storageItem = parsed;
        }
        
        if (storageItem.metadata.expiresAt && storageItem.metadata.expiresAt < now) {
          await this.removeItem(key);
          console.debug(`Cleaned up expired item: ${key}`);
        }
      } catch {
        // Skip invalid items
      }
    }
  }

  /**
   * Start automatic cleanup
   */
  private startAutoCleanup(): void {
    this.cleanupTimer = setInterval(() => {
      this.cleanup().catch(console.error);
    }, this.config.cleanupInterval);
  }

  /**
   * Stop automatic cleanup
   */
  stopAutoCleanup(): void {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
      this.cleanupTimer = undefined;
    }
  }

  /**
   * Get storage size (approximate)
   */
  async getSize(): Promise<number> {
    let totalSize = 0;
    const keys = await this.keys();
    
    for (const key of keys) {
      const rawData = localStorage.getItem(this.getStorageKey(key));
      if (rawData) {
        totalSize += rawData.length;
      }
    }
    
    return totalSize;
  }
}

// Export singleton instance
export const secureStorage = SecureStorage.getInstance();

// Export convenience functions
export const setSecureItem = secureStorage.setItem.bind(secureStorage);
export const getSecureItem = secureStorage.getItem.bind(secureStorage);
export const removeSecureItem = secureStorage.removeItem.bind(secureStorage);
export const clearSecureStorage = secureStorage.clear.bind(secureStorage);
