# Feeder Load Analysis — Design Spec

**Goal:** Calculate and display instantaneous load factor (% utilization) for all F11 and F33 feeders by comparing measured apparent power (from V×I readings) against nominal transformer capacity (NameplateRating).

**Architecture:** New `vizualizacija/load.py` module with two cached SQL queries (F11 load, F33 load), one pure aggregation helper, and a `show_load()` Streamlit function. `app.py` gets one import and one call added after `show_consumers()`.

**Tech Stack:** Python, pandas, pymssql, Streamlit, plotly

---

## Load Factor Formula

```
S_measured_kVA  = SUM(V_A×I_A + V_B×I_B + V_C×I_C) / 1_000_000  for DTs with readings
S_nominal_kVA   = SUM(NameplateRating)                             for ALL DTs on feeder
load_factor_%   = S_measured_kVA / S_nominal_kVA × 100
```

Current values only (mA units for current, same as consumers.py). DTs without V×I readings contribute 0 to measured but full NameplateRating to nominal — this conservatively under-estimates load factor where coverage is partial.

---

## Load Zones (Industrial Standard)

| Zone | Threshold | Color | Meaning |
|---|---|---|---|
| Normalno | < 70% | Green `#2d6a2d` | Healthy utilization |
| Upozorenje | 70–85% | Yellow `#997700` | Approaching capacity |
| Kritično | > 85% | Red `#8b0000` | Overloaded or near limit |

---

## SQL Queries

### `load_f11()` — F11 feeder load

CTEs:
1. `latest_ts` — latest timestamp per meter in MeterReads (Cid 6-11)
2. `pivoted` — pivot to V_A/B/C, I_A/B/C at that timestamp
3. `s_dt` — S_kVA per DT (same formula as consumers.py)
4. Final SELECT: join DT → Feeders11 → Substations, group by F11, compute:
   - `S_measured_kVA = SUM(s_dt.S_kVA)` — only DTs with readings
   - `S_nominal_kVA = SUM(d.NameplateRating) / 1000.0` — all DTs on feeder
   - `load_pct = S_measured / S_nominal * 100`
   - `dt_with_reads / dt_total` — coverage
   - TS via correlated subquery (same pattern as losses.py and consumers.py)

Filter: only F11 feeders where at least one DT has a reading AND S_nominal > 0.

### `load_f33()` — F33 feeder load

CTEs:
1–3. Same `latest_ts`, `pivoted`, `s_dt` as above
4. `f11_load` — group s_dt by Feeder11Id, sum S_measured and S_nominal (NameplateRating of all DTs)
5. Final SELECT: join through DistributionSubstation → Feeders11 → Feeder33Substation → Feeders33, group by F33:
   - `S_measured_kVA = SUM(f11_load.S_measured)`
   - `S_nominal_kVA = SUM(f11_load.S_nominal)`
   - `load_pct = S_measured / S_nominal * 100`
   - TS via TransmissionStations join

Filter: only F33 feeders where S_nominal > 0 and at least one DT reading exists.

---

## No-Readings Tables

**F11 without readings:** F11 feeders where ALL DTs have no MeterId or no V/I MeterReads. Columns: TS, SS, Feeder11, DT ukupno, Nominalni kapacitet (kVA).

**F33 without readings:** F33 feeders where no connected DT has readings. Columns: TS, Feeder33, SS lista, DT ukupno, Nominalni kapacitet (kVA).

---

## UI Layout (`show_load()`)

```
st.subheader("Opterećenje F11 fidera")

[metrics: F11 fidera | Kritično opterećenih | Prosečno opterećenje %]

[Plotly horizontal bar chart]
  Y: Feeder11 name (sorted ascending by load%)
  X: load_pct
  Color: discrete zone (Normalno / Upozorenje / Kritično)
  color_discrete_map: green/yellow/red
  Tooltip: SS, S_measured, S_nominal, DT coverage

[Color-coded dataframe]
  Columns: TS | SS | Feeder11 | S mereno (kVA) | S nominalno (kVA) | Opterećenje (%) | DT merila | DT ukupno | Pokr. (%)
  Row highlight on Opterećenje (%) column: green/yellow/red

[Expander: "F11 fideri bez merenja (N)"]
  Dataframe with no-reading F11s

st.divider()

st.subheader("Opterećenje F33 fidera")
[same structure: metrics → chart → table → expander]
```

---

## File Changes

| File | Action |
|---|---|
| `vizualizacija/load.py` | Create — queries, `_color_load`, `show_load()` |
| `vizualizacija/app.py` | Modify — import + call `show_load()` after `show_consumers()` |

---

## Testing

Pure helper `_color_load(pct)` → returns zone string ("Normalno" / "Upozorenje" / "Kritično") — unit testable without DB.

Test file: `tests/test_load.py`
- `test_color_load_normal()` — pct=50 → "Normalno"
- `test_color_load_warning()` — pct=75 → "Upozorenje"
- `test_color_load_critical()` — pct=90 → "Kritično"
- `test_color_load_boundaries()` — pct=70 → "Upozorenje", pct=85 → "Kritično"
