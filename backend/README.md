# GolfDaddy Brain

Backend API for task management with RACI framework, KPI tracking, and AI-powered features.

## Project Structure

```
project/
├── app/
│   ├── config/           # Configuration settings and database setup
│   ├── middleware/       # API Gateway and security middleware
│   ├── auth/             # Authentication and authorization
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
- Slack workspace with admin privileges to create an app

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

4. Create a Slack App for authentication
   - Go to https://api.slack.com/apps
   - Click "Create New App" and select "From scratch"
   - Choose a name and select your workspace
   - Under "OAuth & Permissions", add the redirect URL: `http://localhost:8000/auth/slack/callback`
   - Add the following scopes:
     - `identity.basic`
     - `identity.email`
   - Save changes and install the app to your workspace
   - Note your Client ID and Client Secret from "Basic Information"

5. Create a `.env` file with your configuration
   ```
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=golfdaddy
   DB_USER=postgres
   DB_PASSWORD=yourpassword
   
   SLACK_TOKEN=your_slack_token
   SLACK_SIGNING_SECRET=your_slack_signing_secret
   
   # Slack OAuth for authentication
   SLACK_CLIENT_ID=your_slack_client_id
   SLACK_CLIENT_SECRET=your_slack_client_secret
   SLACK_REDIRECT_URI=http://localhost:8000/auth/slack/callback
   ALLOWED_SLACK_TEAMS=your_slack_team_id
   
   # JWT settings for authentication tokens
   JWT_SECRET=random_secure_string
   JWT_ALGORITHM=HS256
   JWT_EXPIRY_HOURS=24
   
   GITHUB_TOKEN=your_github_token
   AI_SERVICE_KEY=your_ai_service_key
   
   # API Gateway settings
   ENABLE_API_AUTH=true
   ENABLE_RATE_LIMITING=true
   API_KEY_HEADER=X-API-Key
   DEFAULT_RATE_LIMIT=60
   
   # API keys for development (JSON string)
   API_KEYS={"your-api-key": {"owner": "your-name", "role": "admin", "rate_limit": 1000}}
   ```

6. Run the application
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

## Authentication

### Slack Authentication

The application uses Slack for user authentication:

1. Direct users to `/auth/login/slack` to initiate authentication
2. Users will be redirected to Slack to authorize the application
3. After authorization, they'll be redirected back with a JWT token
4. Use this token in the Authorization header for all API requests:
   ```
   Authorization: Bearer your.jwt.token
   ```

To get the currently authenticated user, call the `/auth/me` endpoint.

### API Key Authentication

For service-to-service communication, API key authentication is also available:

1. Add your API key to the request header:
   ```
   X-API-Key: your-api-key
   ```

2. API keys can be configured with different roles and rate limits in the `.env` file.

## API Gateway Features

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
AUTH_EXCLUDE_PATHS=/docs,/redoc,/openapi.json,/health,/auth

# Paths excluded from rate limiting (comma-separated)
RATE_LIMIT_EXCLUDE_PATHS=/health,/auth

# JSON string of API keys and their properties
API_KEYS={"api-key": {"owner": "name", "role": "role", "rate_limit": 100}}

# Or path to a JSON/YAML file containing API keys (more secure)
# API_KEYS_FILE_PATH=/path/to/api_keys.json
# API_KEYS_FILE_PATH=/path/to/api_keys.yaml
```

### API Keys File Configuration

For better security, API keys can be loaded from an external file instead of environment variables. This is especially useful for production environments where you want to keep sensitive keys separate from your main configuration.

#### Setting up API Keys File

1. Create an API keys file in JSON or YAML format:

**JSON format (`api_keys.json`):**
```json
{
  "admin-key": {
    "owner": "admin-user",
    "role": "admin",
    "rate_limit": 1000,
    "description": "Administrator API key"
  },
  "service-key": {
    "owner": "external-service",
    "role": "service", 
    "rate_limit": 500,
    "description": "Service-to-service integration key"
  }
}
```

**YAML format (`api_keys.yaml`):**
```yaml
admin-key:
  owner: admin-user
  role: admin
  rate_limit: 1000
  description: Administrator API key

service-key:
  owner: external-service
  role: service
  rate_limit: 500
  description: Service-to-service integration key
```

2. Set the file path in your environment:
```bash
API_KEYS_FILE_PATH=/secure/path/to/api_keys.json
```

#### Key Merging Priority

- **Environment variables override file values**: If both file and `API_KEYS` environment variable are provided, environment variable values take precedence
- **File-only**: If only `API_KEYS_FILE_PATH` is set, keys are loaded from the file
- **Environment-only**: If only `API_KEYS` is set, keys are parsed from the JSON string

#### Template Files

Use the provided template files as starting points:
- `apikeys.template.json` - JSON format template
- `apikeys.template.yaml` - YAML format template
## User Profile Email Source

The authoritative record for a user's **email** lives in `auth.users`. A copy is stored in `public.users` for convenience when joining profile data. Whenever an email is changed via Supabase Auth, a trigger updates the value in `public.users` so the two tables remain consistent.

Updates to name or `avatar_url` are stored in `public.users` and may optionally be synced back into the auth metadata using the service key.
