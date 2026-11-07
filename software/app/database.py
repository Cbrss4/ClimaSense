import os
import sqlite3
from contextlib import closing
from pathlib import Path

DATABASE_VERSION = 3
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "station.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    device_id TEXT NOT NULL CHECK (length(trim(device_id)) > 0),
    captured_at TEXT,
    received_at TEXT NOT NULL,
    temperature_c REAL,
    temperature_source TEXT NOT NULL DEFAULT 'sensor',
    humidity_pct REAL CHECK (
        humidity_pct IS NULL OR humidity_pct BETWEEN 0 AND 100
    ),
    humidity_source TEXT NOT NULL DEFAULT 'sensor',
    pressure_hpa REAL,
    pressure_source TEXT NOT NULL DEFAULT 'sensor',
    gas_raw INTEGER,
    light_raw INTEGER CHECK (
        light_raw IS NULL OR light_raw BETWEEN 0 AND 4095
    ),
    light_detected INTEGER CHECK (
        light_detected IS NULL OR light_detected IN (0, 1)
    ),
    rain_detected INTEGER CHECK (
        rain_detected IS NULL OR rain_detected IN (0, 1)
    ),
    status TEXT NOT NULL CHECK (status IN ('valid', 'partial', 'invalid')),
    validation_error TEXT
);
"""


def resolve_database_path(database_path: str | Path | None = None) -> Path:
    """Resolve o caminho explícito, a variável de ambiente ou o padrão local."""
    if database_path is not None:
        return Path(database_path)

    configured_path = os.getenv("WEATHER_DATABASE_PATH")
    if configured_path:
        return Path(configured_path)

    return DEFAULT_DATABASE_PATH


def connect_database(database_path: str | Path | None = None) -> sqlite3.Connection:
    """Abre uma conexão SQLite configurada para uso pela aplicação."""
    path = resolve_database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_database(database_path: str | Path | None = None) -> Path:
    """Cria o esquema inicial de forma idempotente e retorna o caminho usado."""
    path = resolve_database_path(database_path)

    with closing(connect_database(path)) as connection:
        connection.executescript(SCHEMA_SQL)
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(readings)").fetchall()
        }
        if "light_raw" not in columns:
            connection.execute(
                """
                ALTER TABLE readings
                ADD COLUMN light_raw INTEGER CHECK (
                    light_raw IS NULL OR light_raw BETWEEN 0 AND 4095
                )
                """
            )
        for field in ("temperature", "humidity", "pressure"):
            column = f"{field}_source"
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE readings ADD COLUMN {column} TEXT NOT NULL DEFAULT 'sensor'"
                )
            value_column = {
                "temperature": "temperature_c",
                "humidity": "humidity_pct",
                "pressure": "pressure_hpa",
            }[field]
            connection.execute(
                f"UPDATE readings SET {column} = 'unavailable' "
                f"WHERE {value_column} IS NULL"
            )
        connection.execute(f"PRAGMA user_version = {DATABASE_VERSION}")
        connection.commit()

    return path


if __name__ == "__main__":
    initialized_path = initialize_database()
    print(f"Banco inicializado em: {initialized_path}")
