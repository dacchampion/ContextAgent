from services.options_data import parse_gex_payloads


def test_parse_gex_payloads_extracts_expected_fields():
    captures = [
        {
            "url": "https://provider.example/api/gex-levels",
            "status": 200,
            "method": "GET",
            "data": {
                "zeroGamma": 551.25,
                "dealerClusterUpper": [554.0, 557.5],
                "dealerClusterLower": [{"level": 548.0}, {"price": 545.5}],
                "maxY1": 560.0,
                "minY0": 542.0,
                "gexMap": [
                    {
                        "strike": 545,
                        "gammaExposure": -1200000,
                        "callGammaExposure": 400000,
                        "putGammaExposure": -1600000,
                    },
                    {
                        "strike": 550,
                        "gammaExposure": 1800000,
                        "callGammaExposure": 2200000,
                        "putGammaExposure": -400000,
                    },
                ],
            },
        }
    ]

    result = parse_gex_payloads("spy", captures)

    assert result["ticker"] == "SPY"
    assert result["zero_gamma_level"] == 551.25
    assert result["dealer_cluster_upper"] == 554.0
    assert result["dealer_cluster_lower"] == 548.0
    assert result["dealer_cluster_upper_range_start"] == 560.0
    assert result["dealer_cluster_lower_range_start"] == 542.0
    assert list(result["gex_map"].keys()) == ["545", "550"]


def test_parse_gex_payloads_dedupes_rows_across_sources():
    row = {"strike": 500, "gammaExposure": 1000}
    captures = [
        {"url": "https://x/api/gex", "status": 200, "method": "GET", "data": {"gexMap": [row]}},
        {"url": "wss://x/ws", "status": "ws", "method": "WS", "data": {"gexMap": [row]}},
    ]

    result = parse_gex_payloads("qqq", captures)

    assert result["ticker"] == "QQQ"
    assert len(result["gex_map"]) == 1


def test_parse_gex_payloads_supports_candlestick_graph_payload_shape():
    captures = [
        {
            "url": "https://api.example/get_candlestick_graph_data_v2?select_ticker=AAPL",
            "status": 200,
            "method": "GET",
            "data": {
                "zeroGamma": 165.0,
                "gamma_zone_add": [170.0, 175.0],
                "gamma_zone_sub": [160.0, 155.0],
                "maxY1": 180.0,
                "minY0": 150.0,
                "df_gex2": {
                    "StrikePrice": [160.0, 165.0, 170.0],
                    "TotalCallGEX": [100.0, 700.0, 1200.0],
                    "TotalPutGEX": [-1100.0, -200.0, -300.0],
                },
                "df_volume_table": {
                    "StrikePrice": [160.0, 165.0, 170.0],
                    "Volume": [10, 20, 30],
                },
            },
        }
    ]

    result = parse_gex_payloads("aapl", captures)

    assert result["zero_gamma_level"] == 165.0
    assert result["dealer_cluster_upper"] == 170.0
    assert result["dealer_cluster_lower"] == 160.0
    assert result["dealer_cluster_upper_range_start"] == 180.0
    assert result["dealer_cluster_lower_range_start"] == 150.0
    assert list(result["gex_map"].keys()) == ["160", "165", "170"]
    assert [row["net_gamma_exposure"] for row in result["gex_map"].values()] == [-1000.0, 500.0, 900.0]
    assert [row["positive_gamma_exposure"] for row in result["gex_map"].values()] == [100.0, 700.0, 1200.0]
    assert [row["negative_gamma_exposure"] for row in result["gex_map"].values()] == [-1100.0, -200.0, -300.0]
    assert [row["volume"] for row in result["gex_map"].values()] == [10.0, 20.0, 30.0]
    assert result["total_positive_gamma"] == 2000.0
    assert result["total_negative_gamma"] == -1600.0
    assert result["total_net_gamma"] == 400.0


def test_parse_gex_payloads_prefers_requested_ticker_over_previous_capture():
    captures = [
        {
            "url": "https://api.example/get_candlestick_graph_data_v2?select_ticker=TXN&gex_type=GROSS",
            "status": 200,
            "method": "GET",
            "data": {
                "zeroGamma": 190.0,
                "gamma_zone_add": [202.85],
                "gamma_zone_sub": [182.15],
                "maxY1": 210.0,
                "minY0": 180.0,
                "df_gex2": {
                    "StrikePrice": [190.0],
                    "TotalCallGEX": [20.0],
                    "TotalPutGEX": [-10.0],
                },
            },
        },
        {
            "url": "https://api.example/get_candlestick_graph_data_v2?select_ticker=AAPL&gex_type=GROSS",
            "status": 200,
            "method": "GET",
            "data": {
                "zeroGamma": 250.0,
                "gamma_zone_add": [255.0],
                "gamma_zone_sub": [245.0],
                "maxY1": 260.0,
                "minY0": 240.0,
                "df_gex2": {
                    "StrikePrice": [250.0],
                    "TotalCallGEX": [30.0],
                    "TotalPutGEX": [-10.0],
                },
            },
        },
    ]

    result = parse_gex_payloads("AAPL", captures)

    assert result["zero_gamma_level"] == 250.0
    assert result["dealer_cluster_upper"] == 255.0
    assert result["dealer_cluster_lower"] == 245.0
    assert result["dealer_cluster_upper_range_start"] == 260.0
    assert result["dealer_cluster_lower_range_start"] == 240.0
    assert list(result["gex_map"].keys()) == ["250"]
