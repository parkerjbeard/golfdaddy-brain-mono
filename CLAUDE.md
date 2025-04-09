# Guidelines for Claude in this repository

## Project Information
- This project is a backend application for task management with RACI framework, KPI tracking, and AI-powered features.
- The project uses a Python backend (likely FastAPI or similar) with PostgreSQL database.

## Build Commands
- Install dependencies: `pip install -r requirements.txt`
- Run development server: `python -m app.main`
- Run tests: `pytest tests/`
- Run single test: `pytest tests/path/to/test_file.py::test_function_name`
- Run linter: `flake8`
- Type checking: `mypy app/`

## Code Style Guidelines
- **Formatting**: Follow PEP 8 style guide
- **Imports**: Group standard library, third-party, and local imports with a blank line between groups
- **Typing**: Use type annotations for all function parameters and return types
- **Naming**:
  - Classes: PascalCase
  - Functions/variables: snake_case
  - Constants: UPPER_SNAKE_CASE
- **Error Handling**: Use appropriate exceptions with descriptive messages
- **Documentation**: All modules, classes, and functions should have docstrings
- **Database**: Use SQLAlchemy ORM patterns for database operations

## Architecture Guidelines
- Follow the repository pattern for database operations
- Service layer should contain business logic
- Keep integrations with external services (Slack, GitHub, etc.) isolated
- Use dependency injection for testability