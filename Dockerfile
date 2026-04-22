# Stage 1: Build the Next.js frontend
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Run the FastAPI backend
FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY backend ./backend
COPY scripts ./scripts

RUN uv pip install fastapi uvicorn openai python-dotenv --system

# Copy built frontend so FastAPI can serve it at /
COPY --from=frontend-builder /app/frontend/.next ./frontend/.next

EXPOSE 8000

CMD ["sh", "./scripts/start.sh"]
