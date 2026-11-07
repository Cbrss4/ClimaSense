from datetime import datetime
from typing import Annotated, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

DeviceId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ClimateSource = Literal["sensor", "simulated", "unavailable"]


class ReadingPayloadBase(BaseModel):
    """Campos comuns às versões aceitas do contrato de dados."""

    model_config = ConfigDict(extra="forbid", strict=True)

    device_id: DeviceId
    captured_at: datetime | None
    temperature_c: float | None
    temperature_source: ClimateSource | None = None
    humidity_pct: float | None = Field(ge=0, le=100)
    humidity_source: ClimateSource | None = None
    pressure_hpa: float | None
    pressure_source: ClimateSource | None = None
    gas_raw: int | None
    light_detected: bool | None
    rain_detected: bool | None

    sensor_fields: ClassVar[tuple[str, ...]] = (
        "temperature_c",
        "humidity_pct",
        "pressure_hpa",
        "gas_raw",
        "light_detected",
        "rain_detected",
    )

    @field_validator("captured_at")
    @classmethod
    def require_timezone_when_captured_at_is_available(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("captured_at deve informar UTC ou um fuso horário")
        return value

    @model_validator(mode="after")
    def infer_and_validate_climate_sources(self):
        for field in ("temperature", "humidity", "pressure"):
            value_field = {
                "temperature": "temperature_c",
                "humidity": "humidity_pct",
                "pressure": "pressure_hpa",
            }[field]
            value = getattr(self, value_field)
            source_field = f"{field}_source"
            source = getattr(self, source_field)
            if source is None:
                source = "sensor" if value is not None else "unavailable"
                setattr(self, source_field, source)
            if (value is None) != (source == "unavailable"):
                raise ValueError(f"{source_field} incompatível com {value_field}")
        return self

    @property
    def is_partial(self) -> bool:
        """Indica se pelo menos uma leitura de sensor está indisponível."""
        return any(getattr(self, field) is None for field in self.sensor_fields)

    @property
    def reading_status(self) -> Literal["valid", "partial"]:
        return "partial" if self.is_partial else "valid"


class ReadingPayloadV1(ReadingPayloadBase):
    """Payload histórico sem a leitura bruta de luminosidade."""

    schema_version: Literal[1]


class ReadingPayloadV2(ReadingPayloadBase):
    """Payload atual com a leitura bruta de luminosidade."""

    schema_version: Literal[2]
    light_raw: int | None = Field(ge=0, le=4095)

    sensor_fields: ClassVar[tuple[str, ...]] = (
        "temperature_c",
        "humidity_pct",
        "pressure_hpa",
        "gas_raw",
        "light_raw",
        "light_detected",
        "rain_detected",
    )


class ReadingPayloadV3(ReadingPayloadBase):
    """Contrato atual com origem explícita para medidas climáticas."""

    schema_version: Literal[3]
    light_raw: int | None = Field(ge=0, le=4095)


ReadingPayload = Annotated[
    ReadingPayloadV1 | ReadingPayloadV2 | ReadingPayloadV3,
    Field(discriminator="schema_version"),
]
READING_PAYLOAD_ADAPTER = TypeAdapter(ReadingPayload)


class ReadingRecord(BaseModel):
    """Leitura armazenada e devolvida pela API."""

    model_config = ConfigDict(extra="forbid")

    id: int
    schema_version: int
    device_id: str
    captured_at: datetime | None
    received_at: datetime
    temperature_c: float | None
    humidity_pct: float | None
    pressure_hpa: float | None
    temperature_source: ClimateSource = "unavailable"
    humidity_source: ClimateSource = "unavailable"
    pressure_source: ClimateSource = "unavailable"
    gas_raw: int | None
    light_raw: int | None
    light_detected: bool | None
    rain_detected: bool | None
    status: Literal["valid", "partial", "invalid"]
    validation_error: str | None
