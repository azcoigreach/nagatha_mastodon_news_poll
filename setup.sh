#!/bin/bash

echo "🚀 Nagatha Mastodon News Poll - Setup Script"
echo "============================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created!"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your credentials:"
    echo "   - MASTODON_ACCESS_TOKEN"
    echo "   - OPENAI_API_KEY"
    echo ""
    echo "Run: nano .env"
    echo ""
    read -p "Press Enter when you've configured .env file..."
else
    echo "✅ .env file found"
fi

# Make scripts executable
echo ""
echo "🔧 Making scripts executable..."
chmod +x docker-entrypoint.sh
echo "✅ Scripts are now executable"

# Check if nagatha_core is running
echo ""
echo "🔍 Checking for Nagatha Core..."
if curl -s http://localhost:8000/api/v1/ping > /dev/null 2>&1; then
    echo "✅ Nagatha Core is running!"
    CORE_RUNNING=true
else
    echo "⚠️  Nagatha Core not detected on localhost:8000"
    echo ""
    echo "Options:"
    echo "  1. Deploy with existing Nagatha Core (recommended)"
    echo "  2. Deploy standalone (includes own RabbitMQ/Redis)"
    echo ""
    read -p "Choose deployment mode (1 or 2): " deploy_mode
    
    if [ "$deploy_mode" = "1" ]; then
        echo ""
        echo "Please start Nagatha Core first:"
        echo "  git clone https://github.com/azcoigreach/nagatha_core"
        echo "  cd nagatha_core"
        echo "  docker-compose up -d"
        echo ""
        echo "Then run this script again."
        exit 1
    else
        CORE_RUNNING=false
    fi
fi

# Build and start services
echo ""
echo "🐳 Building Docker images..."
if [ "$CORE_RUNNING" = false ]; then
    docker-compose -f docker-compose.standalone.yml build
else
    docker-compose build
fi

echo ""
echo "🚀 Starting services..."
if [ "$CORE_RUNNING" = false ]; then
    docker-compose -f docker-compose.standalone.yml up -d
else
    docker-compose up -d
fi

# Wait for services
echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Check health
echo ""
echo "🏥 Checking health..."
if curl -s http://localhost:9000/health > /dev/null 2>&1; then
    echo "✅ Provider API is healthy!"
else
    echo "❌ Provider API not responding. Check logs:"
    echo "   docker-compose logs -f api"
    exit 1
fi

echo ""
echo "============================================="
echo "✅ Setup complete!"
echo ""
echo "📊 Service Status:"
echo "  - Provider API: http://localhost:9000"
echo "  - API Docs: http://localhost:9000/docs"
if [ "$CORE_RUNNING" = true ]; then
    echo "  - Nagatha Core: http://localhost:8000"
fi
echo ""
echo "🎯 Quick Start Commands:"
echo ""
echo "  # View logs"
echo "  docker-compose logs -f"
echo ""
echo "  # Run a news cycle"
echo "  curl -X POST http://localhost:9000/run-cycle"
echo ""
echo "  # View pending polls"
echo "  curl http://localhost:9000/polls?status_filter=pending"
echo ""
echo "  # View statistics"
echo "  curl http://localhost:9000/stats"
echo ""
echo "📚 Read README.md for full documentation"
echo ""
