#!/bin/bash

# DSPy Agent with Celery Background Tasks Startup Script

echo "🚀 Starting DSPy Agent with Background Task Processing"
echo "======================================================"

# Check if required services are running
check_service() {
    local service=$1
    local port=$2
    if nc -z localhost $port 2>/dev/null; then
        echo "✅ $service is running on port $port"
    else
        echo "❌ $service is not running on port $port"
        echo "   Please start $service before running this script"
        exit 1
    fi
}

echo "Checking required services..."
check_service "Redis" 6379
check_service "RabbitMQ" 5672


echo ""
echo "Starting background task workers..."

# Start Celery worker for document processing
echo "📄 Starting document processing worker..."
celery -A celery_app worker --loglevel=info --queues=document_processing --concurrency=2 &
DOCUMENT_WORKER_PID=$!

# Start Celery worker for bulk indexing
echo "📊 Starting bulk indexing worker..."
celery -A celery_app worker --loglevel=info --queues=bulk_indexing --concurrency=4 &
BULK_WORKER_PID=$!

# Start Celery beat scheduler (optional, for periodic tasks)
echo "⏰ Starting task scheduler..."
celery -A celery_app beat --loglevel=info &
BEAT_PID=$!

# Wait a moment for workers to start
sleep 3

echo ""
echo "🎯 Starting FastAPI application..."
python main.py &
APP_PID=$!

echo ""
echo "✨ All services started successfully!"
echo "======================================================"
echo "📱 FastAPI App: http://localhost:8000"
echo "📊 Celery Flower (if installed): http://localhost:5555"
echo "🔍 Task queues: document_processing, bulk_indexing"
echo ""
echo "Background task endpoints:"
echo "  POST /tasks/process-pdf - Submit PDF for processing"
echo "  POST /tasks/bulk-index - Submit bulk indexing task"
echo "  GET /tasks/{task_id}/status - Check task status"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $DOCUMENT_WORKER_PID 2>/dev/null
    kill $BULK_WORKER_PID 2>/dev/null
    kill $BEAT_PID 2>/dev/null
    kill $APP_PID 2>/dev/null
    echo "✅ All services stopped"
    exit 0
}

# Set trap for cleanup on script exit
trap cleanup SIGINT SIGTERM

# Wait for all background processes
wait
