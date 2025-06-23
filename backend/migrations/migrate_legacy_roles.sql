-- Migrate legacy roles to new role system
-- This migration maps old roles to the new simplified role structure

-- Update USER roles to employee
UPDATE users SET role = 'employee' WHERE LOWER(role) = 'user';

-- Update DEVELOPER roles to employee
UPDATE users SET role = 'employee' WHERE LOWER(role) = 'developer';

-- Update VIEWER roles to employee
UPDATE users SET role = 'employee' WHERE LOWER(role) = 'viewer';

-- Update SERVICE_ACCOUNT roles to employee
UPDATE users SET role = 'employee' WHERE LOWER(role) = 'service_account';

-- Update LEAD roles to manager
UPDATE users SET role = 'manager' WHERE LOWER(role) = 'lead';

-- Update MANAGER roles to lowercase (if not already)
UPDATE users SET role = 'manager' WHERE LOWER(role) = 'manager' AND role != 'manager';

-- Update ADMIN roles to lowercase (if not already)
UPDATE users SET role = 'admin' WHERE LOWER(role) = 'admin' AND role != 'admin';

-- Verify all roles are now valid
SELECT role, COUNT(*) as count 
FROM users 
GROUP BY role 
ORDER BY role;

-- This should only show: employee, manager, admin