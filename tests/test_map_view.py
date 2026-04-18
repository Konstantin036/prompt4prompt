import pandas as pd
import folium
from vizualizacija.map_view import (get_map_center, build_ts_ss_lines, build_ss_dt_lines,
                                    build_ss_dt_chains, build_ts_ss_chains,
                                    _nearest_neighbor_chain, create_map, _valid_coords)


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


def test_valid_coords_rejects_null_island():
    assert _valid_coords(0.0, 0.0) is False
    assert _valid_coords(0.1, 0.1) is False


def test_valid_coords_accepts_real_coords():
    assert _valid_coords(44.0, 21.0) is True


def test_get_map_center_ignores_null_island():
    data = _make_data()
    # dodaj DT sa (0,0) koordinatama — treba da bude ignorisan
    data["distribution_substations"] = pd.concat([
        data["distribution_substations"],
        pd.DataFrame({"Id": [101], "Name": ["Bad"], "Feeder11Id": [None],
                      "NameplateRating": [0], "Latitude": [0.0], "Longitude": [0.0]}),
    ], ignore_index=True)
    center = get_map_center(data)
    assert abs(center[0] - 44.1) < 0.5


def test_nearest_neighbor_chain_ordering():
    start = [0.0, 0.0]
    points = [[0.0, 2.0], [0.0, 1.0], [0.0, 3.0]]
    result = _nearest_neighbor_chain(start, points)
    # treba da bude [1, 2, 3] redosled (svaki put bira najbliži)
    assert result == [[0.0, 1.0], [0.0, 2.0], [0.0, 3.0]]


def test_build_ss_dt_chains_returns_chain_starting_at_ss():
    data = _make_data()
    chains = build_ss_dt_chains(data)
    assert len(chains) == 1
    chain, ss_id, f11_id = chains[0]
    # Chain počinje na SS koordinatama
    assert chain[0] == [44.1, 21.1]
    # Chain ima SS + DT = 2 tačke
    assert len(chain) == 2
    assert ss_id == 10
    assert f11_id == 200


def test_build_ts_ss_chains_returns_chain_starting_at_ts():
    data = _make_data()
    chains = build_ts_ss_chains(data)
    assert len(chains) == 1
    chain, ts_id = chains[0]
    assert chain[0] == [44.0, 21.0]  # počinje na TS
    assert len(chain) == 2            # TS + SS
    assert ts_id == 1


def test_build_ts_ss_lines_with_ss_filter():
    data = _make_data()
    # sa filterom na ss_id=10 treba da vrati 1 liniju
    lines = build_ts_ss_lines(data, ss_id_filter=10)
    assert len(lines) == 1
    # sa filterom na nepostojeci ss_id treba da vrati 0 linija
    lines_empty = build_ts_ss_lines(data, ss_id_filter=99)
    assert len(lines_empty) == 0
