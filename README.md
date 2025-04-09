# GolfDaddy Brain

Backend API for task management with RACI framework, KPI tracking, and AI-powered features.

## Project Structure

```
project/
├── app/
│   ├── config/           # Configuration settings and database setup
│   ├── middleware/       # API Gateway and security middleware
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
- **API Gateway & Security**: API key authentication, rate limiting, and request metrics

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
   
   # API Gateway settings
   ENABLE_API_AUTH=true
   ENABLE_RATE_LIMITING=true
   API_KEY_HEADER=X-API-Key
   DEFAULT_RATE_LIMIT=60
   
   # API keys for development (JSON string)
   API_KEYS={"your-api-key": {"owner": "your-name", "role": "admin", "rate_limit": 1000}}
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

## API Gateway Features

### API Key Authentication

The API Gateway includes API key authentication for secure access control. To use authenticated endpoints:

1. Add your API key to the request header:
   ```
   X-API-Key: your-api-key
   ```

2. API keys can be configured with different roles and rate limits in the `.env` file.

### Rate Limiting

To prevent abuse, the API includes rate limiting:

- Default: 60 requests per minute per client
- Custom limits can be set for specific API keys
- Rate limit headers are included in responses:
  ```
  X-RateLimit-Limit: 60
  X-RateLimit-Remaining: 59
  X-RateLimit-Reset: 1612345678
  ```

### Metrics

API usage metrics are available at the `/metrics` endpoint (admin access only):

- Request counts by endpoint
- Response status codes
- Average response time

## Configuration

API Gateway settings can be configured in your `.env` file:

```
# Enable/disable API authentication
ENABLE_API_AUTH=true

# Enable/disable rate limiting
ENABLE_RATE_LIMITING=true

# Custom header name for API keys
API_KEY_HEADER=X-API-Key

# Default rate limit (requests per minute)
DEFAULT_RATE_LIMIT=60

# Paths excluded from authentication (comma-separated)
AUTH_EXCLUDE_PATHS=/docs,/redoc,/openapi.json,/health

# Paths excluded from rate limiting (comma-separated)
RATE_LIMIT_EXCLUDE_PATHS=/health

# JSON string of API keys and their properties
API_KEYS={"api-key": {"owner": "name", "role": "role", "rate_limit": 100}}

# Or path to a JSON file containing API keys (more secure)
# API_KEYS_FILE=/path/to/api_keys.json
```