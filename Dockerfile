# Multi-Architecture Dockerfile for ResiliZ
# Fully compatible with IBM LinuxONE (s390x), ARM64 (Apple Silicon), and AMD64 (x86_64)

FROM node:20-slim AS frontend-builder
WORKDIR /app/dashboard
COPY dashboard/package.json ./
RUN npm install
COPY dashboard/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install runtime system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and AI code
COPY simulator/ ./simulator/
COPY ai_engine/ ./ai_engine/
COPY backend/ ./backend/

# Copy built frontend assets from builder stage
COPY --from=frontend-builder /app/dashboard/dist ./dashboard/dist

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
