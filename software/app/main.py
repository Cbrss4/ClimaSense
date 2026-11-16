from functools import lru_cache
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import DeviceId, ReadingRecord, StationLocation
from app.repository import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    ReadingRepository,
    StationLocationRepository,
)

app = FastAPI(title="ClimaSense", version="0.1.0")


@lru_cache
def get_repository() -> ReadingRepository:
    return ReadingRepository()


RepositoryDependency = Annotated[ReadingRepository, Depends(get_repository)]


@lru_cache
def get_location_repository() -> StationLocationRepository:
    return StationLocationRepository()


LocationRepositoryDependency = Annotated[
    StationLocationRepository, Depends(get_location_repository)
]


@app.get("/api/v1/station-location")
def station_location(
    device_id: Annotated[DeviceId, Query()],
    repository: LocationRepositoryDependency,
) -> StationLocation | None:
    return repository.get(device_id)


@app.put("/api/v1/station-location")
def save_station_location(
    device_id: Annotated[DeviceId, Query()],
    location: StationLocation,
    repository: LocationRepositoryDependency,
) -> StationLocation:
    return repository.save(device_id, location)


@app.get("/health")
def health() -> dict[str, str]:
    """Confirma que a API está em execução."""
    return {"status": "ok"}


@app.get("/api/v1/readings/latest", response_model=ReadingRecord)
def latest_reading(repository: RepositoryDependency) -> ReadingRecord:
    reading = repository.get_latest()
    if reading is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma leitura disponível",
        )
    return reading


@app.get("/api/v1/readings", response_model=list[ReadingRecord])
def reading_history(
    repository: RepositoryDependency,
    limit: int = Query(
        default=DEFAULT_HISTORY_LIMIT,
        ge=1,
        le=MAX_HISTORY_LIMIT,
    ),
) -> list[ReadingRecord]:
    return repository.list_readings(limit=limit)


@app.get("/api/v1/readings/{reading_id}", response_model=ReadingRecord)
def reading_by_id(
    repository: RepositoryDependency,
    reading_id: int = Path(gt=0),
) -> ReadingRecord:
    reading = repository.get_by_id(reading_id)
    if reading is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leitura não encontrada",
        )
    return reading


@app.get("/api/v1/dashboard/history", response_model=list[ReadingRecord])
def dashboard_history(repository: RepositoryDependency) -> list[ReadingRecord]:
    """Últimas 12 horas, uma leitura por janela de cinco minutos e dispositivo."""
    return repository.dashboard_history()


FRONTEND = FilePath(__file__).resolve().parent.parent / "frontend"
app.mount("/assets", StaticFiles(directory=FRONTEND), name="frontend-assets")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")
