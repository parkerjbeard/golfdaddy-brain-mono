#!/bin/bash

# check-test-files.sh - Check test files for hardcoded credentials

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

error_found=false

echo "🔍 Checking test files for hardcoded credentials..."

for file in "$@"; do
    if [[ -f "$file" ]]; then
        echo "   Checking: $file"
        
        # Check for Supabase URLs (should be placeholder)
        if grep -q "https://.*\.supabase\.co" "$file"; then
            echo -e "${RED}❌ ERROR: Real Supabase URL found in $file${NC}"
            echo -e "${YELLOW}   Replace with: YOUR_SUPABASE_URL_HERE${NC}"
            error_found=true
        fi
        
        # Check for JWT tokens (base64 patterns starting with ey)
        if grep -q "eyJ[A-Za-z0-9_-]*\." "$file"; then
            echo -e "${RED}❌ ERROR: JWT token found in $file${NC}"
            echo -e "${YELLOW}   Replace with: YOUR_SUPABASE_ANON_KEY_HERE${NC}"
            error_found=true
        fi
        
        # Check for common API key patterns
        if grep -qE "(sk-[a-zA-Z0-9]{32,}|pk_[a-zA-Z0-9]{32,})" "$file"; then
            echo -e "${RED}❌ ERROR: API key pattern found in $file${NC}"
            echo -e "${YELLOW}   Replace with placeholder${NC}"
            error_found=true
        fi
        
        # Check for localhost with ports (should be configurable)
        if grep -q "localhost:[0-9]" "$file"; then
            echo -e "${YELLOW}⚠️  WARNING: Hardcoded localhost URL in $file${NC}"
            echo -e "${YELLOW}   Consider making this configurable${NC}"
        fi
        
        if ! $error_found; then
            echo -e "${GREEN}   ✅ $file looks good${NC}"
        fi
    fi
done

if $error_found; then
    echo ""
    echo -e "${RED}🚨 SECURITY VIOLATION: Hardcoded credentials detected!${NC}"
    echo -e "${YELLOW}Please remove all hardcoded credentials before committing.${NC}"
    echo -e "${YELLOW}Use environment variables or placeholder values instead.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All test files are secure!${NC}"
exit 0 