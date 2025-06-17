#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from supabase import create_client
from dotenv import load_dotenv

# Add the backend directory to Python path so we can import our modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def apply_raci_schema():
    """Apply RACI matrix schema to Supabase database."""
    
    # Load environment variables
    load_dotenv()
    
    # Get database connection details
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print('❌ Error: Missing Supabase credentials')
        print('Please ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set in your .env file')
        return False
    
    print(f'🔗 Connecting to Supabase: {SUPABASE_URL}')
    
    # Read the schema file
    schema_file = backend_dir / 'supabase' / 'schemas' / 'raci_matrices.sql'
    
    if not schema_file.exists():
        print(f'❌ Error: Schema file not found: {schema_file}')
        return False
    
    print(f'📄 Reading schema from: {schema_file}')
    
    try:
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
    except Exception as e:
        print(f'❌ Error reading schema file: {e}')
        return False
    
    # Create Supabase client
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print('✅ Supabase client created successfully')
    except Exception as e:
        print(f'❌ Error creating Supabase client: {e}')
        return False
    
    # Execute the schema
    print('🔧 Applying RACI matrix schema...')
    
    try:
        # For Supabase, we can use the SQL query directly
        result = supabase.rpc('query', {'query': schema_sql}).execute()
        print('✅ RACI matrix schema applied successfully!')
        print('📋 Created tables:')
        print('   - raci_matrices')
        print('   - raci_activities') 
        print('   - raci_roles')
        print('   - raci_assignments')
        print('🔐 RLS policies and triggers configured')
        return True
        
    except Exception as e:
        print(f'❌ Error applying schema: {e}')
        print('\n💡 Tip: You may need to run this SQL manually in your Supabase dashboard')
        print(f'   Go to: {SUPABASE_URL}/project/_/sql')
        return False

if __name__ == '__main__':
    print('🚀 RACI Matrix Schema Installer')
    print('=' * 50)
    
    success = apply_raci_schema()
    
    if success:
        print('\n🎉 Schema installation completed successfully!')
        print('✨ You can now create and manage RACI matrices dynamically')
    else:
        print('\n💀 Schema installation failed')
        print('Please check the error messages above and try again')
        sys.exit(1) 