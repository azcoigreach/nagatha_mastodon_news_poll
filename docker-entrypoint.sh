#!/bin/bash
set -e

# Wait for RabbitMQ to be ready
wait_for_rabbitmq() {
    local host="${RABBITMQ_HOST:-nagatha_rabbitmq}"
    local port="${RABBITMQ_PORT:-5672}"
    echo "Waiting for RabbitMQ at ${host}:${port}..."
    while ! nc -z "${host}" "${port}"; do
        sleep 1
    done
    echo "RabbitMQ is ready!"
}

# Wait for Redis to be ready
wait_for_redis() {
    local host="${REDIS_HOST:-nagatha_redis}"
    local port="${REDIS_PORT:-6379}"
    echo "Waiting for Redis at ${host}:${port}..."
    while ! nc -z "${host}" "${port}"; do
        sleep 1
    done
    echo "Redis is ready!"
}

# Wait for services if needed
if [ "${WAIT_FOR_SERVICES:-true}" = "true" ]; then
    wait_for_rabbitmq
    wait_for_redis
fi

# Execute the command
exec "$@"
