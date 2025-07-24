/**
 * Storage migration utilities to handle transition from plain to secure storage
 */

import { secureStorage } from './secureStorage';

/**
 * Migrate old localStorage data to secure storage
 */
export async function migrateStorageIfNeeded(): Promise<void> {
  console.log('Checking for storage migration...');
  
  try {
    // Check if we have old non-secure data
    const oldTokenKey = 'golf_daddy_auth_tokens';
    const oldUserProfileKey = 'userProfile';
    const oldRememberMeKey = 'rememberMe';
    
    // List of keys that should be migrated
    const migrationKeys = [
      { old: oldTokenKey, new: oldTokenKey },
      { old: oldUserProfileKey, new: oldUserProfileKey },
      { old: oldRememberMeKey, new: oldRememberMeKey },
      { old: 'token', new: 'token' }, // Legacy key
      { old: 'authToken', new: 'authToken' }, // Legacy key
    ];
    
    let migrated = false;
    
    for (const { old, new: newKey } of migrationKeys) {
      const oldData = localStorage.getItem(old);
      
      if (oldData && !oldData.includes('"version"')) {
        // This looks like old unencrypted data
        console.log(`Migrating old data for key: ${old}`);
        
        try {
          // Try to parse and migrate the data
          const parsedData = JSON.parse(oldData);
          
          // Store in secure storage
          await secureStorage.setItem(newKey, parsedData, {
            tags: ['migrated', 'auth'],
          });
          
          // Remove old data
          localStorage.removeItem(old);
          migrated = true;
          
          console.log(`Successfully migrated: ${old}`);
        } catch (parseError) {
          // If it's not JSON, store as-is
          await secureStorage.setItem(newKey, oldData, {
            tags: ['migrated', 'auth'],
          });
          localStorage.removeItem(old);
          migrated = true;
        }
      }
    }
    
    // Also clean up any corrupted secure storage entries
    const keys = await secureStorage.keys();
    for (const key of keys) {
      try {
        await secureStorage.getItem(key);
      } catch (error) {
        console.warn(`Removing corrupted storage entry: ${key}`);
        await secureStorage.removeItem(key);
        migrated = true;
      }
    }
    
    if (migrated) {
      console.log('Storage migration completed');
    } else {
      console.log('No storage migration needed');
    }
  } catch (error) {
    console.error('Storage migration failed:', error);
    
    // If migration fails completely, offer to clear storage
    if (confirm('Storage appears to be corrupted. Clear all data and start fresh?')) {
      localStorage.clear();
      await secureStorage.clear();
      location.reload();
    }
  }
}

/**
 * Check if storage needs migration
 */
export function needsStorageMigration(): boolean {
  // Check for any old unencrypted keys
  const suspiciousKeys = [
    'golf_daddy_auth_tokens',
    'userProfile',
    'rememberMe',
    'token',
    'authToken'
  ];
  
  for (const key of suspiciousKeys) {
    const value = localStorage.getItem(key);
    if (value && !value.includes('"version"') && !value.startsWith('secure_')) {
      return true;
    }
  }
  
  return false;
}