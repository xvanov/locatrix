#!/bin/bash
# Script to run Playwright tests for Story 3.1 with LocalStack
# This script sets up LocalStack resources, starts SAM Local API, and runs Playwright tests

set -e

echo "🚀 Starting Story 3.1 Playwright Test Suite with LocalStack"
echo ""

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo "❌ SAM CLI not found. Please install it:"
    echo "   brew install aws-sam-cli"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Check if LocalStack is running
if ! curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
    echo "⚠️  LocalStack doesn't appear to be running on port 4566"
    echo "   Please start LocalStack: localstack start"
    echo "   Or run: ./scripts/setup-localstack.sh"
    exit 1
fi

echo "✅ LocalStack is running"

# Setup LocalStack resources
echo "🔧 Setting up LocalStack resources..."
./scripts/setup-localstack.sh

# Check if port 3000 is available
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 3000 is already in use. Using existing API server."
    echo "   If you want to restart, stop the existing server first."
    API_RUNNING=true
else
    API_RUNNING=false
fi

# Build SAM application
echo "📦 Building SAM application..."
sam build

# Start SAM Local API in background if not already running
if [ "$API_RUNNING" = false ]; then
    echo "🌐 Starting SAM Local API on port 3000 with LocalStack..."
    sam local start-api --port 3000 --env-vars env-localstack.json > /tmp/sam-local-api.log 2>&1 &
    SAM_PID=$!
    echo "   SAM Local API started (PID: $SAM_PID)"
    echo "   Logs: /tmp/sam-local-api.log"
    
    # Wait for API to be ready (longer timeout for first-time Docker image builds)
    echo "⏳ Waiting for API to be ready (this may take 1-2 minutes on first run for Docker image builds)..."
    for i in {1..120}; do
        if curl -s http://localhost:3000/health > /dev/null 2>&1; then
            echo "✅ API is ready!"
            break
        fi
        if [ $i -eq 120 ]; then
            echo "❌ API failed to start after 2 minutes"
            echo "   Check logs: tail -f /tmp/sam-local-api.log"
            echo "   Or try running manually: sam local start-api --port 3000 --env-vars env-localstack.json"
            kill $SAM_PID 2>/dev/null || true
            exit 1
        fi
        if [ $((i % 10)) -eq 0 ]; then
            echo "   Still waiting... ($i seconds)"
        fi
        sleep 1
    done
else
    echo "✅ Using existing API server on port 3000"
fi

# Run Playwright tests
echo ""
echo "🧪 Running Playwright tests..."
echo ""

if npm run test:api -- tests/api/story-3-1-preview-pipeline.spec.ts; then
    TEST_RESULT=0
else
    TEST_RESULT=$?
fi

# Cleanup: Stop SAM Local API if we started it
if [ "$API_RUNNING" = false ] && [ ! -z "$SAM_PID" ]; then
    echo ""
    echo "🛑 Stopping SAM Local API..."
    kill $SAM_PID 2>/dev/null || true
    wait $SAM_PID 2>/dev/null || true
    echo "✅ SAM Local API stopped"
fi

# Exit with test result
exit $TEST_RESULT

