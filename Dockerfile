FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Install system dependencies
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*

# Copy package files and install dependencies
COPY frontend/package.json frontend/package-lock.json ./
# Fix ARM64 rollup dependency issue
RUN rm -rf node_modules package-lock.json && \
    npm install --legacy-peer-deps && \
    npm install @rollup/rollup-linux-arm64-gnu --save-dev --legacy-peer-deps || true

# Set required environment variables for build
ENV VITE_SUPABASE_URL=https://xfnxafbsmqowzvuwmhvi.supabase.co
ENV VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhmbnhhZmJzbXFvd3p2dXdtaHZpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ3NTM4OTQsImV4cCI6MjA2MDMyOTg5NH0.eqD4qJcwSaEhEbLX_GZMU1xJT7RRKY3SDqSjOL7Rrws
ENV NODE_ENV=production
ENV VITE_API_BASE_URL=/api/v1
ENV VITE_API_KEY=dev-api-key

# Copy source files
COPY frontend/ ./

# Build the frontend
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy doc_agent module
COPY doc_agent/ ./doc_agent/

# Copy built frontend files
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 