/**
 * Test setup file for Vitest
 */

import '@testing-library/jest-dom';
import { expect, afterEach, beforeEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';

// Extend Vitest's expect with jest-dom matchers
expect.extend(matchers);

// Cleanup after each test
afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
  vi.clearAllMocks();
});

// Mock Web Crypto API with writable properties so tests can override behavior
const createCryptoMock = () => ({
  subtle: {
    encrypt: vi.fn(),
    decrypt: vi.fn(),
    generateKey: vi.fn(),
    importKey: vi.fn(),
    exportKey: vi.fn(),
    deriveKey: vi.fn(),
  },
  getRandomValues: (array: Uint8Array) => {
    for (let i = 0; i < array.length; i += 1) {
      array[i] = Math.floor(Math.random() * 256);
    }
    return array;
  },
});

let cryptoMock = createCryptoMock();

const applyCryptoMock = () => {
  Object.defineProperty(globalThis, 'crypto', {
    value: cryptoMock,
    configurable: true,
    writable: true,
  });

  Object.defineProperty(window, 'crypto', {
    value: cryptoMock,
    configurable: true,
    writable: true,
  });
};

applyCryptoMock();

beforeEach(() => {
  cryptoMock = createCryptoMock();
  applyCryptoMock();
});

// Mock fetch for tests
global.fetch = vi.fn();

// Mock console methods to reduce noise in tests
console.log = vi.fn();
console.warn = vi.fn();
console.error = vi.fn();

// Mock IntersectionObserver
global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));
