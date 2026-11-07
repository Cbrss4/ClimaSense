import sqlite3
from contextlib import closing

import pytest

from app.database import DATABASE_VERSION, connect_database, initialize_database


EXPECTED_COLUMNS = [
    "id",
    "schema_version",
    "device_id",
    "captured_at",
    "received_at",
    "temperature_c",
    "temperature_source",
    "humidity_pct",
    "humidity_source",
    "pressure_hpa",
    "pressure_source",
    "gas_raw",
    "light_raw",
    "light_detected",
    "rain_detected",
    "status",
    "validation_error",
]


def test_initialize_database_creates_versioned_readings_table(tmp_path) -> None:
    database_path = tmp_path / "nested" / "test.db"

    initialized_path = initialize_database(database_path)
    initialize_database(database_path)

    assert initialized_path == database_path
    assert database_path.exists()

    with closing(connect_database(database_path)) as connection:
        columns = connection.execute("PRAGMA table_info(readings)").fetchall()
        database_version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert [column["name"] for column in columns] == EXPECTED_COLUMNS
    assert database_version == DATABASE_VERSION


def test_readings_table_accepts_initial_contract_values(tmp_path) -> None:
    database_path = tmp_path / "test.db"
    initialize_database(database_path)

    with closing(connect_database(database_path)) as connection:
        connection.execute(
            """
            INSERT INTO readings (
                schema_version,
                device_id,
                captured_at,
                received_at,
                temperature_c,
                humidity_pct,
                pressure_hpa,
                gas_raw,
                light_raw,
                light_detected,
                rain_detected,
                status,
                validation_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "station-01",
                None,
                "2026-09-30T18:30:00Z",
                25.4,
                61.2,
                1012.8,
                840,
                4095,
                1,
                0,
                "valid",
                None,
            ),
        )

        row = connection.execute("SELECT * FROM readings").fetchone()

    assert row is not None
    assert row["device_id"] == "station-01"
    assert row["captured_at"] is None
    assert row["light_raw"] == 4095
    assert row["light_detected"] == 1
    assert row["rain_detected"] == 0


@pytest.mark.parametrize(
    ("humidity_pct", "status"),
    [(-0.1, "valid"), (100.1, "valid"), (50.0, "unknown")],
)
def test_readings_table_rejects_invalid_constraints(
    tmp_path, humidity_pct: float, status: str
) -> None:
    database_path = tmp_path / "test.db"
    initialize_database(database_path)

    with closing(connect_database(database_path)) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO readings (
                    schema_version,
                    device_id,
                    received_at,
                    humidity_pct,
                    status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (1, "station-01", "2026-09-30T18:30:00Z", humidity_pct, status),
            )


@pytest.mark.parametrize("light_raw", [-1, 4096])
def test_readings_table_rejects_light_raw_outside_adc_range(
    tmp_path, light_raw: int
) -> None:
    database_path = tmp_path / "test.db"
    initialize_database(database_path)

    with closing(connect_database(database_path)) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO readings (
                    schema_version,
                    device_id,
                    received_at,
                    light_raw,
                    status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (2, "station-01", "2026-09-30T18:30:00Z", light_raw, "valid"),
            )


def test_initialize_database_migrates_version_1_without_losing_rows(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.executescript(
            """
            CREATE TABLE readings (
                id INTEGER PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                captured_at TEXT,
                received_at TEXT NOT NULL,
                temperature_c REAL,
                humidity_pct REAL,
                pressure_hpa REAL,
                gas_raw INTEGER,
                light_detected INTEGER,
                rain_detected INTEGER,
                status TEXT NOT NULL,
                validation_error TEXT
            );
            INSERT INTO readings (
                schema_version, device_id, received_at, status
            ) VALUES (1, 'station-01', '2026-09-30T18:30:00Z', 'partial');
            PRAGMA user_version = 1;
            """
        )

    initialize_database(database_path)

    with closing(connect_database(database_path)) as connection:
        columns = connection.execute("PRAGMA table_info(readings)").fetchall()
        row = connection.execute("SELECT * FROM readings WHERE id = 1").fetchone()
        database_version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert "light_raw" in [column["name"] for column in columns]
    assert row is not None
    assert row["light_raw"] is None
    assert database_version == DATABASE_VERSION
