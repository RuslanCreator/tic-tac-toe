.PHONY: install run test lint format cov check

install:
	uv sync

run:
	uv run uvicorn main:app --reload

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

cov:
	uv run pytest --cov=domain --cov=application --cov=web --cov=infrastructure

check: lint test
