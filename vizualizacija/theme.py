import plotly.graph_objects as go

ORANGE = "#FF6B35"

ZONE_COLORS_CHART = {
    "Normalno":   "#1db954",
    "Upozorenje": "#FF8C00",
    "Kritično":   "#e53e3e",
}

ZONE_COLORS_TABLE = {
    "Normalno":   "#0a3d1a",
    "Upozorenje": "#3d2200",
    "Kritično":   "#3d0a0a",
}


def apply_dark_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(22, 33, 62, 0.25)",
        font=dict(color="#a0aec0", size=11),
        title_font=dict(color=ORANGE, size=14),
        legend=dict(
            bgcolor="rgba(22,27,34,0.85)",
            bordercolor="rgba(255,107,53,0.3)",
            borderwidth=1,
            font=dict(color="#a0aec0"),
        ),
        xaxis=dict(
            gridcolor="rgba(255,107,53,0.07)",
            linecolor="rgba(255,107,53,0.15)",
            tickfont=dict(color="#a0aec0"),
            title_font=dict(color="#8892b0"),
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor="rgba(255,107,53,0.07)",
            linecolor="rgba(255,107,53,0.15)",
            tickfont=dict(color="#a0aec0"),
            title_font=dict(color="#8892b0"),
            zeroline=False,
        ),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig
