#!/bin/bash

# Start services directly without prompts
cd /Users/hamzam/willowv4

echo "Starting Docker services..."
docker compose up -d

echo "Waiting for services to start..."
sleep 5

echo "Services started. Checking status..."
docker compose ps

echo ""
echo "✅ Services are running!"
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"