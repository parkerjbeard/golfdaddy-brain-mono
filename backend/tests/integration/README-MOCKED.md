# Mock-Based Integration Tests for GolfDaddy Brain

This directory contains integration tests that use mocking to simulate database interactions while still testing the integration between services and repositories.

## Why Mocked Integration Tests?

While true integration tests would use a real database, there are several scenarios where mocked integration tests are valuable:

1. **Development Environment**: When developers don't have access to a test database or when setting up a test database is complex
2. **CI/CD Pipeline**: For fast automated testing without database dependencies
3. **Service Integration Focus**: When you want to focus on testing the interactions between services and repositories, rather than the database itself

## Current Implementation

The current implementation uses Python's `unittest.mock` library to mock repository classes and simulate database interactions. This allows us to:

1. Test service methods that integrate with repositories
2. Verify that repository methods are called with the correct parameters
3. Simulate various database responses (success, errors, etc.)
4. Test complex business logic that spans multiple repository calls

## Moving to Real Database Integration Tests

To move from mocked tests to real database integration tests, you would need to:

1. **Set up a test database**: This could be a dedicated test database or temporary tables in your development database
2. **Create test tables**: Tables that match your production schema but are isolated for testing
3. **Manage test data**: Create and clean up test data before and after tests
4. **Handle transactions**: Ensure tests don't interfere with each other and can be rolled back

## Example Implementation with a Real Database

Here's how you could modify the current tests to use a real database:

```python
@pytest.fixture(scope="function")
async def setup_test_db():
    """Set up a real test database for integration tests."""
    # Generate a unique ID for this test run
    test_id = str(uuid.uuid4()).replace("-", "_")
    
    # Define test table names
    table_names = {
        "users": f"users_test_{test_id}",
        # Add other tables as needed
    }
    
    # Get a Supabase client
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    
    try:
        # Create the test tables
        for table, name in table_names.items():
            create_table_sql = f"""
            CREATE TABLE {name} (
                -- Define your schema here
                id UUID PRIMARY KEY,
                name TEXT,
                email TEXT,
                role TEXT,
                -- Add other fields as needed
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
            # Execute the SQL to create the table
            await client.rpc("execute_sql", {"sql": create_table_sql}).execute()
        
        # Create a custom repository that uses our test tables
        user_repo = UserRepository()
        user_repo._table = table_names["users"]
        
        # Create the service with our repository
        user_service = UserService()
        user_service.user_repo = user_repo
        
        # Return the test objects
        yield {
            "user_service": user_service,
            "user_repo": user_repo,
            "table_names": table_names,
            "client": client
        }
    
    finally:
        # Clean up the test tables
        for name in table_names.values():
            drop_sql = f"DROP TABLE IF EXISTS {name};"
            await client.rpc("execute_sql", {"sql": drop_sql}).execute()
```

## Best Practices for Integration Tests

1. **Isolation**: Each test should be isolated from others, with its own data
2. **Cleanup**: Always clean up test data and tables after tests
3. **Realistic Data**: Use realistic test data that reflects production scenarios
4. **Error Cases**: Test both success and error paths
5. **Transactions**: Use transactions to ensure data consistency

## When to Use Mocked vs. Real Integration Tests

**Use mocked integration tests when:**
- You need fast tests for CI/CD
- You're focusing on service-repository interactions
- Database setup is complex or not available

**Use real database integration tests when:**
- You need to verify SQL queries and database constraints
- You're testing complex data operations
- You want to catch issues that only appear with a real database
- You're testing migrations or schema changes

## Running the Tests

### Mocked Integration Tests
```bash
pytest tests/integration/services/test_user_service_integration.py -v
```

### Real Database Integration Tests
```bash
# Set up the test database environment variables
export SUPABASE_TEST_URL=your_test_supabase_url
export SUPABASE_TEST_KEY=your_test_service_key

# Run the tests with the real database flag
pytest tests/integration/services/test_user_service_integration.py -v --real-db
``` 