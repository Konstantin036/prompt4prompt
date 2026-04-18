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
