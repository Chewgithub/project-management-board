#!/bin/sh
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE_NAME="pm-backend"
CONTAINER_NAME="pm-backend-local"
VOLUME_NAME="pm-backend-data"
PORT="8000"
ENV_FILE="${REPO_ROOT}/.env"

cd "$REPO_ROOT"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Removing existing container ${CONTAINER_NAME}..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

if lsof -i tcp:${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port ${PORT} is already in use. Stop the process/container using it first."
  exit 1
fi

echo "Building Docker image ${IMAGE_NAME}..."
docker build -t "${IMAGE_NAME}" .

if ! docker volume ls --format '{{.Name}}' | grep -q "^${VOLUME_NAME}$"; then
  echo "Creating Docker volume ${VOLUME_NAME}..."
  docker volume create "${VOLUME_NAME}" >/dev/null
fi

echo "Starting container ${CONTAINER_NAME} on port ${PORT}..."

DOCKER_ENV_ARGS=""
if [ -f "${ENV_FILE}" ]; then
  DOCKER_ENV_ARGS="--env-file ${ENV_FILE}"
else
  echo "Warning: .env file not found at ${ENV_FILE}. AI endpoints may fail without OPENAI_API_KEY."
fi

docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT}:8000" \
  -v "${VOLUME_NAME}:/app/backend/data" \
  ${DOCKER_ENV_ARGS} \
  "${IMAGE_NAME}"

echo "Backend is running at http://localhost:${PORT}"
echo "Health check: http://localhost:${PORT}/api/ping"
