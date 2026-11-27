# Empório da Música — Agente de Atendimento

Agente em Python que atende clientes de uma loja fictícia de instrumentos musicais em Campo Grande/MS, com respostas fundamentadas nos dados operacionais (`data/`) e no manual de políticas da loja.

## Rodando

```bash
cp .env.example .env
uv sync
uv run python -m emporio.db.seed   # cria var/emporio.db a partir de data/ (só se vazio)
uv run pytest
uv run ruff check . && uv run mypy
```
