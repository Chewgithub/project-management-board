# Dockerfile for Project Management App
FROM python:3.12-slim

WORKDIR /app

# Install uv (Python package manager)
RUN pip install uv

# Copy backend and scripts
COPY backend ./backend
COPY scripts ./scripts

# Install backend dependencies
RUN uv pip install fastapi uvicorn openai python-dotenv --system

# Expose port
EXPOSE 8000

# Start backend
CMD ["sh", "./scripts/start.sh"]
