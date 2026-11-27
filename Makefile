.PHONY: install test lint seed chat docker-build docker-chat

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

docker-build:
	docker compose build cli

docker-chat:
	HOST_UID=$$(id -u) HOST_GID=$$(id -g) docker compose run --rm $(if $(REFERENCE_DATE),-e REFERENCE_DATE=$(REFERENCE_DATE)) cli chat $(if $(PHONE),--phone "$(PHONE)") $(if $(DEBUG),--debug)
