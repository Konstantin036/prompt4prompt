import pandas as pd
from vizualizacija.stats import compute_stats


def test_compute_stats_counts():
    data = {
        "transmission_stations": pd.DataFrame({"Id": [1, 2]}),
        "substations": pd.DataFrame({"Id": [1, 2, 3]}),
        "distribution_substations": pd.DataFrame({
            "Id": [1, 2, 3, 4],
            "NameplateRating": [100, 200, 300, None],
        }),
    }
    stats = compute_stats(data)
    assert stats["ts_count"] == 2
    assert stats["ss_count"] == 3
    assert stats["dt_count"] == 4
    assert stats["total_power"] == 600
