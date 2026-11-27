from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from emporio.db.engine import make_engine
from emporio.db.seed import seed

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "knowledge"


@pytest.fixture
def empty_engine() -> Iterator[Engine]:
    engine = make_engine("sqlite://")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def seeded_engine() -> Iterator[Engine]:
    engine = make_engine("sqlite://")
    seed(engine, DATA_DIR, KNOWLEDGE_DIR)
    yield engine
    engine.dispose()


@pytest.fixture
def fresh_engine(empty_engine: Engine) -> Engine:
    """Banco semeado próprio do teste, para quem grava (ex.: chamados)."""
    seed(empty_engine, DATA_DIR, KNOWLEDGE_DIR)
    return empty_engine
