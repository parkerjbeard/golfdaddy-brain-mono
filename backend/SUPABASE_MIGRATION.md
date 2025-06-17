# Supabase Migration Guide

This guide outlines the steps to complete the migration from SQLAlchemy to Supabase for database access and authentication.

## Migration Checklist

### 1. Database Schema Setup

We've created schema files in the `supabase/schemas` directory:
- `users.sql` - User profiles linked to Supabase auth
- `tasks.sql` - Tasks with RACI assignments
- `docs.sql` - AI-generated documentation 
- `commits.sql` - GitHub commit tracking (already existed)

To apply these schemas to your Supabase project:

1. Log in to your Supabase dashboard
2. Go to SQL Editor
3. Copy and paste each schema file content
4. Run the SQL queries to create tables, indices, and security policies

### 2. Environment Configuration

Update your environment variables in `.env`:

```
# Supabase Configuration
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
SUPABASE_ANON_KEY=your-anon-key-here
DATABASE_URL=postgres://postgres:postgres@your-project-ref.supabase.co:5432/postgres
```

### 3. Authentication Configuration

1. Enable Email/Password authentication in Supabase Authentication settings
2. Configure any additional auth providers you need (Social, SSO, etc.)
3. Update security policies in SQL Editor if needed

### 4. Verify Repositories

Ensure all repositories are using the Supabase client:
- `UserRepository` - Updated to use Supabase
- `TaskRepository` - Updated to use Supabase
- Any additional repositories should follow same pattern

### 5. Update Tests

All tests have been updated to use mocked Supabase clients instead of SQLAlchemy sessions:
- Created mock fixtures in `tests/conftest.py`
- Updated API endpoint tests
- Removed SQLite in-memory database references

### 6. Clean Up Legacy Code

You can safely remove:
- Any SQLAlchemy model definitions (replaced by Pydantic models)
- SQLAlchemy engine configuration
- Database session factories and dependencies

### 7. Test Authentication Flow

Verify the following auth flows work correctly:
- User registration
- Email/password login
- Token refresh
- User profile creation
- Authorization with JWT tokens

## Additional Configuration

### Row Level Security (RLS)

The schema files include Row Level Security policies that:
- Allow authenticated users to read profiles
- Only allow users to update their own profiles
- Control access to tasks based on user role
- Limit document access based on ownership

You may need to adjust these policies based on your specific security requirements.

### User Management

Supabase Auth provides an admin UI for user management:
- Invite users
- Reset passwords
- Delete user accounts
- View authentication logs

### Database Backups

Supabase automatically creates backups of your database. Consider setting up additional backup procedures for production environments.

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Ensure your SUPABASE_SERVICE_ROLE_KEY is valid and has the appropriate permissions.

2. **Database Connection Errors**: Check that DATABASE_URL is correctly formatted and accessible.

3. **RLS Policy Errors**: If data access is blocked, verify that RLS policies are correctly defined.

4. **Missing Tables**: Ensure all schema SQL has been executed on your Supabase instance.

### Getting Help

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase GitHub Issues](https://github.com/supabase/supabase/issues)
- [Supabase Discord](https://discord.supabase.com) 