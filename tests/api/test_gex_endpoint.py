# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.v1.gex as gex_api
from services import options_data as options_service


app = FastAPI()
app.include_router(gex_api.router)
client = TestClient(app)


def test_gex_endpoint_ok(monkeypatch):
    async def fake_fetch(ticker: str, gex_filter_preset: str = "All"):
        return {
            "ticker": ticker.upper(),
            "zero_gamma_level": 500.0,
            "dealer_cluster_upper": 505.0,
            "dealer_cluster_lower": 495.0,
            "dealer_cluster_upper_range_start": 510.0,
            "dealer_cluster_lower_range_start": 490.0,
            "gex_map": {"500": {"net_gamma_exposure": 123.0}},
        }

    monkeypatch.setattr(gex_api, "fetch_options_gex", fake_fetch)

    response = client.get("/gex/exposure-map", params={"ticker": "spy"})

    assert response.status_code == 200
    assert response.json()["ticker"] == "SPY"
    assert response.json()["zero_gamma_level"] == 500.0


def test_gex_endpoint_maps_fetch_error(monkeypatch):
    async def fake_fetch(ticker: str, gex_filter_preset: str = "All"):
        raise options_service.OptionsDataFetchError("fetch failed")

    monkeypatch.setattr(gex_api, "fetch_options_gex", fake_fetch)

    response = client.get("/gex/exposure-map", params={"ticker": "spy"})

    assert response.status_code == 502
    assert response.json()["detail"] == "fetch failed"
