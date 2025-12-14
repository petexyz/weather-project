#!/bin/bash
echo "Stopping all services..."
podman-compose down

echo "Rebuilding..."
podman-compose build --no-cache

echo "Starting services..."
podman-compose up -d

echo "Waiting for services to be ready..."
sleep 5

echo "Status:"
podman-compose ps

echo ""
echo "Logs (Ctrl+C to exit):"

podman-compose logs -f weather-collector