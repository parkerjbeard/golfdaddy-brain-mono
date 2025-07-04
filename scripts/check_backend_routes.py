#!/usr/bin/env python3
"""
Check available backend routes
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

try:
    from app.main import app
    
    print("Available Backend Routes:")
    print("=" * 60)
    
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                'path': route.path,
                'methods': list(route.methods) if route.methods else ['GET'],
                'name': route.name if hasattr(route, 'name') else 'N/A'
            })
    
    # Sort by path
    routes.sort(key=lambda x: x['path'])
    
    # Group by prefix
    current_prefix = None
    for route in routes:
        path = route['path']
        prefix = path.split('/')[1] if '/' in path and len(path.split('/')) > 1 else ''
        
        if prefix != current_prefix:
            if current_prefix is not None:
                print()
            current_prefix = prefix
            if prefix:
                print(f"\n{prefix.upper()} endpoints:")
                print("-" * 40)
        
        methods = ', '.join(route['methods'])
        print(f"{methods:8} {path:40} {route['name']}")
    
    # Look specifically for webhook endpoints
    print("\n\nWebhook-related endpoints:")
    print("=" * 60)
    webhook_routes = [r for r in routes if 'webhook' in r['path'].lower()]
    if webhook_routes:
        for route in webhook_routes:
            methods = ', '.join(route['methods'])
            print(f"{methods:8} {route['path']:40} {route['name']}")
    else:
        print("No webhook endpoints found!")
        
    # Look for commit-related endpoints
    print("\n\nCommit-related endpoints:")
    print("=" * 60)
    commit_routes = [r for r in routes if 'commit' in r['path'].lower()]
    if commit_routes:
        for route in commit_routes:
            methods = ', '.join(route['methods'])
            print(f"{methods:8} {route['path']:40} {route['name']}")
    else:
        print("No commit endpoints found!")
        
except ImportError as e:
    print(f"Error importing app: {e}")
    print("\nMake sure you're in the backend directory or have the backend dependencies installed.")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()