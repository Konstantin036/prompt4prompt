import folium
import pandas as pd


def get_map_center(data: dict) -> list:
    lats, lons = [], []
    for key in ("transmission_stations", "substations", "distribution_substations"):
        df = data[key]
        lats.extend(df["Latitude"].dropna().tolist())
        lons.extend(df["Longitude"].dropna().tolist())
    if not lats:
        return [44.0, 21.0]
    return [sum(lats) / len(lats), sum(lons) / len(lons)]


def build_ts_ss_lines(data: dict) -> list:
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
