import streamlit as st


def compute_stats(data: dict, ts_ids=None, ss_ids=None, feeder11_filter=None) -> dict:
    f11 = data["feeders11"].set_index("Id")
    dt = data["distribution_substations"]

    if ss_ids:
        visible_ss_ids = ss_ids
    elif ts_ids:
        f33 = data["feeders33"]
        f33_ss = data["feeder33_substation"]
        linked_f33 = f33[f33["TsId"].isin(ts_ids)]["Id"].tolist()
        linked_ss = f33_ss[f33_ss["Feeders33Id"].isin(linked_f33)]["SubstationsId"].tolist()
        visible_ss_ids = [int(x) for x in linked_ss]
    else:
        visible_ss_ids = None

    if ss_ids:
        ss_count = len(ss_ids)
    elif ts_ids:
        ss_count = len(visible_ss_ids)
    else:
        ss_count = len(data["substations"])

    if feeder11_filter is not None:
        dt = dt[dt["Feeder11Id"] == feeder11_filter]
    elif visible_ss_ids:
        visible_f11_ids = f11[f11["SsId"].isin(visible_ss_ids)].index.tolist()
        dt = dt[dt["Feeder11Id"].isin(visible_f11_ids)]

    return {
        "ts_count": len(ts_ids) if ts_ids else len(data["transmission_stations"]),
        "ss_count": ss_count,
        "dt_count": len(dt),
        "total_power": int(dt["NameplateRating"].sum(skipna=True)),
    }


def show_stats(data: dict, ts_ids=None, ss_ids=None, feeder11_filter=None) -> None:
    s = compute_stats(data, ts_ids=ts_ids, ss_ids=ss_ids, feeder11_filter=feeder11_filter)
    st.sidebar.markdown(
        '<p style="color:#FF6B35;font-size:1.0rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:0.12em;'
        'text-align:center;margin:0.5rem 0 0.75rem 0;">📊 Statistike mreže</p>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.sidebar.columns(2)
    col1.metric("TS Stanice", s["ts_count"])
    col2.metric("Substations", s["ss_count"])
    col1.metric("DT Stanice", s["dt_count"])
    col2.metric("Snaga (kVA)", f"{s['total_power']:,}")
