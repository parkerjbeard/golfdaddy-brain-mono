# GolfDaddy Brain

GolfDaddy Brain is an AI assistant for software engineering.

## Project Structure

The project is structured into two main parts:

- `backend/`: FastAPI-based backend API
- `frontend/`: React/TypeScript frontend application

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

## Deployment

The application can be deployed using Docker Compose or separately for the frontend and backend.

### Docker Deployment

```bash
docker-compose -f docker-compose.yml up -d
```

## License

[Your License]