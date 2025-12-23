#!/bin/bash

echo "🔍 Verifying Configuration"
echo "=========================="
echo ""

# Check credentials
echo "✅ Checking credentials..."
if grep -q "MASTODON_ACCESS_TOKEN=.\{10,\}" .env; then
    echo "   ✓ Mastodon token configured"
else
    echo "   ✗ Mastodon token missing or too short"
fi

if grep -q "OPENAI_API_KEY=sk-" .env; then
    echo "   ✓ OpenAI key configured"
else
    echo "   ✗ OpenAI key missing"
fi

echo ""

# Check service URLs
echo "✅ Checking service configuration..."
if grep -q "nagatha_rabbitmq" .env; then
    echo "   ✓ Using nagatha_core's RabbitMQ (no duplicate)"
else
    echo "   ✗ WARNING: Not using nagatha_core's RabbitMQ"
fi

if grep -q "nagatha_redis" .env; then
    echo "   ✓ Using nagatha_core's Redis (no duplicate)"
else
    echo "   ✗ WARNING: Not using nagatha_core's Redis"
fi

echo ""

# Check docker-compose
echo "✅ Checking docker-compose.yml..."
if ! grep -q "image: rabbitmq" docker-compose.yml; then
    echo "   ✓ No duplicate RabbitMQ service"
else
    echo "   ✗ WARNING: Duplicate RabbitMQ found!"
fi

if ! grep -q "image: redis" docker-compose.yml; then
    echo "   ✓ No duplicate Redis service"
else
    echo "   ✗ WARNING: Duplicate Redis found!"
fi

if grep -q "nagatha_core_nagatha_network" docker-compose.yml; then
    echo "   ✓ Using nagatha_core network"
else
    echo "   ✗ WARNING: Not using nagatha_core network"
fi

echo ""
echo "=========================="
echo "Configuration verified! ✨"
