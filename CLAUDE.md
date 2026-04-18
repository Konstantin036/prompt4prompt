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

Kredencijali se čitaju iz environment varijabli (sa fallback vrednostima za lokalni razvoj):
- `DB_SERVER` (default: localhost)
- `DB_PORT` (default: 1433)
- `DB_NAME` (default: SotexHackathon)
- `DB_USER` (default: sa)
- `DB_PASSWORD`

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
