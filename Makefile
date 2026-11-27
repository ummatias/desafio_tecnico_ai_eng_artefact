.PHONY: install test lint seed chat

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

seed:
	uv run python -m emporio.db.seed

# make chat PHONE="(67) 99654-7821" DEBUG=1
chat:
	uv run emporio chat $(if $(PHONE),--phone "$(PHONE)") $(if $(DEBUG),--debug)
