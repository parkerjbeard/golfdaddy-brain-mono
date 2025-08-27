FROM node:20-slim AS frontend-build

WORKDIR /app

# Copy any environment files from project root (Render's secret files)
COPY .env* ./

# Setup frontend directory
WORKDIR /app/frontend

# Copy package files and install deps deterministically
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy source
COPY frontend/ .

# Set build-time environment variables for Vite
# These will be available during the build process
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_API_BASE_URL

# Build with environment variables passed from Render
# The ARG values will be available as environment variables during build
ENV VITE_SUPABASE_URL=${VITE_SUPABASE_URL}
ENV VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

FROM python:3.11-slim AS backend-base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir gunicorn

# Copy backend code
COPY backend/ ./

# Copy built frontend where app.main expects it
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Expose container port (Render sets $PORT at runtime)
EXPOSE 8000

# Use gunicorn with uvicorn workers; bind to $PORT provided by Render
ENV PORT=8000
CMD ["sh", "-c", "exec gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT} --access-logfile - --error-logfile -"]