#!/bin/bash
set -e

echo "Starting Docker Compose environment..."
# Build and run containers in detached mode
docker compose up -d --build

echo "Environment started successfully."
echo "Python App (Web UI): http://localhost:3000"
echo "Node.js App (Word/Screenshot Service): http://localhost:3007"
