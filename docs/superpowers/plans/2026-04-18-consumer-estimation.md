# Consumer Estimation per F11 Feeder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Streamlit section that estimates the number of electricity consumers per F11 feeder using live voltage and current meter readings, with a user-adjustable kVA-per-consumer slider.

**Architecture:** New `vizualizacija/consumers.py` module with two cached DB queries and a pure aggregation function. `show_consumers()` renders a Plotly horizontal bar chart, a detail expander, and a "no readings" warning table. `app.py` gets one import and one call added after `show_losses()`.

**Tech Stack:** Python, pandas, pymssql, Streamlit, plotly (new dependency)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `vizualizacija/consumers.py` | Create | DB queries, aggregation logic, Streamlit UI |
| `vizualizacija/requirements.txt` | Modify | Add `plotly>=5.0.0` |
| `vizualizacija/app.py` | Modify | Import and call `show_consumers()` |
| `tests/test_consumers.py` | Create | Unit tests for `_aggregate_by_feeder()` |

---

### Task 1: Add plotly to requirements and install it

**Files:**
- Modify: `vizualizacija/requirements.txt`

- [ ] **Step 1: Add plotly to requirements.txt**

Open `vizualizacija/requirements.txt` and add one line so the file reads:

```
streamlit>=1.32.0
streamlit-folium>=0.20.0
folium>=0.17.0
pymssql>=2.3.0
pandas>=2.0.0
pytest>=8.0.0
plotly>=5.0.0
```

- [ ] **Step 2: Install plotly**

```bash
pip install plotly>=5.0.0
```

Expected: plotly installs without errors.

- [ ] **Step 3: Commit**

```bash
git add vizualizacija/requirements.txt
git commit -m "chore: add plotly dependency for consumer estimation chart"
```

---

### Task 2: Write failing tests for `_aggregate_by_feeder`

**Files:**
- Create: `tests/test_consumers.py`

- [ ] **Step 1: Create the test file**

```python
# tests/test_consumers.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd c:/Users/Korisnik/OneDrive/Desktop/hakatoon
pytest tests/test_consumers.py -v
```

Expected: `ModuleNotFoundError: No module named 'vizualizacija.consumers'` or similar — all 6 tests FAIL.

---

### Task 3: Implement `consumers.py` — DB queries and aggregation

**Files:**
- Create: `vizualizacija/consumers.py`

- [ ] **Step 1: Create the file with both SQL queries and `_aggregate_by_feeder`**

```python
# vizualizacija/consumers.py
import pandas as pd
import streamlit as st
from db import get_connection


@st.cache_data
def load_consumer_estimates() -> pd.DataFrame:
    """One row per DT that has at least one V+I pair in MeterReads at its latest timestamp."""
    conn = get_connection()
    try:
        query = """
        WITH latest_ts AS (
            SELECT Mid, MAX(Ts) AS ts
            FROM MeterReads
            WHERE Cid IN (6,7,8,9,10,11)
            GROUP BY Mid
        ),
        pivoted AS (
            SELECT mr.Mid,
                   MAX(CASE WHEN mr.Cid = 6  THEN mr.Val END) AS V_A,
                   MAX(CASE WHEN mr.Cid = 7  THEN mr.Val END) AS V_B,
                   MAX(CASE WHEN mr.Cid = 8  THEN mr.Val END) AS V_C,
                   MAX(CASE WHEN mr.Cid = 9  THEN mr.Val END) AS I_A,
                   MAX(CASE WHEN mr.Cid = 10 THEN mr.Val END) AS I_B,
                   MAX(CASE WHEN mr.Cid = 11 THEN mr.Val END) AS I_C,
                   MAX(lt.ts)                                  AS last_ts
            FROM MeterReads mr
            JOIN latest_ts lt ON lt.Mid = mr.Mid AND mr.Ts = lt.ts
            WHERE mr.Cid IN (6,7,8,9,10,11)
            GROUP BY mr.Mid
        ),
        s_calc AS (
            SELECT Mid,
                   last_ts,
                   ROUND((
                       ISNULL(V_A * I_A, 0) +
                       ISNULL(V_B * I_B, 0) +
                       ISNULL(V_C * I_C, 0)
                   ) / 1000000.0, 2) AS S_kVA
            FROM pivoted
            WHERE (V_A IS NOT NULL AND I_A IS NOT NULL)
               OR (V_B IS NOT NULL AND I_B IS NOT NULL)
               OR (V_C IS NOT NULL AND I_C IS NOT NULL)
        )
        SELECT
            ISNULL((
                SELECT TOP 1 ts2.Name
                FROM Feeder33Substation fs2
                JOIN Feeders33 f33b ON f33b.Id = fs2.Feeders33Id
                JOIN TransmissionStations ts2 ON ts2.Id = f33b.TsId
                WHERE fs2.SubstationsId = f11.SsId
            ), 'N/A')              AS [TS],
            sub.Name               AS [Podstanica (SS)],
            f11.Name               AS [Feeder11],
            d.Name                 AS [DT Stanica],
            d.NameplateRating      AS [Snaga (kVA)],
            sc.S_kVA               AS [S (kVA)],
            sc.last_ts             AS [Poslednje merenje]
        FROM s_calc sc
        JOIN DistributionSubstation d  ON d.MeterId  = sc.Mid
        JOIN Feeders11 f11             ON f11.Id     = d.Feeder11Id
        JOIN Substations sub           ON sub.Id     = f11.SsId
        WHERE sc.S_kVA > 0
        ORDER BY sc.S_kVA DESC
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()


@st.cache_data
def load_no_reading_dts() -> pd.DataFrame:
    """DTs that have no MeterId or no MeterReads rows for V/I channels."""
    conn = get_connection()
    try:
        query = """
        SELECT
            d.Name                                   AS [DT Stanica],
            d.NameplateRating                        AS [Snaga (kVA)],
            ISNULL(f11.Name, 'N/A')                 AS [Feeder11],
            ISNULL(sub.Name, 'N/A')                 AS [Podstanica (SS)],
            CASE
                WHEN d.MeterId IS NULL THEN 'Nema merača'
                ELSE 'Nema očitavanja V/I'
            END                                      AS [Razlog]
        FROM DistributionSubstation d
        LEFT JOIN Feeders11  f11 ON f11.Id  = d.Feeder11Id
        LEFT JOIN Substations sub ON sub.Id = f11.SsId
        WHERE d.MeterId IS NULL
           OR d.MeterId NOT IN (
               SELECT DISTINCT Mid FROM MeterReads
               WHERE Cid IN (6,7,8,9,10,11)
           )
        ORDER BY sub.Name, f11.Name, d.Name
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()


def _aggregate_by_feeder(df: pd.DataFrame, kva_per_consumer: float) -> pd.DataFrame:
    """Pure function: aggregate DT-level DataFrame to F11 feeder level."""
    agg = (
        df.groupby(["TS", "Podstanica (SS)", "Feeder11"])
        .agg(
            S_kVA=("S (kVA)", "sum"),
            DT_count=("DT Stanica", "count"),
        )
        .reset_index()
    )
    agg["consumers"] = (agg["S_kVA"] / kva_per_consumer).round(0).astype(int)
    return agg.sort_values("consumers", ascending=False).reset_index(drop=True)
```

- [ ] **Step 2: Run the tests**

```bash
cd c:/Users/Korisnik/OneDrive/Desktop/hakatoon
pytest tests/test_consumers.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add vizualizacija/consumers.py tests/test_consumers.py
git commit -m "feat: add consumer estimation queries and aggregation logic"
```

---

### Task 4: Implement `show_consumers()` UI

**Files:**
- Modify: `vizualizacija/consumers.py` (append `show_consumers` function)

- [ ] **Step 1: Append `show_consumers` to `consumers.py`**

Add the following function at the end of `vizualizacija/consumers.py`:

```python
def show_consumers() -> None:
    st.subheader("Estimacija broja potrošača po F11 fiderima")

    df = load_consumer_estimates()

    if df.empty:
        st.warning("Nema mernih podataka (V/I) za estimaciju potrošača.")
        _show_no_readings()
        return

    kva_per_consumer = st.slider(
        "kVA po potrošaču",
        min_value=0.5, max_value=5.0, value=1.5, step=0.1,
        help="Prosečna vršna prividna snaga po potrošaču u kVA",
    )

    f11_agg = _aggregate_by_feeder(df, kva_per_consumer)

    col1, col2, col3 = st.columns(3)
    col1.metric("F11 fidera sa merenjima", len(f11_agg))
    col2.metric("DT stanica sa merenjima", len(df))
    col3.metric("Ukupno est. potrošača", f"{f11_agg['consumers'].sum():,}")

    import plotly.express as px

    fig = px.bar(
        f11_agg,
        x="consumers",
        y="Feeder11",
        orientation="h",
        color="Podstanica (SS)",
        hover_data={"TS": True, "S_kVA": ":.1f", "DT_count": True},
        labels={
            "consumers": "Estimirani broj potrošača",
            "Feeder11": "Feeder11",
            "S_kVA": "S ukupno (kVA)",
            "DT_count": "Broj DT",
        },
        height=max(400, len(f11_agg) * 22),
    )
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Detalji po DT stanicama"):
        st.dataframe(
            df[["TS", "Podstanica (SS)", "Feeder11", "DT Stanica",
                "Snaga (kVA)", "S (kVA)", "Poslednje merenje"]],
            use_container_width=True,
            height=400,
        )

    st.divider()
    _show_no_readings()


def _show_no_readings() -> None:
    df_no = load_no_reading_dts()
    st.warning(
        f"**{len(df_no)} stanica bez merenja** — potrebno izvršiti pregled na terenu."
    )
    st.dataframe(df_no, use_container_width=True, height=350)
```

- [ ] **Step 2: Verify tests still pass**

```bash
cd c:/Users/Korisnik/OneDrive/Desktop/hakatoon
pytest tests/test_consumers.py -v
```

Expected: all 6 tests PASS (the new function is UI-only, doesn't affect tested logic).

- [ ] **Step 3: Commit**

```bash
git add vizualizacija/consumers.py
git commit -m "feat: add show_consumers Streamlit UI with plotly bar chart"
```

---

### Task 5: Wire up in app.py

**Files:**
- Modify: `vizualizacija/app.py`

The current `app.py` has `show_losses()` called at line 95. Add the import at the top and the call after `show_losses()`.

- [ ] **Step 1: Add import to app.py**

At the top of `vizualizacija/app.py`, after the existing imports, add:

```python
from consumers import show_consumers
```

So the imports block becomes:

```python
import streamlit as st
from streamlit_folium import st_folium

from db import load_data
from losses import show_losses
from consumers import show_consumers
from map_view import create_map
from stats import show_stats
```

- [ ] **Step 2: Add show_consumers() call after show_losses()**

Find the section in `app.py`:

```python
# --- Analiza gubitaka ---
show_losses()

# --- Tabele ---
```

Replace it with:

```python
# --- Analiza gubitaka ---
show_losses()

# --- Estimacija potrošača ---
show_consumers()

# --- Tabele ---
```

- [ ] **Step 3: Run all tests**

```bash
cd c:/Users/Korisnik/OneDrive/Desktop/hakatoon
pytest tests/ -v
```

Expected: all tests PASS (map_view, stats, consumers).

- [ ] **Step 4: Commit and push**

```bash
git add vizualizacija/app.py
git commit -m "feat: wire consumer estimation section into main app"
git push
```

---

## Self-Review Checklist

- [x] **Spec coverage:** load_consumer_estimates ✅, load_no_reading_dts ✅, _aggregate_by_feeder ✅, slider ✅, plotly bar chart ✅, detail expander ✅, no-readings table ✅
- [x] **Placeholder scan:** No TBD/TODO. All code blocks complete.
- [x] **Type consistency:** `_aggregate_by_feeder(df, kva_per_consumer)` defined in Task 3, used in Task 4 — signature matches. `load_consumer_estimates()` returns DataFrame with column `"S (kVA)"` used consistently.
- [x] **Unit handling:** V(V) × I(mA) / 1,000,000 → kVA baked into SQL `s_calc` CTE.
