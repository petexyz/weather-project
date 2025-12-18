#!/bin/bash
# Master restart script for weather project
# Usage: ./scripts/restart.sh [service]
# Examples:
#   ./scripts/restart.sh          # Restart everything
#   ./scripts/restart.sh web      # Restart only web
#   ./scripts/restart.sh collector # Restart only collector

set -e

SERVICE=${1:-all}

echo "=========================================="
echo "Weather Project Restart Script"
echo "=========================================="
echo ""

case $SERVICE in
  all)
    echo "Stopping all services..."
    podman-compose down
    
    echo "Rebuilding images..."
    podman-compose build --no-cache
    
    echo "Starting services..."
    podman-compose up -d
    ;;
    
  web)
    echo "Restarting web service..."
    podman-compose stop web
    podman-compose build --no-cache web
    podman-compose up -d web
    ;;
    
  collector)
    echo "Restarting collector service..."
    podman-compose stop collector
    podman-compose build --no-cache collector
    podman-compose up -d collector
    ;;
    
  database)
    echo "Restarting database service..."
    podman-compose restart database
    ;;
    
  *)
    echo "Unknown service: $SERVICE"
    echo "Usage: $0 [all|web|collector|database]"
    exit 1
    ;;
esac

echo ""
echo "Waiting for services to be ready..."
sleep 5

echo ""
echo "Service Status:"
echo "----------------------------------------"
podman-compose ps

echo ""
echo "=========================================="
echo "Restart Complete!"
echo "=========================================="
echo ""
echo "Available commands:"
echo "  podman-compose logs -f           # View all logs"
echo "  podman-compose logs -f $SERVICE  # View specific service"
echo "  podman-compose ps                # Check status"
echo ""