"""
Script to sync a Supabase user to the local PostgreSQL database.
Usage: python sync_user.py <user_id> <email> [role]
"""
import sys
import psycopg2
from uuid import UUID

def sync_user(user_id: str, email: str, role: str = 'employee'):
    """Sync a user from Supabase to local PostgreSQL."""
    
    # Database connection
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        database="golfdaddy",
        user="postgres",
        password="postgres"
    )
    
    try:
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing user
            cursor.execute("""
                UPDATE users 
                SET email = %s, role = %s, updated_at = NOW()
                WHERE id = %s
            """, (email, role, user_id))
            print(f"Updated user {user_id} with role {role}")
        else:
            # Insert new user
            cursor.execute("""
                INSERT INTO users (id, email, name, role)
                VALUES (%s, %s, %s, %s)
            """, (user_id, email, email.split('@')[0], role))
            print(f"Created user {user_id} with role {role}")
        
        conn.commit()
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python sync_user.py <user_id> <email> [role]")
        sys.exit(1)
    
    user_id = sys.argv[1]
    email = sys.argv[2]
    role = sys.argv[3] if len(sys.argv) > 3 else 'admin'  # Default to admin for testing
    
    sync_user(user_id, email, role)