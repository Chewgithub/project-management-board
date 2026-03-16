#!/bin/sh
set -e

CONTAINER_NAME="pm-backend-local"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  docker rm -f "${CONTAINER_NAME}"
  echo "Stopped and removed ${CONTAINER_NAME}."
else
  echo "No container named ${CONTAINER_NAME} found."
fi
