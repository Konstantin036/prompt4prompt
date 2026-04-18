# Consumer Estimation per F11 Feeder — Design Spec

**Goal:** Estimate the number of electricity consumers per F11 feeder using real voltage and current readings from DT meters, with a user-adjustable kVA-per-consumer slider.

**Architecture:** New `consumers.py` module with two SQL queries (DTs with readings, DTs without readings) and a Streamlit section added to `app.py`. Apparent power is computed from latest per-phase V and I readings; consumer count is derived by dividing by the slider value.

**Tech Stack:** Python, pandas, pymssql, Streamlit, Altair (horizontal bar chart)

---

## Data Model

### Tables used

| Table | Columns used | Purpose |
|---|---|---|
| `MeterReads` | `Mid, Val, Ts, Cid` | Latest V and I per meter |
| `Channels` | `Id` = 6,7,8 (V), 9,10,11 (I) | Phase identification |
| `DistributionSubstation` | `Id, Name, MeterId, Feeder11Id, NameplateRating` | DT → meter → feeder mapping |
| `Feeders11` | `Id, Name, SsId` | Feeder name and SS link |
| `Substations` | `Id, Name` | SS name |

### Unit handling

`MeterReads.Val` for current channels (9,10,11) is stored in **milliamps (mA)** despite the channel unit label "A" — confirmed by comparing calculated S against NameplateRating. Voltage channels (6,7,8) are stored in **volts (V)**.

Apparent power per DT:
```
S_phase (VA) = V_phase (V) × I_phase (mA) / 1000
S_total (VA) = S_A + S_B + S_C
S_total (kVA) = S_total (VA) / 1000
```

Consumer estimate per DT:
```
consumers_DT = S_total_kVA / slider_kva_per_consumer
```

Aggregate per F11:
```
consumers_F11 = SUM(consumers_DT) for all DTs on that feeder with readings
```

---

## SQL Queries

### Query 1 — DTs with readings (`load_consumer_estimates`)

Logic:
1. For each meter, find the latest timestamp that has readings for at least one voltage channel (6,7,8).
2. Pivot that latest reading into V_A, V_B, V_C, I_A, I_B, I_C (NULL if a phase is missing).
3. Compute S_total = (V_A×I_A + V_B×I_B + V_C×I_C) / 1,000,000 kVA — skip phases with NULL.
4. Join to DistributionSubstation → Feeders11 → Substations.
5. Return one row per DT with readings on both V and I.

Filter: only DTs where at least one V channel AND at least one I channel has a reading at the latest timestamp.

### Query 2 — DTs without readings (`load_no_reading_dts`)

Return all DistributionSubstations that have a MeterId but NO rows in MeterReads for channels 6–11, plus DTs that have no MeterId at all. Include: DT name, NameplateRating, F11 name, SS name, reason (no meter / no reads).

---

## UI Design (`show_consumers` in `consumers.py`)

```
st.subheader("Estimacija broja potrošača po F11 fiderima")

slider: kVA po potrošaču  [0.5 … 5.0, step 0.1, default 1.5]

metrics row:  F11 fidera  |  DT-a sa merenjima  |  Ukupno est. potrošača

--- Altair horizontal bar chart ---
  Y-axis: F11 feeder name (sorted by consumers desc)
  X-axis: estimated consumers
  Color: Substations (SS) — grouped by color
  Tooltip: F11 name, SS, DT count, S_total kVA, consumers

--- Expander: "Detalji po DT stanicama" ---
  Searchable dataframe with per-DT rows:
  TS | SS | F11 | DT Name | S (kVA) | Est. potrošači | Pokrivenost faze

--- st.divider ---

st.warning("Stanice bez merenja — potrebno izvršiti pregled na terenu")
Dataframe: DT Name | SS | F11 | NameplateRating | Razlog
```

The slider recomputes consumers in Python (no re-query) — `load_consumer_estimates` is cached and returns raw S_kVA per DT; the slider just divides at display time.

---

## File Changes

| File | Change |
|---|---|
| `vizualizacija/consumers.py` | New file: `load_consumer_estimates()`, `load_no_reading_dts()`, `show_consumers()` |
| `vizualizacija/app.py` | Add `from consumers import show_consumers` and call `show_consumers()` after `show_losses()` |

---

## Testing

No unit tests for SQL queries (requires live DB). Manual verification:
- Pick one DT with known NameplateRating, compare S_kVA to rated capacity — should be ≤ 100% load.
- Confirm "no readings" table contains DTs with MeterId but no MeterReads rows.
- Confirm slider changes consumer counts without re-querying DB.
