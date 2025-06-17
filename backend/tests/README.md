# GolfDaddy Brain Tests

This directory contains all tests for the GolfDaddy Brain application.

## Directory Structure

- `unit/`: Unit tests for individual components
  - Tests are isolated and don't require external services
  - Naming convention: `test_<module_name>.py`

- `integrations/`: Integration tests between components and external services
  - Tests interactions between multiple components or with external services
  - Naming convention: `test_<integration_name>.py`

- `fixtures/`: Shared test fixtures and test data
  - Contains reusable test data and helper fixtures
  - Structured by domain area

- `utils/`: Test utilities and helpers
  - Contains helper functions used across tests
  - Reduces code duplication in test files

## Running Tests

Run all tests:
```bash
pytest
```

Run a specific test module:
```bash
pytest tests/unit/test_raci_service.py
```

Run tests with code coverage:
```bash
pytest --cov=app tests/
```

## Test Conventions

1. All test files should be prefixed with `test_`
2. Test class names should be prefixed with `Test`
3. Test method names should be prefixed with `test_`
4. Use fixtures for reusable test setup/teardown
5. Use meaningful test names that describe the behavior being tested 