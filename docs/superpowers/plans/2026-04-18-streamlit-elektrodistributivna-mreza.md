# Streamlit Elektrodistributivna Mreža Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit web app that visualizes an MSSQL electrical distribution network on an interactive Folium map with filters, sidebar stats, and raw data tables.

**Architecture:** Modular Python package in `vizualizacija/` with `db.py` (data loading), `map_view.py` (Folium map), `stats.py` (sidebar stats), and `app.py` (Streamlit entry point). Data cached via `@st.cache_data`, refreshable on demand.

**Tech Stack:** Python 3.10+, Streamlit, streamlit-folium, Folium, pymssql, pandas, pytest

---

## File Map

| File | Responsibility |
|---|---|
| `vizualizacija/db.py` | DB connection, `load_data()` with cache |
| `vizualizacija/map_view.py` | `create_map()`, topology builders |
| `vizualizacija/stats.py` | `show_stats()` sidebar block |
| `vizualizacija/app.py` | Streamlit layout, sidebar, map, tables |
| `vizualizacija/requirements.txt` | Python dependencies |
| `tests/test_map_view.py` | Unit tests for pure map logic |
| `tests/test_stats.py` | Unit tests for stats calculations |
| `CLAUDE.md` | Project documentation |

---

## Task 1: Setup strukture i zavisnosti

**Files:**
- Create: `vizualizacija/requirements.txt`
- Create: `vizualizacija/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Kreiraj direktorijume**

```bash
mkdir -p vizualizacija tests
touch vizualizacija/__init__.py tests/__init__.py
```

- [ ] **Step 2: Kreiraj `vizualizacija/requirements.txt`**

```
streamlit>=1.32.0
streamlit-folium>=0.20.0
folium>=0.17.0
pymssql>=2.3.0
pandas>=2.0.0
pytest>=8.0.0
```

- [ ] **Step 3: Instaliraj zavisnosti**

```bash
pip install -r vizualizacija/requirements.txt
```

Očekivano: sve biblioteke instalirane bez grešaka. Ako `pymssql` ne može da se instalira na Windows, koristi alternativu: `pip install pymssql --only-binary :all:` ili zameni sa `pyodbc` (potreban ODBC Driver 17).

- [ ] **Step 4: Verifikuj instalaciju**

```bash
python -c "import streamlit, folium, pymssql, pandas; print('OK')"
```

Očekivano: `OK`

- [ ] **Step 5: Commit**

```bash
git add vizualizacija/requirements.txt vizualizacija/__init__.py tests/__init__.py
git commit -m "feat: setup vizualizacija project structure"
```

---

## Task 2: `db.py` — Konekcija i učitavanje podataka

**Files:**
- Create: `vizualizacija/db.py`

- [ ] **Step 1: Napiši `vizualizacija/db.py`**

```python
import pymssql
import pandas as pd
import streamlit as st

_DB_CONFIG = {
    "server": "localhost",
    "port": 1433,
    "database": "SotexHackathon",
    "user": "sa",
    "password": "SotexSolutions123!",
}


def get_connection():
    return pymssql.connect(**_DB_CONFIG)


@st.cache_data
def load_data() -> dict[str, pd.DataFrame]:
    conn = get_connection()
    try:
        return {
            "transmission_stations": pd.read_sql("SELECT * FROM TransmissionStations", conn),
            "substations": pd.read_sql("SELECT * FROM Substations", conn),
            "distribution_substations": pd.read_sql("SELECT * FROM DistributionSubstation", conn),
            "feeders11": pd.read_sql("SELECT * FROM Feeders11", conn),
            "feeders33": pd.read_sql("SELECT * FROM Feeders33 WHERE IsDeleted = 0", conn),
            "feeder33_substation": pd.read_sql("SELECT * FROM Feeder33Substation", conn),
        }
    finally:
        conn.close()
```

- [ ] **Step 2: Testiraj konekciju**

```bash
cd vizualizacija
python -c "from db import load_data; d = load_data(); print({k: len(v) for k, v in d.items()})"
```

Očekivano: dictionary sa brojevima redova po tabeli, npr. `{'transmission_stations': 5, 'substations': 20, ...}`

- [ ] **Step 3: Commit**

```bash
git add vizualizacija/db.py
git commit -m "feat: add db connection and load_data with cache"
```

---

## Task 3: `stats.py` — Sidebar statistike

**Files:**
- Create: `vizualizacija/stats.py`
- Create: `tests/test_stats.py`

- [ ] **Step 1: Napiši test u `tests/test_stats.py`**

```python
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
```

- [ ] **Step 2: Pokreni test da vidiš da pada**

```bash
pytest tests/test_stats.py -v
```

Očekivano: `FAILED` — `ImportError: cannot import name 'compute_stats'`

- [ ] **Step 3: Napiši `vizualizacija/stats.py`**

```python
import streamlit as st
import pandas as pd


def compute_stats(data: dict) -> dict:
    dt = data["distribution_substations"]
    return {
        "ts_count": len(data["transmission_stations"]),
        "ss_count": len(data["substations"]),
        "dt_count": len(dt),
        "total_power": int(dt["NameplateRating"].sum(skipna=True)),
    }


def show_stats(data: dict) -> None:
    s = compute_stats(data)
    st.sidebar.subheader("Statistike mreže")
    col1, col2 = st.sidebar.columns(2)
    col1.metric("TS Stanice", s["ts_count"])
    col2.metric("Substations", s["ss_count"])
    col1.metric("DT Stanice", s["dt_count"])
    col2.metric("Snaga (kVA)", f"{s['total_power']:,}")
```

- [ ] **Step 4: Pokreni test da prođe**

```bash
pytest tests/test_stats.py -v
```

Očekivano: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add vizualizacija/stats.py tests/test_stats.py
git commit -m "feat: add stats computation and sidebar display"
```

---

## Task 4: `map_view.py` — Topologija i mapa

**Files:**
- Create: `vizualizacija/map_view.py`
- Create: `tests/test_map_view.py`

- [ ] **Step 1: Napiši testove u `tests/test_map_view.py`**

```python
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
```

- [ ] **Step 2: Pokreni testove da vidiš da padaju**

```bash
pytest tests/test_map_view.py -v
```

Očekivano: `FAILED` — `ImportError`

- [ ] **Step 3: Napiši `vizualizacija/map_view.py`**

```python
import folium
import pandas as pd


def get_map_center(data: dict) -> list[float]:
    lats, lons = [], []
    for key in ("transmission_stations", "substations", "distribution_substations"):
        df = data[key]
        lats.extend(df["Latitude"].dropna().tolist())
        lons.extend(df["Longitude"].dropna().tolist())
    if not lats:
        return [44.0, 21.0]
    return [sum(lats) / len(lats), sum(lons) / len(lons)]


def build_ts_ss_lines(data: dict) -> list[tuple]:
    ts = data["transmission_stations"].set_index("Id")
    ss = data["substations"].set_index("Id")
    f33 = data["feeders33"].set_index("Id")
    lines = []
    for _, row in data["feeder33_substation"].iterrows():
        f33_id = row["Feeders33Id"]
        ss_id = row["SubstationsId"]
        if f33_id not in f33.index or ss_id not in ss.index:
            continue
        ts_id = f33.loc[f33_id, "TsId"]
        if pd.isna(ts_id) or int(ts_id) not in ts.index:
            continue
        ts_row = ts.loc[int(ts_id)]
        ss_row = ss.loc[ss_id]
        if pd.isna(ts_row["Latitude"]) or pd.isna(ss_row["Latitude"]):
            continue
        lines.append(
            ([float(ts_row["Latitude"]), float(ts_row["Longitude"])],
             [float(ss_row["Latitude"]), float(ss_row["Longitude"])])
        )
    return lines


def build_ss_dt_lines(data: dict, feeder11_filter=None, substation_filter=None) -> list[tuple]:
    ss = data["substations"].set_index("Id")
    f11 = data["feeders11"].set_index("Id")
    dt = data["distribution_substations"].copy()

    if feeder11_filter is not None:
        dt = dt[dt["Feeder11Id"] == feeder11_filter]
    if substation_filter is not None:
        valid_ids = f11[f11["SsId"] == substation_filter].index.tolist()
        dt = dt[dt["Feeder11Id"].isin(valid_ids)]

    lines = []
    for _, dt_row in dt.iterrows():
        f11_id = dt_row["Feeder11Id"]
        if pd.isna(f11_id) or int(f11_id) not in f11.index:
            continue
        ss_id = f11.loc[int(f11_id), "SsId"]
        if pd.isna(ss_id) or int(ss_id) not in ss.index:
            continue
        ss_row = ss.loc[int(ss_id)]
        if pd.isna(dt_row["Latitude"]) or pd.isna(ss_row["Latitude"]):
            continue
        lines.append(
            ([float(ss_row["Latitude"]), float(ss_row["Longitude"])],
             [float(dt_row["Latitude"]), float(dt_row["Longitude"])])
        )
    return lines


def create_map(data: dict, feeder11_filter=None, substation_filter=None) -> folium.Map:
    center = get_map_center(data)
    m = folium.Map(location=center, zoom_start=10)

    ts_group = folium.FeatureGroup(name="Transmission Stations", show=True)
    ss_group = folium.FeatureGroup(name="Substations", show=True)
    dt_group = folium.FeatureGroup(name="Distribution Substations (DT)", show=True)
    ts_ss_group = folium.FeatureGroup(name="TS → SS veze", show=True)
    ss_dt_group = folium.FeatureGroup(name="SS → DT veze", show=True)

    for _, row in data["transmission_stations"].iterrows():
        if pd.isna(row["Latitude"]):
            continue
        folium.Marker(
            location=[float(row["Latitude"]), float(row["Longitude"])],
            popup=f"<b>{row['Name']}</b><br>Id: {row['Id']}",
            icon=folium.Icon(color="blue", icon="bolt", prefix="fa"),
        ).add_to(ts_group)

    for _, row in data["substations"].iterrows():
        if pd.isna(row["Latitude"]):
            continue
        folium.Marker(
            location=[float(row["Latitude"]), float(row["Longitude"])],
            popup=f"<b>{row['Name']}</b><br>Id: {row['Id']}",
            icon=folium.Icon(color="orange", icon="plug", prefix="fa"),
        ).add_to(ss_group)

    f11 = data["feeders11"].set_index("Id")
    dt_data = data["distribution_substations"].copy()
    if feeder11_filter is not None:
        dt_data = dt_data[dt_data["Feeder11Id"] == feeder11_filter]
    if substation_filter is not None:
        valid_ids = f11[f11["SsId"] == substation_filter].index.tolist()
        dt_data = dt_data[dt_data["Feeder11Id"].isin(valid_ids)]

    for _, row in dt_data.iterrows():
        if pd.isna(row["Latitude"]):
            continue
        folium.CircleMarker(
            location=[float(row["Latitude"]), float(row["Longitude"])],
            radius=6,
            color="green",
            fill=True,
            fill_color="green",
            fill_opacity=0.7,
            popup=f"<b>{row['Name']}</b><br>Id: {row['Id']}<br>Snaga: {row['NameplateRating']} kVA",
        ).add_to(dt_group)

    for ts_coords, ss_coords in build_ts_ss_lines(data):
        folium.PolyLine([ts_coords, ss_coords], color="darkblue", weight=2, opacity=0.8).add_to(ts_ss_group)

    for ss_coords, dt_coords in build_ss_dt_lines(data, feeder11_filter, substation_filter):
        folium.PolyLine([ss_coords, dt_coords], color="green", weight=1.5, opacity=0.6).add_to(ss_dt_group)

    for group in (ts_group, ss_group, dt_group, ts_ss_group, ss_dt_group):
        group.add_to(m)
    folium.LayerControl().add_to(m)
    return m
```

- [ ] **Step 4: Pokreni testove da prođu**

```bash
pytest tests/test_map_view.py -v
```

Očekivano: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add vizualizacija/map_view.py tests/test_map_view.py
git commit -m "feat: add folium map with topology layers and filters"
```

---

## Task 5: `app.py` — Streamlit aplikacija

**Files:**
- Create: `vizualizacija/app.py`

- [ ] **Step 1: Napiši `vizualizacija/app.py`**

```python
import streamlit as st
from streamlit_folium import st_folium

from db import load_data
from map_view import create_map
from stats import show_stats

st.set_page_config(
    page_title="Elektrodistributivna Mreža",
    page_icon="⚡",
    layout="wide",
)
st.title("⚡ Elektrodistributivna Mreža — Vizualizacija")

# --- Sidebar ---
with st.sidebar:
    st.header("Kontrolna tabla")
    if st.button("🔄 Refresh Data", use_container_width=True):
        load_data.clear()
        st.rerun()

    data = load_data()
    show_stats(data)

    st.divider()
    st.subheader("Filteri")

    feeder11_options = {"Svi Feeders11": None} | {
        f"{row['Name']} (Id: {row['Id']})": int(row["Id"])
        for _, row in data["feeders11"].iterrows()
    }
    feeder11_filter = feeder11_options[
        st.selectbox("Feeder11", list(feeder11_options.keys()))
    ]

    ss_options = {"Sve Substations": None} | {
        f"{row['Name']} (Id: {row['Id']})": int(row["Id"])
        for _, row in data["substations"].iterrows()
    }
    substation_filter = ss_options[
        st.selectbox("Substation", list(ss_options.keys()))
    ]

# --- Mapa ---
st.subheader("Mapa mreže")
m = create_map(data, feeder11_filter=feeder11_filter, substation_filter=substation_filter)
st_folium(m, use_container_width=True, height=600, returned_objects=[])

# --- Tabele ---
st.subheader("Podaci iz baze")
tab1, tab2, tab3, tab4 = st.tabs(
    ["Transmission Stations", "Substations", "DT Stanice", "Feeders"]
)
with tab1:
    st.dataframe(data["transmission_stations"], use_container_width=True)
with tab2:
    st.dataframe(data["substations"], use_container_width=True)
with tab3:
    st.dataframe(data["distribution_substations"], use_container_width=True)
with tab4:
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Feeders11")
        st.dataframe(data["feeders11"], use_container_width=True)
    with col2:
        st.caption("Feeders33")
        st.dataframe(data["feeders33"], use_container_width=True)
```

- [ ] **Step 2: Pokreni aplikaciju**

```bash
cd vizualizacija
streamlit run app.py
```

Očekivano: browser se otvori na `http://localhost:8501`, mapa se prikazuje, sidebar ima filtere i statistike.

- [ ] **Step 3: Proveri sve slojeve**

U LayerControl (desni ugao mape) uključi/isključi sve 5 slojeva:
- `Transmission Stations` ✓
- `Substations` ✓
- `Distribution Substations (DT)` ✓
- `TS → SS veze` ✓
- `SS → DT veze` ✓

- [ ] **Step 4: Proveri Refresh**

Klikni "Refresh Data" — stranica se ponovo učitava bez gašenja servera.

- [ ] **Step 5: Commit**

```bash
git add vizualizacija/app.py
git commit -m "feat: add streamlit app with sidebar, map, and data tables"
```

---

## Task 6: `CLAUDE.md`

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Napiši `CLAUDE.md`**

```markdown
# SotexHackathon — Elektrodistributivna Mreža

## Pokretanje aplikacije

```bash
pip install -r vizualizacija/requirements.txt
cd vizualizacija
streamlit run app.py
```

Aplikacija se otvara na http://localhost:8501

## Baza podataka

- **Server:** localhost:1433 (SQL Server 2022 u Dockeru)
- **Baza:** SotexHackathon
- **User:** sa

Docker kontejner: `sotex_hackathon_db`

## Struktura projekta

```
vizualizacija/
├── app.py          # Streamlit entry point
├── db.py           # DB konekcija i load_data()
├── map_view.py     # Folium mapa i topologija
├── stats.py        # Sidebar statistike
└── requirements.txt
tests/
├── test_map_view.py
└── test_stats.py
```

## Testovi

```bash
pytest tests/ -v
```

## Dodavanje novih funkcionalnosti

- **Novi sloj na mapi:** dodaj u `map_view.py` → `create_map()`
- **Nova statistika:** dodaj u `stats.py` → `compute_stats()` i `show_stats()`
- **Novi upit iz baze:** dodaj u `db.py` → `load_data()`
- **Nova stranica/tab:** dodaj u `app.py`
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with project overview and dev guide"
```

---

## Task 7: Finalna verifikacija

- [ ] **Step 1: Pokreni sve testove**

```bash
pytest tests/ -v
```

Očekivano: `6 passed`

- [ ] **Step 2: Pokreni aplikaciju i proveri**

```bash
cd vizualizacija && streamlit run app.py
```

Checklist:
- [ ] Mapa se prikazuje centrirana na Srbiju
- [ ] Plavi markeri za TS stanice sa popupom (Name, Id)
- [ ] Narandžasti markeri za Substations sa popupom (Name, Id)
- [ ] Zeleni krugovi za DT stanice sa popupom (Name, Id, NameplateRating)
- [ ] Tamno plave linije TS → SS
- [ ] Zelene linije SS → DT
- [ ] LayerControl uključuje/isključuje sve slojeve
- [ ] Sidebar prikazuje ukupan broj stanica i snagu
- [ ] Filter po Feeder11 filtrira DT stanice i linije
- [ ] Filter po Substation filtrira DT stanice i linije
- [ ] "Refresh Data" radi bez gašenja servera
- [ ] Tabele prikazuju podatke sa search opcijom

- [ ] **Step 3: Finalni commit**

```bash
git add -A
git commit -m "feat: complete streamlit network visualization app"
```
