from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from daily_dash.contracts.common import ArtifactFormat, DeliveryStatus, JsonValue


class ReportArtifact(BaseModel):
    """Rendered output ready for persistence or delivery."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)

    format: ArtifactFormat
    content: str

    created_at: datetime

    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class DeliveryResult(BaseModel):
    """Outcome of sending one artifact to a destination."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    destination: str = Field(min_length=1)

    status: DeliveryStatus

    external_id: str | None = None
    error: str | None = None
