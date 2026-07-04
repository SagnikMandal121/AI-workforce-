.PHONY: help install format lint test run-web run-backend docker-up docker-down

help:
	@echo "AI Workforce scaffold commands"

install:
	@echo "Install frontend and backend dependencies"

format:
	@echo "Format code"

lint:
	@echo "Run lint checks"

test:
	@echo "Run tests"

run-web:
	@echo "Start Next.js app"

run-backend:
	@echo "Start FastAPI backend"

docker-up:
	@echo "Start local infrastructure"

docker-down:
	@echo "Stop local infrastructure"
