/**
 * Web Crypto API wrapper for secure data encryption/decryption
 * Uses AES-GCM for authenticated encryption
 */

// Constants for encryption
const ALGORITHM = 'AES-GCM';
const KEY_LENGTH = 256;
const IV_LENGTH = 12; // 96 bits for GCM
const SALT_LENGTH = 16; // 128 bits
const ITERATIONS = 100000; // PBKDF2 iterations
const VERSION = 1; // Encryption version for future compatibility

/**
 * Encrypted data structure
 */
export interface EncryptedData {
  version: number;
  data: string; // Base64 encoded encrypted data
  iv: string; // Base64 encoded initialization vector
  salt: string; // Base64 encoded salt
  tag?: string; // Authentication tag (included in data for GCM)
}

/**
 * Crypto utilities class for secure storage
 */
export class CryptoUtils {
  private static instance: CryptoUtils;
  private masterKey: CryptoKey | null = null;

  private constructor() {}

  /**
   * Get singleton instance
   */
  static getInstance(): CryptoUtils {
    if (!CryptoUtils.instance) {
      CryptoUtils.instance = new CryptoUtils();
    }
    return CryptoUtils.instance;
  }

  /**
   * Check if Web Crypto API is available
   */
  static isSupported(): boolean {
    return typeof window !== 'undefined' && 
           window.crypto && 
           window.crypto.subtle !== undefined;
  }

  /**
   * Generate a random salt
   */
  private generateSalt(): Uint8Array {
    return window.crypto.getRandomValues(new Uint8Array(SALT_LENGTH));
  }

  /**
   * Generate a random IV
   */
  private generateIV(): Uint8Array {
    return window.crypto.getRandomValues(new Uint8Array(IV_LENGTH));
  }

  /**
   * Derive encryption key from a master password
   */
  private async deriveKey(
    password: string,
    salt: Uint8Array
  ): Promise<CryptoKey> {
    const encoder = new TextEncoder();
    const passwordKey = await window.crypto.subtle.importKey(
      'raw',
      encoder.encode(password),
      'PBKDF2',
      false,
      ['deriveKey']
    );

    return window.crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt,
        iterations: ITERATIONS,
        hash: 'SHA-256'
      },
      passwordKey,
      {
        name: ALGORITHM,
        length: KEY_LENGTH
      },
      false,
      ['encrypt', 'decrypt']
    );
  }

  /**
   * Get or generate master key
   * In production, this should use a more secure key derivation method
   */
  private async getMasterKey(): Promise<CryptoKey> {
    if (this.masterKey) {
      return this.masterKey;
    }

    // Generate a unique key based on browser fingerprint and a fixed salt
    // This provides some protection but is not as secure as a user-provided password
    const fingerprint = this.getBrowserFingerprint();
    const fixedSalt = new TextEncoder().encode('GolfDaddySecureStorage2024');
    
    this.masterKey = await this.deriveKey(fingerprint, fixedSalt);
    return this.masterKey;
  }

  /**
   * Get a simple browser fingerprint for key generation
   * This is not cryptographically secure but provides some uniqueness
   */
  private getBrowserFingerprint(): string {
    try {
      const components = [
        navigator.userAgent,
        navigator.language,
        new Date().getTimezoneOffset().toString(),
        screen?.colorDepth?.toString() || '24',
        screen?.width?.toString() || '1920',
        screen?.height?.toString() || '1080',
        // Add a fixed component to ensure consistency
        'GolfDaddyBrain2024'
      ];
      
      return components.join('|');
    } catch (error) {
      // Fallback for environments where these APIs might not be available
      return 'GolfDaddyBrain2024-Fallback';
    }
  }

  /**
   * Convert ArrayBuffer to Base64 string
   */
  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  /**
   * Convert Base64 string to ArrayBuffer
   */
  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  /**
   * Encrypt data using AES-GCM
   */
  async encrypt(plaintext: string): Promise<EncryptedData> {
    if (!CryptoUtils.isSupported()) {
      throw new Error('Web Crypto API is not supported in this browser');
    }

    try {
      const encoder = new TextEncoder();
      const salt = this.generateSalt();
      const iv = this.generateIV();
      const key = await this.getMasterKey();

      const encryptedData = await window.crypto.subtle.encrypt(
        {
          name: ALGORITHM,
          iv
        },
        key,
        encoder.encode(plaintext)
      );

      return {
        version: VERSION,
        data: this.arrayBufferToBase64(encryptedData),
        iv: this.arrayBufferToBase64(iv),
        salt: this.arrayBufferToBase64(salt)
      };
    } catch (error) {
      console.error('Encryption failed:', error);
      throw new Error('Failed to encrypt data');
    }
  }

  /**
   * Decrypt data using AES-GCM
   */
  async decrypt(encryptedData: EncryptedData): Promise<string> {
    if (!CryptoUtils.isSupported()) {
      throw new Error('Web Crypto API is not supported in this browser');
    }

    if (encryptedData.version !== VERSION) {
      throw new Error(`Unsupported encryption version: ${encryptedData.version}`);
    }

    try {
      const decoder = new TextDecoder();
      const key = await this.getMasterKey();
      const iv = this.base64ToArrayBuffer(encryptedData.iv);
      const data = this.base64ToArrayBuffer(encryptedData.data);

      const decryptedData = await window.crypto.subtle.decrypt(
        {
          name: ALGORITHM,
          iv: new Uint8Array(iv)
        },
        key,
        data
      );

      return decoder.decode(decryptedData);
    } catch (error) {
      console.error('Decryption failed:', error);
      throw new Error('Failed to decrypt data - data may be corrupted or tampered with');
    }
  }

  /**
   * Clear the master key from memory
   */
  clearMasterKey(): void {
    this.masterKey = null;
  }

  /**
   * Generate a cryptographically secure random string
   */
  generateSecureRandom(length: number = 32): string {
    const bytes = window.crypto.getRandomValues(new Uint8Array(length));
    return Array.from(bytes)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }
}

// Export singleton instance
export const cryptoUtils = CryptoUtils.getInstance();