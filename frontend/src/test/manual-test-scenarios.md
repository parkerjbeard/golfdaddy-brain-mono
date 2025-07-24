# Manual Test Scenarios for Secure Token Storage

## Prerequisites
- Frontend application running locally
- Backend API available
- Browser developer tools open
- Test user accounts available

## Test Scenarios

### 1. Basic Token Encryption

**Steps:**
1. Open the application in a browser
2. Navigate to the login page
3. Login with valid credentials
4. Open Browser DevTools > Application > Local Storage
5. Look for stored tokens

**Expected Results:**
- ✅ Tokens should be stored with the `secure_` prefix
- ✅ Token values should appear as encrypted JSON objects with `version`, `data`, `iv`, and `salt` fields
- ✅ Actual token values should NOT be visible in plain text
- ✅ No console warnings about "Secure storage not yet implemented"

**Verification:**
```javascript
// In console, check if tokens are encrypted:
const tokenKey = localStorage.getItem('secure_golf_daddy_auth_tokens');
console.log('Is encrypted:', tokenKey && JSON.parse(tokenKey).data !== undefined);
```

### 2. Token Persistence Across Sessions

**Steps:**
1. Login to the application
2. Close the browser completely
3. Reopen the browser and navigate to the application
4. Check if still logged in

**Expected Results:**
- ✅ User should remain logged in if "Remember Me" was checked
- ✅ Tokens should be decrypted and usable after browser restart
- ✅ No authentication errors on page refresh

### 3. Token Rotation Testing

**Steps:**
1. Login to the application
2. Wait for token to near expiration (check token expiry in debug info)
3. Perform an API action that requires authentication
4. Monitor Network tab for refresh token calls

**Expected Results:**
- ✅ Token should auto-refresh before expiration
- ✅ New tokens should be encrypted and stored
- ✅ Rotation count should increment
- ✅ No interruption in user experience

**Debug Commands:**
```javascript
// Check token status
tokenManager.getDebugInfo();
```

### 4. Logout and Cleanup

**Steps:**
1. Login to the application
2. Navigate through several authenticated pages
3. Click logout
4. Check Local Storage for any remaining tokens

**Expected Results:**
- ✅ All tokens with `secure_` prefix should be removed
- ✅ User profile cache should be cleared
- ✅ Remember Me preference should be cleared
- ✅ User redirected to login page

**Verification:**
```javascript
// Check for cleanup
Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i))
  .filter(key => key.startsWith('secure_') || key.includes('token') || key.includes('auth'));
```

### 5. Multi-Tab Synchronization

**Steps:**
1. Open application in Tab 1 and login
2. Open application in Tab 2 (should be logged in)
3. Logout from Tab 1
4. Switch to Tab 2 and try to perform an action

**Expected Results:**
- ✅ Tab 2 should detect logout and redirect to login
- ✅ Storage events should propagate between tabs
- ✅ No security tokens should remain accessible

### 6. Token Expiration Handling

**Steps:**
1. Login to the application
2. Manually expire the token by modifying its expiry in DevTools
3. Attempt to perform an authenticated action
4. Monitor console and network for refresh attempts

**Expected Results:**
- ✅ Application should attempt token refresh
- ✅ If refresh fails, user should be logged out
- ✅ Cleanup service should trigger
- ✅ Clear error message should be shown

**Manual Token Expiration:**
```javascript
// Force token expiration for testing
const key = 'secure_golf_daddy_auth_tokens';
const data = await secureStorage.getItem(key);
if (data) {
  data.expiresAt = Date.now() - 1000;
  await secureStorage.setItem(key, data);
}
```

### 7. Security Validation

**Steps:**
1. Login to the application
2. Try to manually decrypt tokens without the encryption key
3. Attempt to tamper with encrypted data
4. Try to access tokens from another origin

**Expected Results:**
- ✅ Tokens cannot be decrypted without proper key
- ✅ Tampered tokens should fail validation
- ✅ Tokens not accessible cross-origin
- ✅ Failed decryption should trigger cleanup

### 8. Performance Testing

**Steps:**
1. Login and use the application normally
2. Monitor performance in DevTools
3. Check for any lag during token operations
4. Verify smooth user experience

**Expected Results:**
- ✅ Token encryption/decryption < 50ms
- ✅ No noticeable UI lag
- ✅ Smooth page transitions
- ✅ Quick authentication checks

**Performance Check:**
```javascript
// Measure encryption performance
console.time('encrypt');
await secureStorage.setItem('perf_test', { data: 'x'.repeat(1000) });
console.timeEnd('encrypt');

console.time('decrypt');
await secureStorage.getItem('perf_test');
console.timeEnd('decrypt');
```

### 9. Error Recovery

**Steps:**
1. Disable Web Crypto API support (use older browser)
2. Attempt to login
3. Check error handling and fallback behavior

**Expected Results:**
- ✅ Application should detect lack of crypto support
- ✅ Clear error message about browser compatibility
- ✅ Graceful degradation if fallback enabled
- ✅ Security warning in console

### 10. Development vs Production

**Steps:**
1. Build application for production
2. Deploy to staging environment
3. Verify all console.log statements are removed
4. Check that tokens are properly encrypted

**Expected Results:**
- ✅ No sensitive data in console logs
- ✅ No debug information exposed
- ✅ Encryption working in production
- ✅ Proper error messages for users

## Troubleshooting

### Common Issues

1. **"Failed to decrypt data" errors**
   - Clear all storage and login again
   - Check browser crypto API support
   - Verify no corruption in stored data

2. **Tokens not persisting**
   - Check browser storage quotas
   - Verify no browser extensions blocking storage
   - Check for private/incognito mode

3. **Performance issues**
   - Monitor encryption operation times
   - Check for storage quota limits
   - Verify no infinite refresh loops

### Debug Tools

```javascript
// Full storage inspection
const inspectSecureStorage = async () => {
  const keys = await secureStorage.keys();
  for (const key of keys) {
    console.log(`Key: ${key}`);
    try {
      const value = await secureStorage.getItem(key);
      console.log('Value:', value);
    } catch (e) {
      console.error('Failed to decrypt:', e);
    }
  }
};

// Token manager status
const checkTokenStatus = () => {
  console.log('Token Manager Debug Info:', tokenManager.getDebugInfo());
};

// Force cleanup
const forceCleanup = async () => {
  TokenCleanupService.triggerLogout();
  await secureStorage.clear();
  console.log('Cleanup completed');
};
```

## Security Checklist

- [ ] Tokens encrypted at rest
- [ ] No plain text tokens in storage
- [ ] Automatic cleanup on logout
- [ ] Token rotation tracking
- [ ] Secure key derivation
- [ ] No sensitive data in logs
- [ ] Proper error handling
- [ ] Cross-tab synchronization
- [ ] Performance acceptable
- [ ] Production ready