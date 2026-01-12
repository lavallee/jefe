.PHONY: help lint format typecheck test install dev clean

help:
	@echo "Station Chief - Development Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  make lint       - Run linting checks with ruff"
	@echo "  make format     - Format code with ruff"
	@echo "  make typecheck  - Run type checking with mypy"
	@echo "  make test       - Run tests with pytest"
	@echo "  make install    - Install project with development dependencies"
	@echo "  make dev        - Shortcut for: lint typecheck test"
	@echo "  make clean      - Remove build artifacts and cache files"
	@echo "  make help       - Show this help message"
	@echo ""

lint:
	ruff check src/station_chief tests

format:
	ruff format src/station_chief tests

typecheck:
	mypy src/station_chief

test:
	pytest

install:
	pip install -e ".[dev]"

dev: lint typecheck test
	@echo "✓ All checks passed!"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .eggs -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info 2>/dev/null || true
