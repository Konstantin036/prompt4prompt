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

    ts_name_to_id = dict(zip(
        data["transmission_stations"]["Name"],
        data["transmission_stations"]["Id"].astype(int),
    ))
    ts_names = data["transmission_stations"]["Name"].dropna().tolist()
    selected_ts_names = st.multiselect(
        "Transmission Stations (110kV+)",
        options=ts_names,
        default=[],
        placeholder="Prikaži sve...",
    )
    ts_ids = [ts_name_to_id[n] for n in selected_ts_names] or None

    # Kada su TS izabrani, prikaži samo SS koje su vezane za te TS
    if ts_ids:
        f33 = data["feeders33"]
        f33_ss = data["feeder33_substation"]
        linked_f33 = f33[f33["TsId"].isin(ts_ids)]["Id"].tolist()
        linked_ss_ids = f33_ss[f33_ss["Feeders33Id"].isin(linked_f33)]["SubstationsId"].tolist()
        ss_options_df = data["substations"][data["substations"]["Id"].isin(linked_ss_ids)]
    else:
        ss_options_df = data["substations"]

    ss_name_to_id = dict(zip(
        ss_options_df["Name"],
        ss_options_df["Id"].astype(int),
    ))
    ss_names_filtered = ss_options_df["Name"].dropna().tolist()
    selected_ss_names = st.multiselect(
        "Substations (33kV)",
        options=ss_names_filtered,
        default=[],
        placeholder="Prikaži sve..." if not ts_ids else f"Filtrirano ({len(ss_names_filtered)})...",
    )
    ss_ids = [ss_name_to_id[n] for n in selected_ss_names] or None

    st.divider()
    st.subheader("Filteri")

    f11_df = data["feeders11"]
    if ss_ids:
        f11_df = f11_df[f11_df["SsId"].isin(ss_ids)]
    placeholder = f"Filtrirano ({len(f11_df)})..." if ss_ids else "Svi Feeders11"
    feeder11_options = {placeholder: None} | {
        f"{row['Name']} (Id: {row['Id']})": int(row["Id"])
        for _, row in f11_df.iterrows()
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
