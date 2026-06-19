"""
visualization/chart.py
Interactive HTML chart built with Plotly.

Layout (4 rows, shared x-axis)
───────────────────────────────
Row 1  Candlestick + EMA lines + Swing pivots + OB zones + FVG zones
       + BOS markers + Buy / Sell signals
Row 2  RSI with overbought / oversold bands
Row 3  Signal-strength bar chart
Row 4  Equity curve (when backtest data is provided)

Output
──────
chart.html   — saved to working directory and auto-opened in the browser.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import EMA_SHORT, EMA_LONG, EMA_TREND, RSI_OVERBOUGHT, RSI_OVERSOLD

# Maximum number of OB / FVG rectangles to draw (keeps rendering fast)
_MAX_SHAPES = 50


def plot_chart(
    df: pd.DataFrame,
    trades_df: pd.DataFrame | None = None,
    equity_curve: list | None = None,
    output_file: str = "chart.html",
) -> go.Figure:

    row_heights = [0.50, 0.15, 0.15, 0.20]
    subplot_titles = ["Price + Indicators", "RSI", "Signal Strength", "Equity Curve"]

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
    )

    # ── Row 1 : Candlestick ───────────────────────────────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"], high=df["high"],
            low=df["low"],   close=df["close"],
            name="Price",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1, col=1,
    )

    # ── EMA lines ─────────────────────────────────────────────────────────────
    ema_cfg = [
        (f"EMA_{EMA_SHORT}", f"EMA {EMA_SHORT}", "#FFD700", 1.5),
        (f"EMA_{EMA_LONG}",  f"EMA {EMA_LONG}",  "#FF69B4", 1.5),
        (f"EMA_{EMA_TREND}", f"EMA {EMA_TREND}", "#00BFFF", 2.0),
    ]
    for col_name, label, colour, width in ema_cfg:
        fig.add_trace(
            go.Scatter(x=df.index, y=df[col_name], name=label,
                       line=dict(color=colour, width=width)),
            row=1, col=1,
        )

    # ── Swing pivots ──────────────────────────────────────────────────────────
    sh = df[df["swing_high"]]
    sl = df[df["swing_low"]]
    fig.add_trace(
        go.Scatter(x=sh.index, y=sh["high"], mode="markers", name="Swing High",
                   marker=dict(symbol="triangle-down", size=9, color="#ef5350")),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=sl.index, y=sl["low"], mode="markers", name="Swing Low",
                   marker=dict(symbol="triangle-up", size=9, color="#26a69a")),
        row=1, col=1,
    )

    # ── BOS markers ───────────────────────────────────────────────────────────
    bos_b = df[df["bos_bullish"]]
    bos_s = df[df["bos_bearish"]]
    fig.add_trace(
        go.Scatter(x=bos_b.index, y=bos_b["high"],
                   mode="markers+text", text="BOS↑", textposition="top center",
                   name="BOS Bull",
                   marker=dict(symbol="circle-open", size=8, color="#26a69a")),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=bos_s.index, y=bos_s["low"],
                   mode="markers+text", text="BOS↓", textposition="bottom center",
                   name="BOS Bear",
                   marker=dict(symbol="circle-open", size=8, color="#ef5350")),
        row=1, col=1,
    )

    # ── CHoCH markers ─────────────────────────────────────────────────────────
    choch_b = df[df["choch_bullish"]]
    choch_s = df[df["choch_bearish"]]
    if not choch_b.empty:
        fig.add_trace(
            go.Scatter(x=choch_b.index, y=choch_b["high"],
                       mode="markers+text", text="CHoCH↑", textposition="top center",
                       name="CHoCH Bull",
                       marker=dict(symbol="star", size=10, color="#00FF7F")),
            row=1, col=1,
        )
    if not choch_s.empty:
        fig.add_trace(
            go.Scatter(x=choch_s.index, y=choch_s["low"],
                       mode="markers+text", text="CHoCH↓", textposition="bottom center",
                       name="CHoCH Bear",
                       marker=dict(symbol="star", size=10, color="#FF4500")),
            row=1, col=1,
        )

    # ── Order Block rectangles ────────────────────────────────────────────────
    last_ts = df.index[-1]

    bull_obs = df[df["ob_bullish"]].tail(_MAX_SHAPES)
    bear_obs = df[df["ob_bearish"]].tail(_MAX_SHAPES)

    for idx, row in bull_obs.iterrows():
        fig.add_shape(
            type="rect", x0=idx, x1=last_ts,
            y0=row["ob_bullish_low"], y1=row["ob_bullish_high"],
            line=dict(color="rgba(38,166,154,0.6)", width=1),
            fillcolor="rgba(38,166,154,0.12)",
            row=1, col=1,
        )
    for idx, row in bear_obs.iterrows():
        fig.add_shape(
            type="rect", x0=idx, x1=last_ts,
            y0=row["ob_bearish_low"], y1=row["ob_bearish_high"],
            line=dict(color="rgba(239,83,80,0.6)", width=1),
            fillcolor="rgba(239,83,80,0.12)",
            row=1, col=1,
        )

    # ── FVG rectangles (unfilled only) ────────────────────────────────────────
    bull_fvg = df[df["fvg_bullish"] & ~df["fvg_bull_filled"]].tail(_MAX_SHAPES)
    bear_fvg = df[df["fvg_bearish"] & ~df["fvg_bear_filled"]].tail(_MAX_SHAPES)

    for idx, row in bull_fvg.iterrows():
        fig.add_shape(
            type="rect", x0=idx, x1=last_ts,
            y0=row["fvg_bull_bottom"], y1=row["fvg_bull_top"],
            line=dict(color="rgba(100,220,130,0.7)", width=1),
            fillcolor="rgba(100,220,130,0.15)",
            row=1, col=1,
        )
    for idx, row in bear_fvg.iterrows():
        fig.add_shape(
            type="rect", x0=idx, x1=last_ts,
            y0=row["fvg_bear_bottom"], y1=row["fvg_bear_top"],
            line=dict(color="rgba(220,80,80,0.7)", width=1),
            fillcolor="rgba(220,80,80,0.15)",
            row=1, col=1,
        )

    # ── Buy / Sell signal markers ─────────────────────────────────────────────
    long_sig  = df[df["signal"] == 1]
    short_sig = df[df["signal"] == -1]

    if not long_sig.empty:
        fig.add_trace(
            go.Scatter(x=long_sig.index, y=long_sig["low"] * 0.998,
                       mode="markers", name="BUY",
                       marker=dict(symbol="triangle-up", size=14, color="#00FF00",
                                   line=dict(color="white", width=1))),
            row=1, col=1,
        )
    if not short_sig.empty:
        fig.add_trace(
            go.Scatter(x=short_sig.index, y=short_sig["high"] * 1.002,
                       mode="markers", name="SELL",
                       marker=dict(symbol="triangle-down", size=14, color="#FF0000",
                                   line=dict(color="white", width=1))),
            row=1, col=1,
        )

    # ── Row 2 : RSI ───────────────────────────────────────────────────────────
    fig.add_trace(
        go.Scatter(x=df.index, y=df["RSI"], name="RSI",
                   line=dict(color="#BA55D3", width=1.5)),
        row=2, col=1,
    )
    for y_val, colour, dash in [
        (RSI_OVERBOUGHT, "red",   "dash"),
        (RSI_OVERSOLD,   "green", "dash"),
        (50,             "gray",  "dot"),
    ]:
        fig.add_hline(y=y_val, line_dash=dash, line_color=colour, row=2, col=1)

    # ── Row 3 : Signal Strength ───────────────────────────────────────────────
    bar_colours = [
        "#26a69a" if s == 1 else "#ef5350" if s == -1 else "#444444"
        for s in df["signal"]
    ]
    fig.add_trace(
        go.Bar(x=df.index, y=df["signal_strength"],
               name="Signal Strength", marker_color=bar_colours),
        row=3, col=1,
    )

    # ── Row 4 : Equity Curve ──────────────────────────────────────────────────
    if equity_curve is not None:
        eq_index = df.index[: len(equity_curve)]
        fig.add_trace(
            go.Scatter(x=eq_index, y=equity_curve,
                       name="Equity", line=dict(color="#FFD700", width=2),
                       fill="tozeroy", fillcolor="rgba(255,215,0,0.08)"),
            row=4, col=1,
        )

    # ── Layout ────────────────────────────────────────────────────────────────
    symbol_cfg = getattr(__import__("config"), "SYMBOL", "")
    tf_cfg     = getattr(__import__("config"), "TIMEFRAME", "")

    fig.update_layout(
        title=f"SMC + FVG + EMA + RSI — {symbol_cfg} {tf_cfg}",
        template="plotly_dark",
        height=1200,
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=1),
        xaxis_rangeslider_visible=False,
        margin=dict(l=60, r=160, t=60, b=40),
    )

    fig.write_html(output_file)
    print(f"Chart saved → {output_file}")
    return fig
