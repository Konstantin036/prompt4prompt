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
    st.subheader("Vidljivost slojeva")

    ts_names = data["transmission_stations"]["Name"].dropna().tolist()
    selected_ts_names = st.multiselect(
        "Transmission Stations (110kV+)",
        options=ts_names,
        default=[],
        placeholder="Prikaži sve...",
    )
    ts_name_to_id = dict(zip(
        data["transmission_stations"]["Name"],
        data["transmission_stations"]["Id"].astype(int),
    ))
    ts_ids = [ts_name_to_id[n] for n in selected_ts_names] or None

    ss_names = data["substations"]["Name"].dropna().tolist()
    selected_ss_names = st.multiselect(
        "Substations (33kV)",
        options=ss_names,
        default=[],
        placeholder="Prikaži sve...",
    )
    ss_name_to_id = dict(zip(
        data["substations"]["Name"],
        data["substations"]["Id"].astype(int),
    ))
    ss_ids = [ss_name_to_id[n] for n in selected_ss_names] or None

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
        st.selectbox("Substation (filter DT)", list(ss_options.keys()))
    ]

# --- Mapa ---
st.subheader("Mapa mreže")
m = create_map(
    data,
    feeder11_filter=feeder11_filter,
    substation_filter=substation_filter,
    ts_ids=ts_ids,
    ss_ids=ss_ids,
)
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
