# Streamlit Vizualizacija Elektrodistributivne Mreže — Design

**Datum:** 2026-04-18  
**Status:** Odobren

---

## Pregled

Streamlit web aplikacija za interaktivnu vizualizaciju i analizu elektrodistributivne mreže iz Microsoft SQL Server baze podataka (Docker, `localhost:1433`, baza `SotexHackathon`).

---

## Tehnički stack

| Komponenta | Tehnologija |
|---|---|
| UI framework | Streamlit |
| Mapa | Folium + streamlit-folium |
| DB konekcija | pymssql |
| Baza | MSSQL Server 2022 (Docker, `localhost:1433`) |
| Baza ime | `SotexHackathon` |
| Kredencijali | `sa` / `SotexSolutions123!` |

---

## Struktura fajlova

```
vizualizacija/
├── app.py           # Streamlit entry point
├── db.py            # Konekcija i load_data()
├── map_view.py      # create_map()
├── stats.py         # show_stats()
└── requirements.txt
```

Pokretanje: `streamlit run vizualizacija/app.py`

---

## Baza podataka — tabele i relacije

### Tabele
- **TransmissionStations**: Id, Name, Latitude, Longitude (visoki napon)
- **Substations**: Id, Name, Latitude, Longitude (srednji napon)
- **DistributionSubstation**: Id, Name, Feeder11Id, NameplateRating, Latitude, Longitude (niskonaponske — "Dt")
- **Feeders11**: Id, Name, SsId (→Substations.Id), TsId (→TransmissionStations.Id)
- **Feeders33**: Id, Name, TsId (→TransmissionStations.Id)
- **Feeder33Substation**: Feeders33Id, SubstationsId (junction tabela)

### Topologija veza (linije na mapi)
- **TS → SS:** `TransmissionStations` → `Feeders33` (via `Feeders33.TsId`) → `Feeder33Substation` → `Substations`
- **SS → DT:** `Substations` → `Feeders11` (via `Feeders11.SsId`) → `DistributionSubstation` (via `Feeder11Id`)

---

## Komponente

### `db.py` — Podaci

```python
@st.cache_data
def load_data() -> dict[str, pd.DataFrame]:
    # Vraća sve tabele kao pandas DataFrames
    return {
        "transmission_stations": ...,
        "substations": ...,
        "distribution_substations": ...,
        "feeders11": ...,
        "feeders33": ...,
        "feeder33_substation": ...,
    }
```

- `get_connection()` — pymssql konekcija na localhost:1433
- "Refresh Data" dugme poziva `st.cache_data.clear()` i rerun

### `map_view.py` — Mapa

`create_map(data, feeder_filter=None, substation_filter=None) -> folium.Map`

**Slojevi (LayerControl — svi uključeni po defaultu):**
1. `Transmission Stations` — plavi `folium.Marker` (icon="bolt")
2. `Substations` — narandžasti `folium.Marker`
3. `Distribution Substations (DT)` — zeleni `folium.CircleMarker` (radius=6)
4. `TS → SS veze` — tamno plave `folium.PolyLine`
5. `SS → DT veze` — svetlo zelene `folium.PolyLine`

**Popup sadržaj:**
- TS/SS: Name, Id
- DT: Name, Id, NameplateRating

**Centar mape:** prosek svih lat/lon vrednosti iz svih stanica.

**Filtriranje:** Ako je izabran feeder ili substation, mapa prikazuje samo relevantne DT stanice i veze.

### `stats.py` — Statistike

`show_stats(data)` — prikazuje u sidebaru:
- Ukupan broj TransmissionStations
- Ukupan broj Substations
- Ukupan broj Distribution Substations (DT)
- Ukupna snaga mreže (suma NameplateRating iz DistributionSubstation)

### `app.py` — Glavni fajl

**Sidebar:**
- "Refresh Data" dugme
- Dropdown: "Filter po Feederu" (Feeder11 ili Feeder33)
- Dropdown: "Filter po Substation"
- `show_stats(data)` blok

**Glavni panel:**
1. `st_folium(create_map(...), width="100%", height=600)`
2. Ispod mape: `st.tabs(["TS", "SS", "DT", "Feeders"])` sa `st.dataframe` + search po kolonama

---

## Zavisnosti (`requirements.txt`)

```
streamlit
streamlit-folium
folium
pymssql
pandas
```

---

## Šta nije u scopeu

- Autentikacija korisnika
- Editovanje podataka u bazi
- Real-time osvežavanje (samo na pritisak dugmeta)
- Istorijski podaci (MeterReads tabele)
