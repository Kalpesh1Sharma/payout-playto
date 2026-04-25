#!/usr/bin/env sh
set -eu

BUILD_FLAG="--build"
if [ "${1:-}" = "--no-build" ]; then
  BUILD_FLAG=""
fi

echo "Starting Playto stack via docker compose..."
docker compose up -d $BUILD_FLAG

echo "Waiting briefly for services to stabilize..."
sleep 12

echo "Checking backend merchants endpoint..."
if curl -fsS "http://localhost:8000/api/v1/merchants/" >/dev/null; then
  echo "Backend reachable."
else
  echo "Smoke check failed on backend endpoint."
  echo "Run: docker compose logs backend worker beat"
  exit 1
fi

echo "Checking frontend URL..."
if curl -fsS "http://localhost:5173" >/dev/null; then
  echo "Frontend reachable."
else
  echo "Smoke check failed on frontend endpoint."
  echo "Run: docker compose logs frontend"
  exit 1
fi

echo "Smoke check complete."
