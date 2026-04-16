from __future__ import annotations

from pydantic import BaseModel, Field


class GexMapLevel(BaseModel):
    net_gamma_exposure: float | None = None
    positive_gamma_exposure: float | None = None
    negative_gamma_exposure: float | None = None
    volume: float | None = None


class GexExposureResponse(BaseModel):
    ticker: str
    zero_gamma_level: float | None = None
    dealer_cluster_upper: float | None = None
    dealer_cluster_lower: float | None = None
    dealer_cluster_upper_range_start: float | None = None
    dealer_cluster_lower_range_start: float | None = None
    total_positive_gamma: float | None = None
    total_negative_gamma: float | None = None
    total_net_gamma: float | None = None
    gex_map: dict[str, GexMapLevel] = Field(default_factory=dict)
