from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.database import connect_database, initialize_database
from app.models import ReadingPayload, ReadingRecord

DEFAULT_HISTORY_LIMIT = 100
MAX_HISTORY_LIMIT = 500


def to_utc_iso(value: datetime) -> str:
    """Converte uma data com fuso para ISO 8601 em UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("a data deve informar UTC ou um fuso horário")

    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ReadingRepository:
    """Persiste leituras já validadas usando apenas o módulo sqlite3."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = initialize_database(database_path)

    def save(
        self,
        reading: ReadingPayload,
        *,
        received_at: datetime | None = None,
    ) -> int:
        received_time = received_at or datetime.now(timezone.utc)
        received_at_text = to_utc_iso(received_time)
        captured_at_text = (
            to_utc_iso(reading.captured_at)
            if reading.captured_at is not None
            else None
        )

        with closing(connect_database(self.database_path)) as connection:
            cursor = connection.execute(
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
                    reading.schema_version,
                    reading.device_id,
                    captured_at_text,
                    received_at_text,
                    reading.temperature_c,
                    reading.humidity_pct,
                    reading.pressure_hpa,
                    reading.gas_raw,
                    getattr(reading, "light_raw", None),
                    reading.light_detected,
                    reading.rain_detected,
                    reading.reading_status,
                    None,
                ),
            )
            connection.commit()
            reading_id = cursor.lastrowid

        if reading_id is None:
            raise RuntimeError("o SQLite não retornou o identificador da leitura")

        return reading_id

    def get_latest(self) -> ReadingRecord | None:
        """Retorna a leitura válida ou parcial mais recente."""
        with closing(connect_database(self.database_path)) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM readings
                WHERE status IN ('valid', 'partial')
                ORDER BY received_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()

        if row is None:
            return None

        return ReadingRecord.model_validate(dict(row))

    def list_readings(
        self, limit: int = DEFAULT_HISTORY_LIMIT
    ) -> list[ReadingRecord]:
        """Lista leituras válidas ou parciais da mais recente para a mais antiga."""
        if not 1 <= limit <= MAX_HISTORY_LIMIT:
            raise ValueError(
                f"limit deve estar entre 1 e {MAX_HISTORY_LIMIT}"
            )

        with closing(connect_database(self.database_path)) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM readings
                WHERE status IN ('valid', 'partial')
                ORDER BY received_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [ReadingRecord.model_validate(dict(row)) for row in rows]

    def get_by_id(self, reading_id: int) -> ReadingRecord | None:
        """Retorna uma leitura específica, independentemente do status."""
        if reading_id <= 0:
            raise ValueError("reading_id deve ser maior que zero")

        with closing(connect_database(self.database_path)) as connection:
            row = connection.execute(
                "SELECT * FROM readings WHERE id = ?",
                (reading_id,),
            ).fetchone()

        if row is None:
            return None

        return ReadingRecord.model_validate(dict(row))


    def dashboard_history(self) -> list[ReadingRecord]:
        """Amostragem temporal; não limita 12 horas às últimas 500 mensagens MQTT."""
        now = datetime.now(timezone.utc)
        cutoff = to_utc_iso(now - timedelta(hours=12))
        with closing(connect_database(self.database_path)) as connection:
            rows = connection.execute(
                """
                WITH ranked AS (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY device_id,
                            CAST(strftime('%s', received_at) AS INTEGER) / 300
                        ORDER BY received_at DESC, id DESC
                    ) AS position
                    FROM readings
                    WHERE status IN ('valid', 'partial')
                      AND received_at >= ? AND received_at <= ?
                )
                SELECT readings.* FROM readings
                JOIN ranked ON readings.id = ranked.id
                WHERE ranked.position = 1
                ORDER BY received_at ASC, readings.id ASC
                """,
                (cutoff, to_utc_iso(now)),
            ).fetchall()
        return [ReadingRecord.model_validate(dict(row)) for row in rows]
