from fastapi import FastAPI

from emporio import __version__

app = FastAPI(title="Empório da Música - Canal de Atendimento", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
