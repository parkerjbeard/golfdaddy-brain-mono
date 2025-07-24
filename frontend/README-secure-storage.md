# Frontend Secure Token Storage

## Overview

The GolfDaddy Brain frontend implements a comprehensive secure token storage system using Web Crypto API encryption. This ensures that authentication tokens and sensitive data are never stored in plain text.

## Key Features

- 🔐 **AES-GCM Encryption**: Industry-standard encryption for all stored tokens
- 🔄 **Automatic Token Refresh**: Seamless token renewal before expiration
- 🧹 **Automatic Cleanup**: Tokens cleared on logout across all tabs
- 📊 **Token Rotation Tracking**: Monitor token lifecycle and rotations
- 🏷️ **Tag-Based Organization**: Categorize stored items for easy management
- ⏰ **Expiration Support**: Automatic removal of expired items

## Quick Start

### Installation

The secure storage system is already integrated into the application. To use it in new components:

```typescript
import { secureStorage } from '@/services/secureStorage';
import { tokenManager } from '@/services/api/tokenManager';
```

### Basic Usage

```typescript
// Store encrypted data
await secureStorage.setItem('key', sensitiveData, {
  expiresIn: 3600000, // 1 hour
  tags: ['user', 'preferences']
});

// Retrieve decrypted data
const data = await secureStorage.getItem('key');

// Get authentication token (auto-refreshes if needed)
const token = await tokenManager.getToken();
```

## Architecture

```
┌─────────────────┐
│   Components    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  TokenManager   │────▶│  SecureStorage   │
└─────────────────┘     └────────┬─────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   CryptoUtils   │
                        └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Web Crypto API  │
                        └─────────────────┘
```

## Security Implementation

### Encryption Details

- **Algorithm**: AES-GCM (256-bit)
- **Key Derivation**: PBKDF2 (100,000 iterations)
- **IV Generation**: Cryptographically secure random
- **Salt**: Unique per encryption operation

### Token Lifecycle

1. **Login**: Tokens encrypted and stored
2. **Usage**: Automatic decryption on access
3. **Refresh**: Proactive renewal before expiration
4. **Logout**: Complete cleanup across all tabs

## Testing

### Run Tests

```bash
# Unit tests
npm test src/services/__tests__/secureStorage.test.ts
npm test src/lib/__tests__/crypto.test.ts

# Integration tests
npm test src/services/api/__tests__/tokenManager.integration.test.ts

# All tests
npm test
```

### Manual Testing

See `/src/test/manual-test-scenarios.md` for detailed manual testing procedures.

## Configuration

### Environment Variables

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000/api/v1

# Token Manager Settings (optional)
VITE_TOKEN_REFRESH_THRESHOLD=300000  # 5 minutes
VITE_TOKEN_MAX_RETRIES=3
```

### Custom Configuration

```typescript
// Custom SecureStorage instance
const customStorage = SecureStorage.getInstance({
  prefix: 'myapp_',
  autoCleanup: true,
  cleanupInterval: 300000 // 5 minutes
});

// Custom TokenManager instance
const customTokenManager = new GolfDaddyTokenManager({
  storageKey: 'custom_tokens',
  refreshThreshold: 600000, // 10 minutes
  secureStorage: true
});
```

## Troubleshooting

### Common Issues

1. **"Failed to decrypt data"**
   - Clear browser storage and re-login
   - Check for storage corruption

2. **"Web Crypto API not supported"**
   - Update to a modern browser
   - Ensure HTTPS in production

3. **Tokens not persisting**
   - Check browser storage quota
   - Disable private browsing mode

### Debug Commands

```javascript
// Console commands for debugging

// Check token status
tokenManager.getDebugInfo()

// List all secure storage keys
await secureStorage.keys()

// Clear all secure storage
await secureStorage.clear()

// Force token refresh
await tokenManager.refreshToken()
```

## Migration from Plain Storage

If migrating from plain localStorage:

```typescript
// Before
localStorage.setItem('token', token);
const token = localStorage.getItem('token');

// After
await secureStorage.setItem('token', token);
const token = await secureStorage.getItem('token');
```

## Browser Support

- Chrome 37+
- Firefox 34+
- Safari 10.1+
- Edge 79+
- Opera 24+

## Contributing

When adding new features that require secure storage:

1. Always use `secureStorage` for sensitive data
2. Add appropriate tags for categorization
3. Set reasonable expiration times
4. Handle decryption errors gracefully
5. Write tests for new storage operations

## Documentation

- [Full Documentation](../claude_docs/secure-token-storage-documentation.md)
- [API Reference](../claude_docs/secure-token-storage-documentation.md#api-reference)
- [Security Considerations](../claude_docs/secure-token-storage-documentation.md#security-considerations)

## License

Part of the GolfDaddy Brain project.