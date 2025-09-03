# GolfDaddy Brain

GolfDaddy Brain is an AI-powered software engineering assistant that helps teams track work, manage tasks, and improve productivity through intelligent analysis of code commits and daily reports.

## Key Features

- **Daily Batch Commit Analysis**: Revolutionary AI-powered system that analyzes all daily commits together for 90% cost reduction and improved accuracy
- **GitHub Commit Analysis**: AI-powered analysis of individual commits to estimate work hours and complexity
- **Daily Report Collection**: Slack bot collects end-of-day reports with intelligent deduplication
- **RACI Task Management**: Complete task tracking with Responsible, Accountable, Consulted, and Informed roles
- **KPI Tracking**: Automated calculation of velocity, completion rates, and team performance
- **Automatic Documentation**: AI generates and updates documentation based on code changes
- **Manager Development**: Personal mastery tracking and AI-generated development plans

## Project Structure

The project is structured into two main parts:

- `backend/`: FastAPI-based backend API with AI integrations
- `frontend/`: React/TypeScript frontend application with real-time updates

## Setup and Installation

### Prerequisites

- Python 3.11+
- Node.js 20+
- npm or yarn
- Docker and Docker Compose (optional, for containerized setup)

### Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/golfdaddy.git
   cd golfdaddy
   ```

2. **Set up environment variables**:
   ```bash
   # Create root .env file
   cp .env.example .env
   
   # Create frontend .env file
   echo "VITE_API_BASE_URL=http://localhost:8000" > frontend/.env
   ```

3. **Install dependencies**:
   ```bash
   # Install root dependencies
   npm install
   
   # Install frontend dependencies
   npm install --prefix frontend
   
   # Install backend dependencies (preferably in a virtual environment)
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r backend/requirements.txt
   ```

4. **Start development servers**:
   ```bash
   # Start both frontend and backend with one command
   npm start
   
   # Or start them separately:
   # Backend
   npm run start:backend
   
   # Frontend
   npm run start:frontend
   ```

5. **Access the application**:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Docker Setup

1. **Build and start the containers**:
   ```bash
   docker-compose up --build
   ```

2. **Access the application**:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Testing

### Running Backend Tests

```bash
cd backend
pytest
```

### Running Frontend Tests

```bash
cd frontend
npm test
```

## Daily Batch Commit Analysis

**NEW**: Revolutionary approach to commit analysis that provides 90% cost reduction and improved accuracy:

### How It Works
1. **Daily Report Submission**: When users submit daily reports, all commits from that day are analyzed together
2. **Midnight Automatic Analysis**: Users without reports get automatic analysis at 12:05 AM
3. **Holistic AI Analysis**: Single AI call analyzes entire day's work with full context
4. **Smart Reconciliation**: Compares AI estimates with user-reported hours for accuracy

### Benefits
- **90% Cost Reduction**: One AI call per day instead of per commit
- **Better Context**: AI sees full daily work patterns and context switching
- **Improved Accuracy**: Holistic analysis provides more realistic hour estimates
- **Automatic Coverage**: Works with or without daily reports

### Configuration
```bash
ENABLE_DAILY_BATCH_ANALYSIS=true
SKIP_INDIVIDUAL_COMMIT_ANALYSIS=false  # Gradual migration
EOD_REMINDER_HOUR=17  # 5 PM
EOD_REMINDER_MINUTE=30  # 5:30 PM
```

See [DAILY_BATCH_COMMIT_ANALYSIS.md](./claude_docs/DAILY_BATCH_COMMIT_ANALYSIS.md) for complete documentation.

## Daily Report Workflow

The system combines GitHub commit analysis with daily reports collected via Slack:

1. **Individual Analysis**: Each GitHub commit can be analyzed by AI to estimate work hours (optional)
2. **Daily Batch Analysis**: All commits analyzed together when daily report is submitted
3. **EOD Reports**: Slack bot prompts employees for daily reports at configurable times
4. **Intelligent Deduplication**: AI prevents double-counting between commits and reports
5. **Weekly Aggregation**: Combined view of all work performed with accurate hour tracking

See [DAILY_REPORT_WORKFLOW.md](./DAILY_REPORT_WORKFLOW.md) for detailed information.

## Deployment

The application can be deployed using Docker Compose or separately for the frontend and backend.

### Docker Deployment

```bash
docker-compose -f docker-compose.yml up -d
```

## Automated Documentation

Note: The previous automated documentation agent and related UI have been removed to streamline the product to its core (repo scan, commit analysis, dashboard). If you need these features, refer to earlier tags or the BLOAT-REDUCTION-PLAN.md for guidance.


## License

[Your License]
