from services.options_data import validate_gex_payload


def test_validate_gex_payload_success_case():
    payload = {
        "ticker": "SPY",
        "zero_gamma_level": 500.0,
        "dealer_cluster_upper": 505.0,
        "dealer_cluster_lower": 495.0,
        "gex_map": {
            "495": {"net_gamma_exposure": -100.0},
            "500": {"net_gamma_exposure": 50.0},
            "505": {"net_gamma_exposure": 150.0},
        },
    }

    result = validate_gex_payload(payload)

    assert result["ok"] is True
    assert result["issues"] == []
    assert result["stats"]["gex_map_count"] == 3


def test_validate_gex_payload_missing_fields():
    payload = {
        "ticker": "SPY",
        "zero_gamma_level": None,
        "dealer_cluster_upper": None,
        "dealer_cluster_lower": None,
        "gex_map": {},
    }

    result = validate_gex_payload(payload)

    assert result["ok"] is False
    assert "Missing zero gamma level." in result["issues"]
    assert "Missing upper dealer cluster." in result["issues"]
    assert "Missing lower dealer cluster." in result["issues"]
    assert "Missing GEX map rows." in result["issues"]
