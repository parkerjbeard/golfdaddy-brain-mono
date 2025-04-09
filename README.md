# GolfDaddy Brain

Backend API for task management with RACI framework, KPI tracking, and AI-powered features.

## Project Structure

```
project/
├── app/
│   ├── config/           # Configuration settings and database setup
│   ├── models/           # SQLAlchemy models
│   ├── repositories/     # Database operations
│   ├── services/         # Business logic
│   ├── integrations/     # External service integrations
│   ├── api/              # API endpoints
│   ├── main.py           # Application entrypoint
│   └── __init__.py
└── tests/
    ├── unit/             # Unit tests
    ├── integration/      # Integration tests
    └── __init__.py
```

## Features

- **Task Management with RACI Framework**: Assign Responsible, Accountable, Consulted, and Informed roles
- **KPI Tracking**: Calculate performance metrics from tasks and commits
- **AI-Powered Analytics**: Analyze GitHub commits and estimate points/time
- **Documentation Generation**: Transform minimal input into robust documentation
- **Slack Integration**: Notifications, task creation, and daily reminders
- **Personal Mastery Tracking**: Manager-specific tasks with reminders

## Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL
- Redis (optional, for caching)

### Installation

1. Clone the repository
   ```
   git clone https://github.com/yourusername/golfdaddy-brain.git
   cd golfdaddy-brain
   ```

2. Create a virtual environment
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your configuration
   ```
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=golfdaddy
   DB_USER=postgres
   DB_PASSWORD=yourpassword
   
   SLACK_TOKEN=your_slack_token
   SLACK_SIGNING_SECRET=your_slack_signing_secret
   GITHUB_TOKEN=your_github_token
   CLICKUP_TOKEN=your_clickup_token
   AI_SERVICE_KEY=your_ai_service_key
   ```

5. Run the application
   ```
   python -m app.main
   ```

### Running Tests

```
pytest tests/
```

## API Documentation

Once the server is running, API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`