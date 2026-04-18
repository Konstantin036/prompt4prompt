import pandas as pd
from vizualizacija.stats import compute_stats


def _make_data():
    return {
        "transmission_stations": pd.DataFrame({"Id": [1, 2]}),
        "substations": pd.DataFrame({"Id": [10, 20, 30]}),
        "distribution_substations": pd.DataFrame({
            "Id": [1, 2, 3, 4],
            "Feeder11Id": [100, 100, 200, None],
            "NameplateRating": [100, 200, 300, 50],
        }),
        "feeders11": pd.DataFrame({"Id": [100, 200], "SsId": [10, 20]}),
        "feeders33": pd.DataFrame({"Id": [300], "TsId": [1]}),
        "feeder33_substation": pd.DataFrame({"Feeders33Id": [300], "SubstationsId": [10]}),
    }


def test_compute_stats_no_filter():
    stats = compute_stats(_make_data())
    assert stats["ts_count"] == 2
    assert stats["ss_count"] == 3
    assert stats["dt_count"] == 4
    assert stats["total_power"] == 650


def test_compute_stats_ss_filter():
    stats = compute_stats(_make_data(), ss_ids=[10])
    assert stats["ss_count"] == 1
    assert stats["dt_count"] == 2  # feeder 100 -> DT 1,2
    assert stats["total_power"] == 300


def test_compute_stats_ts_filter():
    stats = compute_stats(_make_data(), ts_ids=[1])
    assert stats["ts_count"] == 1
    assert stats["ss_count"] == 1  # SS 10 linked via feeder33
    assert stats["dt_count"] == 2


def test_compute_stats_feeder11_filter():
    stats = compute_stats(_make_data(), feeder11_filter=200)
    assert stats["dt_count"] == 1
    assert stats["total_power"] == 300
