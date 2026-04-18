import pandas as pd
import folium
from vizualizacija.map_view import get_map_center, build_ts_ss_lines, build_ss_dt_lines, create_map


def _make_data():
    return {
        "transmission_stations": pd.DataFrame({
            "Id": [1], "Name": ["TS1"], "Latitude": [44.0], "Longitude": [21.0],
        }),
        "substations": pd.DataFrame({
            "Id": [10], "Name": ["SS1"], "Latitude": [44.1], "Longitude": [21.1],
        }),
        "distribution_substations": pd.DataFrame({
            "Id": [100], "Name": ["DT1"], "Feeder11Id": [200],
            "NameplateRating": [630], "Latitude": [44.2], "Longitude": [21.2],
        }),
        "feeders11": pd.DataFrame({
            "Id": [200], "Name": ["F11-1"], "SsId": [10], "TsId": [1],
        }),
        "feeders33": pd.DataFrame({
            "Id": [300], "Name": ["F33-1"], "TsId": [1],
        }),
        "feeder33_substation": pd.DataFrame({
            "Feeders33Id": [300], "SubstationsId": [10],
        }),
    }


def test_get_map_center():
    data = _make_data()
    center = get_map_center(data)
    assert len(center) == 2
    assert abs(center[0] - 44.1) < 0.5
    assert abs(center[1] - 21.1) < 0.5


def test_build_ts_ss_lines():
    lines = build_ts_ss_lines(_make_data())
    assert len(lines) == 1
    ts_coords, ss_coords = lines[0]
    assert ts_coords == [44.0, 21.0]
    assert ss_coords == [44.1, 21.1]


def test_build_ss_dt_lines():
    lines = build_ss_dt_lines(_make_data())
    assert len(lines) == 1
    ss_coords, dt_coords = lines[0]
    assert ss_coords == [44.1, 21.1]
    assert dt_coords == [44.2, 21.2]


def test_create_map_returns_folium_map():
    m = create_map(_make_data())
    assert isinstance(m, folium.Map)
