# GolfDaddy Brain

GolfDaddy Brain is an AI-powered software engineering assistant that helps teams track work, manage tasks, and improve productivity through intelligent analysis of code commits and daily reports.

## Key Features

- **Daily Batch Commit Analysis**: Revolutionary AI-powered system that analyzes all daily commits together for 90% cost reduction and improved accuracy
- **GitHub Commit Analysis**: AI-powered analysis of individual commits to estimate work hours and complexity
- **Daily Report Collection**: Slack bot collects end-of-day reports with intelligent deduplication
- **RACI Task Management**: Complete task tracking with Responsible, Accountable, Consulted, and Informed roles
- **KPI Tracking**: Automated calculation of velocity, completion rates, and team performance
- **Automatic Documentation**: AI generates and updates documentation based on code changes
 

## Project Structure

The project is structured into two main parts:

- `backend/`: FastAPI-based backend API with AI integrations
- `frontend/`: React/TypeScript frontend application with real-time updates

## Setup and Installation

### Prerequisites

- Python 3.11+
- Bun 1.x (frontend dev/build)

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
   
   # Frontend .env is optional (frontend defaults to '/api' or '/api/v1')
   # echo "VITE_API_BASE_URL=http://localhost:8000" > frontend/.env
   ```

3. **Install dependencies**:
  ```bash
  # Install frontend dependencies
  cd frontend && bun install
  
  # Install backend dependencies (preferably in a virtual environment)
  python -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  pip install -r backend/requirements.txt
  ```

4. **Start development servers**:
   ```bash
  # Start separately (recommended for clarity)
  # Backend
  (cd backend && make run)

  # Frontend (Bun + Vite)
  (cd frontend && bun run dev)
   ```

5. **Access the application**:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Viewing Logs

- Backend: logs print in the terminal running `make run`
- Frontend: logs print in the terminal running `bun run dev`

Ensure your `.env` (root) and `backend/.env` are configured with your Supabase `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `DATABASE_URL` before starting.

## Testing

### Running Backend Tests

```bash
cd backend
pytest
```

### Running Frontend Tests

```bash
cd frontend && bun run test
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

Render is the canonical deployment target for this project. See `RENDER_DEPLOYMENT.md` and `render.yaml` for service configuration and environment variable management. Other deployment configs (Fly.io, Vercel/Netlify, Docker Compose) have been removed to reduce confusion.

## Automated Documentation

Note: The previous automated documentation agent and related UI have been removed to streamline the product to its core (repo scan, commit analysis, dashboard). If you need these features, refer to earlier tags or the BLOAT-REDUCTION-PLAN.md for guidance.


## License

[Your License]
