import streamlit as st
from streamlit_folium import st_folium

from db import load_data
from losses import show_losses
from consumers import show_consumers
from load import show_load
from map_view import create_map
from stats import show_stats
from outages import show_outages

st.set_page_config(
    page_title="Grid Analytics — EPS",
    page_icon="⚡",
    layout="wide",
)

# ── CSS Theme ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* === METRIC CARDS === */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, rgba(30,42,69,0.95) 0%, rgba(22,33,62,0.95) 100%);
    border: 1px solid rgba(255,107,53,0.28);
    border-radius: 16px;
    padding: 1.2rem 1.4rem !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,107,53,0.07);
    transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    position: relative;
    overflow: hidden;
}
[data-testid="metric-container"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 4px; height: 100%;
    background: linear-gradient(180deg, #FF6B35, #ffb347);
}
[data-testid="metric-container"]:hover {
    border-color: rgba(255,107,53,0.7);
    box-shadow: 0 8px 35px rgba(255,107,53,0.25), 0 0 0 1px rgba(255,107,53,0.2);
    transform: translateY(-3px);
}
[data-testid="stMetricValue"] {
    color: #FF6B35 !important;
    font-size: 2.1rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
}
[data-testid="stMetricLabel"] {
    color: #8892b0 !important;
    font-size: 0.70rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.12em !important;
    font-weight: 600 !important;
}

/* === TABS === */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(22,27,34,0.85);
    border-radius: 14px;
    padding: 5px;
    gap: 3px;
    border: 1px solid rgba(48,54,61,0.6);
}
.stTabs [data-baseweb="tab"] {
    color: #8b949e !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    padding: 9px 22px !important;
    transition: all 0.25s ease !important;
    border: none !important;
}
.stTabs [data-baseweb="tab"]:hover {
    background: rgba(255,107,53,0.12) !important;
    color: #FF6B35 !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #FF6B35 0%, #ff8c42 100%) !important;
    color: white !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 16px rgba(255,107,53,0.45) !important;
}
.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}

/* === SIDEBAR === */
[data-testid="stSidebar"] {
    border-right: 2px solid rgba(255,107,53,0.4);
}

/* === DIVIDER === */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent 0%, #FF6B35 30%, #FF6B35 70%, transparent 100%) !important;
    opacity: 0.3 !important;
    margin: 2rem 0 !important;
}

/* === BUTTONS === */
.stButton > button {
    background: linear-gradient(135deg, #FF6B35 0%, #ff8c42 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em !important;
    box-shadow: 0 4px 15px rgba(255,107,53,0.35) !important;
    transition: all 0.3s ease !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(255,107,53,0.55) !important;
}

/* === EXPANDER === */
.streamlit-expanderHeader {
    border-radius: 10px !important;
    color: #FF6B35 !important;
    font-weight: 600 !important;
}

/* === SCROLLBAR === */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #FF6B35; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #ff8c42; }

/* === MULTISELECT TAGS === */
.stMultiSelect [data-baseweb="tag"] {
    background: rgba(255,107,53,0.2) !important;
    border-color: rgba(255,107,53,0.45) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<p style="color:#FF6B35;font-size:0.75rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.15em;margin-bottom:0.5rem;">'
        '⚡ Kontrolna tabla</p>',
        unsafe_allow_html=True,
    )

    data = load_data()

    st.markdown(
        '<p style="color:#FF6B35;font-size:0.75rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.12em;'
        'text-align:center;margin:0 0 0.75rem 0;">🗺️ Slojevi mape</p>',
        unsafe_allow_html=True,
    )

    ts_name_to_id = dict(zip(
        data["transmission_stations"]["Name"],
        data["transmission_stations"]["Id"].astype(int),
    ))
    ts_names = data["transmission_stations"]["Name"].dropna().tolist()
    selected_ts_names = st.multiselect(
        "Prenosne stanice",
        options=ts_names,
        default=[],
        placeholder="Prikaži sve...",
    )
    ts_ids = [ts_name_to_id[n] for n in selected_ts_names] or None

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
        "Podstanice",
        options=ss_names_filtered,
        default=[],
        placeholder="Prikaži sve..." if not ts_ids else f"Filtrirano ({len(ss_names_filtered)})...",
    )
    ss_ids = [ss_name_to_id[n] for n in selected_ss_names] or None

    st.divider()
    st.markdown(
        '<p style="color:#FF6B35;font-size:0.75rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.12em;'
        'text-align:center;margin:0 0 0.75rem 0;">🔍 Filteri</p>',
        unsafe_allow_html=True,
    )

    f11_with_dt = set(data["distribution_substations"]["Feeder11Id"].dropna().astype(int))
    f11_df = data["feeders11"][data["feeders11"]["Id"].isin(f11_with_dt)]
    if ss_ids:
        f11_df = f11_df[f11_df["SsId"].isin(ss_ids)]
    placeholder = f"Filtrirano ({len(f11_df)})..." if ss_ids else "Svi Feederi"
    feeder11_options = {placeholder: None} | {
        f"{row['Name']} (Id: {row['Id']})": int(row["Id"])
        for _, row in f11_df.iterrows()
    }
    feeder11_filter = feeder11_options[
        st.selectbox("Feederi", list(feeder11_options.keys()))
    ]

    st.divider()
    show_stats(data, ts_ids=ts_ids, ss_ids=ss_ids, feeder11_filter=feeder11_filter)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid rgba(255,107,53,0.2);">
    <div style="
        background: linear-gradient(135deg, #FF6B35 0%, #ff8c42 50%, #ffb347 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.6rem;
        font-weight: 900;
        letter-spacing: -0.04em;
        line-height: 1.1;
        margin: 0;
    ">⚡ Grid Analytics</div>
    <div style="color:#8892b0;font-size:0.88rem;margin-top:6px;
                text-transform:uppercase;letter-spacing:0.1em;font-weight:500;">
        Elektrodistributivna mreža &nbsp;·&nbsp; Vizualizacija u realnom vremenu
    </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_map, tab_losses, tab_consumers, tab_load, tab_outages, tab_data = st.tabs([
    "🗺️  Mapa mreže",
    "📉  Gubici",
    "👥  Potrošači",
    "⚡  Opterećenje",
    "🔴  Nestanci",
    "🗄️  Podaci",
])

with tab_map:
    expand_map = st.toggle("Proširi mapu", value=False)
    map_height = 950 if expand_map else 650
    m = create_map(
        data,
        feeder11_filter=feeder11_filter,
        substation_filter=None,
        ts_ids=ts_ids,
        ss_ids=ss_ids,
    )
    st_folium(m, use_container_width=True, height=map_height, returned_objects=[])

with tab_losses:
    show_losses()

with tab_consumers:
    show_consumers()

with tab_load:
    show_load()

with tab_outages:
    show_outages()

with tab_data:
    st.markdown(
        '<p style="color:#8892b0;font-size:0.8rem;text-transform:uppercase;'
        'letter-spacing:0.1em;">Sirovi podaci iz baze</p>',
        unsafe_allow_html=True,
    )
    dt1, dt2, dt3, dt4 = st.tabs(
        ["Transmission Stations", "Substations", "DT Stanice", "Feeders"]
    )
    with dt1:
        st.dataframe(data["transmission_stations"], use_container_width=True)
    with dt2:
        st.dataframe(data["substations"], use_container_width=True)
    with dt3:
        st.dataframe(data["distribution_substations"], use_container_width=True)
    with dt4:
        col1, col2 = st.columns(2)
        with col1:
            st.caption("Feeders11")
            st.dataframe(data["feeders11"], use_container_width=True)
        with col2:
            st.caption("Feeders33")
            st.dataframe(data["feeders33"], use_container_width=True)
