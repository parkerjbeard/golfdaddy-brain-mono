-- Add role column to users table if it doesn't exist
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'employee';

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Update existing users to have appropriate roles based on your requirements
-- You can customize this based on your needs
UPDATE users SET role = 'admin' WHERE email IN ('admin@company.com'); -- Replace with actual admin emails
UPDATE users SET role = 'manager' WHERE email IN ('manager1@company.com', 'manager2@company.com'); -- Replace with actual manager emails

-- Add check constraint to ensure valid roles
ALTER TABLE users 
ADD CONSTRAINT check_user_role 
CHECK (role IN ('employee', 'manager', 'admin'));

-- Create a simple function to get user with role (optional but useful)
CREATE OR REPLACE FUNCTION get_user_with_role(user_id UUID)
RETURNS TABLE(id UUID, email TEXT, role VARCHAR(50))
AS $$
BEGIN
  RETURN QUERY
  SELECT u.id, u.email, u.role
  FROM users u
  WHERE u.id = user_id;
END;
$$ LANGUAGE plpgsql;