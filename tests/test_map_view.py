import pandas as pd
import folium
from vizualizacija.map_view import (get_map_center, build_ts_ss_lines, build_ss_dt_lines,
                                    build_ss_dt_chains, build_ts_ss_chains,
                                    _nearest_neighbor_chain, create_map, _valid_coords)

# Koordinate u Abuja opsegu (9.0–9.2N, 7.3–7.6E) — prolaze sve validacione provjere
_TS_LAT,  _TS_LON  = 9.07,  7.40
_SS_LAT,  _SS_LON  = 9.08,  7.41
_DT_LAT,  _DT_LON  = 9.09,  7.42


def _make_data():
    return {
        "transmission_stations": pd.DataFrame({
            "Id": [1], "Name": ["TS1"], "Latitude": [_TS_LAT], "Longitude": [_TS_LON],
        }),
        "substations": pd.DataFrame({
            "Id": [10], "Name": ["SS1"], "Latitude": [_SS_LAT], "Longitude": [_SS_LON],
        }),
        "distribution_substations": pd.DataFrame({
            "Id": [100], "Name": ["DT1"], "Feeder11Id": [200],
            "NameplateRating": [630], "Latitude": [_DT_LAT], "Longitude": [_DT_LON],
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
    assert abs(center[0] - _SS_LAT) < 0.5
    assert abs(center[1] - _SS_LON) < 0.5


def test_build_ts_ss_lines():
    lines = build_ts_ss_lines(_make_data())
    assert len(lines) == 1
    ts_coords, ss_coords = lines[0]
    assert ts_coords == [_TS_LAT, _TS_LON]
    assert ss_coords == [_SS_LAT, _SS_LON]


def test_build_ss_dt_lines():
    lines = build_ss_dt_lines(_make_data())
    assert len(lines) == 1
    ss_coords, dt_coords = lines[0]
    assert ss_coords == [_SS_LAT, _SS_LON]
    assert dt_coords == [_DT_LAT, _DT_LON]


def test_create_map_returns_folium_map():
    m = create_map(_make_data())
    assert isinstance(m, folium.Map)


def test_valid_coords_rejects_null_island():
    assert _valid_coords(0.0, 0.0) is False
    assert _valid_coords(0.1, 0.1) is False


def test_valid_coords_accepts_real_coords():
    # Tipicne Abuja koordinate
    assert _valid_coords(9.07, 7.40) is True
    assert _valid_coords(9.11, 7.43) is True


def test_valid_coords_rejects_placeholder_9_7():
    # TS bez GPS podataka (BIDA, LOKOJA, MINNA itd.)
    assert _valid_coords(9.0, 7.0) is False
    assert _valid_coords(9.001, 7.0003) is False


def test_valid_coords_rejects_swapped_abuja():
    # White House dt — zamijenjeni lat/lon
    assert _valid_coords(7.48, 9.07) is False


def test_get_map_center_ignores_null_island():
    data = _make_data()
    data["distribution_substations"] = pd.concat([
        data["distribution_substations"],
        pd.DataFrame({"Id": [101], "Name": ["Bad"], "Feeder11Id": [None],
                      "NameplateRating": [0], "Latitude": [0.0], "Longitude": [0.0]}),
    ], ignore_index=True)
    center = get_map_center(data)
    assert abs(center[0] - _SS_LAT) < 0.5


def test_nearest_neighbor_chain_ordering():
    start = [0.0, 0.0]
    points = [[0.0, 2.0], [0.0, 1.0], [0.0, 3.0]]
    result = _nearest_neighbor_chain(start, points)
    assert result == [[0.0, 1.0], [0.0, 2.0], [0.0, 3.0]]


def test_build_ss_dt_chains_returns_chain_starting_at_ss():
    data = _make_data()
    chains = build_ss_dt_chains(data)
    assert len(chains) == 1
    chain, ss_id, f11_id = chains[0]
    assert chain[0] == [_SS_LAT, _SS_LON]
    assert len(chain) == 2
    assert ss_id == 10
    assert f11_id == 200


def test_build_ts_ss_chains_returns_chain_starting_at_ts():
    data = _make_data()
    chains = build_ts_ss_chains(data)
    assert len(chains) == 1
    chain, ts_id = chains[0]
    assert chain[0] == [_TS_LAT, _TS_LON]
    assert len(chain) == 2
    assert ts_id == 1


def test_build_ts_ss_lines_with_ss_filter():
    data = _make_data()
    lines = build_ts_ss_lines(data, ss_id_filter=10)
    assert len(lines) == 1
    lines_empty = build_ts_ss_lines(data, ss_id_filter=99)
    assert len(lines_empty) == 0
