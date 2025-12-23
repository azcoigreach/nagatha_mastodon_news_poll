# Makefile for Mastodon Poll Provider

.PHONY: help setup build up down logs clean test verify

help:
	@echo "Nagatha Mastodon News Poll - Available Commands"
	@echo "================================================"
	@echo ""
	@echo "  make setup    - Run initial setup"
	@echo "  make verify   - Verify configuration"
	@echo "  make build    - Build Docker images"
	@echo "  make up       - Start services"
	@echo "  make down     - Stop services"
	@echo "  make logs     - View logs"
	@echo "  make restart  - Restart services"
	@echo "  make clean    - Stop and remove volumes"
	@echo "  make shell    - Open shell in API container"
	@echo "  make example  - Run example workflow"
	@echo ""

setup:
	@./setup.sh

verify:
	@./verify_config.sh

build:
	@docker-compose build

up:
	@docker-compose up -d
	@echo "✅ Services started!"
	@echo "   API: http://localhost:9000"
	@echo "   Docs: http://localhost:9000/docs"

down:
	@docker-compose down

logs:
	@docker-compose logs -f

restart:
	@docker-compose restart

clean:
	@docker-compose down -v
	@echo "🧹 Cleaned up containers and volumes"

shell:
	@docker-compose exec api /bin/bash

example:
	@python example_workflow.py

stats:
	@curl -s http://localhost:9000/stats | python -m json.tool

health:
	@curl -s http://localhost:9000/health | python -m json.tool

pending:
	@curl -s "http://localhost:9000/polls?status_filter=pending" | python -m json.tool
