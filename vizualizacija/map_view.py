import folium
import pandas as pd

# Paleta boja za DT stanice — svaki SS dobija svoju boju
_SS_PALETTE = [
    "#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00",
    "#a65628", "#f781bf", "#66c2a5", "#fc8d62", "#8da0cb",
    "#e78ac3", "#a6d854", "#ffd92f", "#e5c494", "#b3b3b3",
]


def _build_ss_color_map(data: dict) -> dict:
    ss_ids = data["substations"]["Id"].tolist()
    return {int(ss_id): _SS_PALETTE[i % len(_SS_PALETTE)] for i, ss_id in enumerate(ss_ids)}


def _valid_coords(lat, lon) -> bool:
    if pd.isna(lat) or pd.isna(lon):
        return False
    # Odbaci koordinate bliske (0, 0) — "null island" u Atlantiku
    if abs(float(lat)) < 0.5 and abs(float(lon)) < 0.5:
        return False
    return True


def get_map_center(data: dict) -> list:
    lats, lons = [], []
    for key in ("transmission_stations", "substations", "distribution_substations"):
        df = data[key]
        for _, row in df.iterrows():
            if _valid_coords(row.get("Latitude"), row.get("Longitude")):
                lats.append(float(row["Latitude"]))
                lons.append(float(row["Longitude"]))
    if not lats:
        return [44.0, 21.0]
    return [sum(lats) / len(lats), sum(lons) / len(lons)]


def build_ts_ss_lines(data: dict, ss_id_filter=None) -> list:
    ts = data["transmission_stations"].set_index("Id")
    ss = data["substations"].set_index("Id")
    f33 = data["feeders33"].set_index("Id")
    lines = []
    for _, row in data["feeder33_substation"].iterrows():
        f33_id = row["Feeders33Id"]
        ss_id = row["SubstationsId"]
        if ss_id_filter is not None and int(ss_id) != ss_id_filter:
            continue
        if f33_id not in f33.index or ss_id not in ss.index:
            continue
        ts_id = f33.loc[f33_id, "TsId"]
        if pd.isna(ts_id) or int(ts_id) not in ts.index:
            continue
        ts_row = ts.loc[int(ts_id)]
        ss_row = ss.loc[ss_id]
        if not _valid_coords(ts_row["Latitude"], ts_row["Longitude"]):
            continue
        if not _valid_coords(ss_row["Latitude"], ss_row["Longitude"]):
            continue
        lines.append(
            ([float(ts_row["Latitude"]), float(ts_row["Longitude"])],
             [float(ss_row["Latitude"]), float(ss_row["Longitude"])])
        )
    return lines


def build_ts_ss_chains(data: dict, ss_id_filter=None, ts_ids=None, ss_ids=None) -> list:
    """
    Returns list of (chain, ts_id) where chain is [ts_coords, ss1, ss2, ...]
    ordered by nearest-neighbor from the TS outward.
    Only includes SS that are currently visible (ss_ids filter).
    """
    ts = data["transmission_stations"].set_index("Id")
    ss = data["substations"].set_index("Id")
    f33 = data["feeders33"].set_index("Id")

    # Grupiši SS po TS-u
    ts_to_ss: dict[int, list] = {}
    for _, row in data["feeder33_substation"].iterrows():
        f33_id = row["Feeders33Id"]
        ss_id = row["SubstationsId"]
        if ss_id_filter is not None and int(ss_id) != ss_id_filter:
            continue
        # Preskoči SS koji nisu vidljivi
        if ss_ids and int(ss_id) not in ss_ids:
            continue
        if f33_id not in f33.index or ss_id not in ss.index:
            continue
        ts_id = f33.loc[f33_id, "TsId"]
        if pd.isna(ts_id) or int(ts_id) not in ts.index:
            continue
        if ts_ids and int(ts_id) not in ts_ids:
            continue
        ss_row = ss.loc[ss_id]
        if not _valid_coords(ss_row["Latitude"], ss_row["Longitude"]):
            continue
        ts_id_int = int(ts_id)
        ts_to_ss.setdefault(ts_id_int, []).append(
            [float(ss_row["Latitude"]), float(ss_row["Longitude"])]
        )

    chains = []
    for ts_id_int, ss_points in ts_to_ss.items():
        ts_row = ts.loc[ts_id_int]
        if not _valid_coords(ts_row["Latitude"], ts_row["Longitude"]):
            continue
        ts_point = [float(ts_row["Latitude"]), float(ts_row["Longitude"])]
        ordered = _nearest_neighbor_chain(ts_point, ss_points)
        chains.append(([ts_point] + ordered, ts_id_int))

    return chains


def _nearest_neighbor_chain(start: list, points: list) -> list:
    """Greedy nearest-neighbor path starting from start through all points."""
    remaining = [list(p) for p in points]
    ordered = []
    current = start
    while remaining:
        idx = min(range(len(remaining)),
                  key=lambda i: (remaining[i][0] - current[0])**2 + (remaining[i][1] - current[1])**2)
        nearest = remaining.pop(idx)
        ordered.append(nearest)
        current = nearest
    return ordered


def build_ss_dt_chains(data: dict, feeder11_filter=None, substation_filter=None,
                       ss_ids=None) -> list:
    """
    Returns list of (chain, ss_id) where chain is [ss_coords, dt1, dt2, ...]
    ordered by nearest-neighbor from the SS outward.
    """
    ss = data["substations"].set_index("Id")
    f11 = data["feeders11"].set_index("Id")
    dt = data["distribution_substations"].copy()

    if feeder11_filter is not None:
        dt = dt[dt["Feeder11Id"] == feeder11_filter]
    if substation_filter is not None:
        valid_ids = f11[f11["SsId"] == substation_filter].index.tolist()
        dt = dt[dt["Feeder11Id"].isin(valid_ids)]
    if ss_ids:
        visible_f11_ids = f11[f11["SsId"].isin(ss_ids)].index.tolist()
        dt = dt[dt["Feeder11Id"].isin(visible_f11_ids)]

    # Grupiši DT po Feeder11 — svaki fider dobija svoj lanac
    f11_to_dts: dict[int, list] = {}
    f11_to_ss: dict[int, int] = {}
    for _, dt_row in dt.iterrows():
        f11_id = dt_row["Feeder11Id"]
        if pd.isna(f11_id) or int(f11_id) not in f11.index:
            continue
        ss_id = f11.loc[int(f11_id), "SsId"]
        if pd.isna(ss_id) or int(ss_id) not in ss.index:
            continue
        if not _valid_coords(dt_row["Latitude"], dt_row["Longitude"]):
            continue
        f11_id_int = int(f11_id)
        f11_to_dts.setdefault(f11_id_int, []).append(
            [float(dt_row["Latitude"]), float(dt_row["Longitude"])]
        )
        f11_to_ss[f11_id_int] = int(ss_id)

    chains = []
    for f11_id_int, dt_points in f11_to_dts.items():
        ss_id_int = f11_to_ss[f11_id_int]
        ss_row = ss.loc[ss_id_int]
        if not _valid_coords(ss_row["Latitude"], ss_row["Longitude"]):
            continue
        ss_point = [float(ss_row["Latitude"]), float(ss_row["Longitude"])]
        ordered = _nearest_neighbor_chain(ss_point, dt_points)
        chains.append(([ss_point] + ordered, ss_id_int))

    return chains


def build_ss_dt_lines(data: dict, feeder11_filter=None, substation_filter=None) -> list:
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
        if not _valid_coords(dt_row["Latitude"], dt_row["Longitude"]):
            continue
        if not _valid_coords(ss_row["Latitude"], ss_row["Longitude"]):
            continue
        lines.append(
            ([float(ss_row["Latitude"]), float(ss_row["Longitude"])],
             [float(dt_row["Latitude"]), float(dt_row["Longitude"])])
        )
    return lines


def _get_ss_id_for_feeder11(data: dict, feeder11_id: int):
    f11 = data["feeders11"].set_index("Id")
    if feeder11_id not in f11.index:
        return None
    ss_id = f11.loc[feeder11_id, "SsId"]
    return int(ss_id) if not pd.isna(ss_id) else None


def create_map(data: dict, feeder11_filter=None, substation_filter=None,
               ts_ids=None, ss_ids=None) -> folium.Map:
    center = get_map_center(data)
    m = folium.Map(location=center, zoom_start=10)

    ts_group = folium.FeatureGroup(name="Transmission Stations", show=True)
    ss_group = folium.FeatureGroup(name="Substations", show=True)
    dt_group = folium.FeatureGroup(name="Distribution Substations (DT)", show=True)
    dt_no_conn_group = folium.FeatureGroup(name="DT bez veze (nisu u topologiji)", show=False)
    ts_ss_group = folium.FeatureGroup(name="TS → SS veze", show=True)
    ss_dt_group = folium.FeatureGroup(name="SS → DT veze", show=True)

    ts_data = data["transmission_stations"]
    if ts_ids:
        ts_data = ts_data[ts_data["Id"].isin(ts_ids)]
    for _, row in ts_data.iterrows():
        if not _valid_coords(row["Latitude"], row["Longitude"]):
            continue
        folium.Marker(
            location=[float(row["Latitude"]), float(row["Longitude"])],
            popup=f"<b>{row['Name']}</b><br>Id: {row['Id']}",
            icon=folium.Icon(color="blue", icon="bolt", prefix="fa"),
        ).add_to(ts_group)

    ss_color_map = _build_ss_color_map(data)
    ss_data = data["substations"]
    if ss_ids:
        ss_data = ss_data[ss_data["Id"].isin(ss_ids)]
    for _, row in ss_data.iterrows():
        if not _valid_coords(row["Latitude"], row["Longitude"]):
            continue
        ss_color = ss_color_map.get(int(row["Id"]), "#ff7800")
        folium.Marker(
            location=[float(row["Latitude"]), float(row["Longitude"])],
            popup=f"<b>{row['Name']}</b><br>Id: {row['Id']}",
            icon=folium.Icon(color="orange", icon="plug", prefix="fa"),
            tooltip=row["Name"],
        ).add_to(ss_group)

    f11 = data["feeders11"].set_index("Id")
    dt_data = data["distribution_substations"].copy()
    if feeder11_filter is not None:
        dt_data = dt_data[dt_data["Feeder11Id"] == feeder11_filter]
    if substation_filter is not None:
        valid_ids = f11[f11["SsId"] == substation_filter].index.tolist()
        dt_data = dt_data[dt_data["Feeder11Id"].isin(valid_ids)]
    # Ako je SS vidljivost filtrirana, prikaži samo DT koji pripadaju vidljivim SS
    if ss_ids:
        visible_f11_ids = f11[f11["SsId"].isin(ss_ids)].index.tolist()
        dt_data = dt_data[dt_data["Feeder11Id"].isin(visible_f11_ids)]

    connected_f11_ids = set(f11.index)
    for _, row in dt_data.iterrows():
        if not _valid_coords(row["Latitude"], row["Longitude"]):
            continue
        f11_id = row["Feeder11Id"]
        is_connected = (not pd.isna(f11_id)) and (int(f11_id) in connected_f11_ids)
        if is_connected:
            ss_id_raw = f11.loc[int(f11_id), "SsId"]
            dt_color = ss_color_map.get(int(ss_id_raw), "#4daf4a") if not pd.isna(ss_id_raw) else "gray"
        else:
            dt_color = "gray"
        marker = folium.CircleMarker(
            location=[float(row["Latitude"]), float(row["Longitude"])],
            radius=6,
            color=dt_color,
            fill=True,
            fill_color=dt_color,
            fill_opacity=0.7,
            popup=f"<b>{row['Name']}</b><br>Id: {row['Id']}<br>Snaga: {row['NameplateRating']} kVA"
                  + ("" if is_connected else "<br><i>Nema Feeder11 veze</i>"),
        )
        marker.add_to(dt_group if is_connected else dt_no_conn_group)

    # Filtriraj TS→SS linije na relevantan SS kada je feeder11 ili substation izabran
    ss_id_for_ts_filter = None
    if feeder11_filter is not None:
        ss_id_for_ts_filter = _get_ss_id_for_feeder11(data, feeder11_filter)
    elif substation_filter is not None:
        ss_id_for_ts_filter = substation_filter

    for chain, _ in build_ts_ss_chains(data, ss_id_filter=ss_id_for_ts_filter, ts_ids=ts_ids, ss_ids=ss_ids):
        folium.PolyLine(chain, color="darkblue", weight=2, opacity=0.8).add_to(ts_ss_group)

    for chain, chain_ss_id in build_ss_dt_chains(data, feeder11_filter, substation_filter, ss_ids):
        color = ss_color_map.get(chain_ss_id, "#4daf4a")
        folium.PolyLine(chain, color=color, weight=1.5, opacity=0.7).add_to(ss_dt_group)

    for group in (ts_group, ss_group, dt_group, dt_no_conn_group, ts_ss_group, ss_dt_group):
        group.add_to(m)
    folium.LayerControl().add_to(m)
    return m
