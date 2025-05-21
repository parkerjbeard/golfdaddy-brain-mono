# Integration Tests for GolfDaddy Brain

This directory contains integration tests for the GolfDaddy Brain backend services. 
Unlike unit tests that mock database interactions, these tests verify the correct functioning 
of services with real database interactions.

## Test Architecture

The integration tests follow these key principles:

1. **Isolated Test Data**: Each test creates its own uniquely named database tables to prevent 
   interference between test runs.

2. **Real Database Interactions**: Tests interact with the actual database engine 
   (Supabase/PostgreSQL) to verify SQL queries, constraints, and transaction behavior.

3. **End-to-End Service Testing**: Tests verify that service methods properly interact with 
   repositories and persist/retrieve data correctly.

## Test Structure

### Test Database Setup

Integration tests use the following approach for database setup:

1. Create temporary tables with unique names for each test run
2. Patch repository classes to use these temporary tables
3. Create test data in these tables
4. Run tests against the real database
5. Clean up the temporary tables after the test

This approach ensures that:
- Tests are isolated from each other
- Tests don't pollute the production/development database
- Tests run against the real database engine to catch SQL issues

### Test Fixtures

The integration tests use these key fixtures:

- `setup_test_db`: Creates temporary tables and patches repositories
- `setup_test_data`: Populates test tables with standard test data
- Various service-specific fixtures for specialized test scenarios

## Running Integration Tests

To run the integration tests, use:

```bash
# Run all integration tests
pytest tests/integration/

# Run tests for a specific service
pytest tests/integration/services/test_raci_service_integration.py

# Run a specific test
pytest tests/integration/services/test_user_service_integration.py::TestUserServiceIntegration::test_create_user
```

## Environment Setup

Integration tests require:

1. A valid Supabase URL and service role key in your environment
2. Either:
   - A running Supabase instance with the ability to create temporary tables
   - A test database with the same schema as production

Set these in your `.env` file or environment variables:

```
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

## Test Categories

The integration tests cover:

### Service Tests

Tests in `tests/integration/services/` verify that service methods correctly:
- Persist data via repositories
- Retrieve and transform data 
- Handle transactions and error conditions
- Apply business logic across database operations

### Repository Tests

Tests in `tests/integration/repositories/` verify that repository methods correctly:
- Execute SQL queries
- Handle database constraints
- Transform between database rows and model objects

### API Tests

Tests in `tests/integration/api/` verify end-to-end API behavior:
- Request handling
- Authentication and authorization
- Response formatting
- Error handling

## Writing New Integration Tests

When writing new integration tests:

1. Follow the pattern of existing tests
2. Use the `setup_test_db` fixture to create isolated tables
3. Create necessary test data
4. Test both happy paths and error conditions
5. Ensure proper cleanup in fixture teardown

## Transactional Testing

For tests that modify data, the temporary table approach ensures
that tests don't interfere with each other even if they fail. 