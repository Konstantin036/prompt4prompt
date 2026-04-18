import pandas as pd
import pytest
from vizualizacija.consumers import _aggregate_by_feeder


def _make_dt_df():
    return pd.DataFrame({
        "TS": ["AT3", "AT3", "AT3"],
        "Podstanica (SS)": ["S23", "S23", "S23"],
        "Feeder11": ["F11-1", "F11-1", "F11-2"],
        "DT Stanica": ["DT1", "DT2", "DT3"],
        "Snaga (kVA)": [500, 300, 200],
        "S (kVA)": [100.0, 50.0, 80.0],
        "Poslednje merenje": [
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-01-01"),
        ],
    })


def test_aggregate_groups_by_feeder():
    result = _aggregate_by_feeder(_make_dt_df(), kva_per_consumer=1.5)
    assert len(result) == 2


def test_aggregate_sums_s_kva():
    result = _aggregate_by_feeder(_make_dt_df(), kva_per_consumer=1.5)
    f11_1 = result[result["Feeder11"] == "F11-1"].iloc[0]
    assert abs(f11_1["S_kVA"] - 150.0) < 0.01


def test_aggregate_counts_dts():
    result = _aggregate_by_feeder(_make_dt_df(), kva_per_consumer=1.5)
    f11_1 = result[result["Feeder11"] == "F11-1"].iloc[0]
    assert f11_1["DT_count"] == 2


def test_aggregate_computes_consumers():
    result = _aggregate_by_feeder(_make_dt_df(), kva_per_consumer=1.5)
    f11_1 = result[result["Feeder11"] == "F11-1"].iloc[0]
    # 150.0 kVA / 1.5 = 100 consumers
    assert f11_1["consumers"] == 100


def test_aggregate_sorted_descending():
    result = _aggregate_by_feeder(_make_dt_df(), kva_per_consumer=1.5)
    consumers = result["consumers"].tolist()
    assert consumers == sorted(consumers, reverse=True)


def test_aggregate_single_kva():
    result = _aggregate_by_feeder(_make_dt_df(), kva_per_consumer=1.0)
    f11_1 = result[result["Feeder11"] == "F11-1"].iloc[0]
    assert f11_1["consumers"] == 150
