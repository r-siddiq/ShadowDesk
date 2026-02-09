"""
Interactive Chart Component
Using Plotly for stable, non-rescaling trading charts
"""

from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


def _format_time(value) -> str:
    """Safely format time value to string YYYY-MM-DD for Plotly"""
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str):
        # Already string, check if it's a date string
        return value[:10] if len(value) >= 10 else value
    return str(value)[:10]


def create_candlestick_data(df: pd.DataFrame) -> list:
    """Convert DataFrame to candlestick format for Plotly"""
    data = []
    for idx, row in df.iterrows():
        time_val = row.get("time", row.get("Date", row.get("date", idx)))
        data.append(
            {
                "time": _format_time(time_val),
                "open": float(row.get("Open", row.get("open", 0))),
                "high": float(row.get("High", row.get("high", 0))),
                "low": float(row.get("Low", row.get("low", 0))),
                "close": float(row.get("Close", row.get("close", 0))),
            }
        )
    return data


def create_indicator_series(df: pd.DataFrame, column: str) -> list:
    """Create line series for indicators"""
    data = []
    for idx, row in df.iterrows():
        val = row.get(column, 0)
        if pd.notna(val):
            time_val = row.get("time", row.get("Date", row.get("date", idx)))
            data.append({"time": _format_time(time_val), "value": float(val)})
    return data


def create_volume_series(df: pd.DataFrame) -> list:
    """Create volume histogram with colors"""
    colors = []
    for _, row in df.iterrows():
        close = row.get("Close", row.get("close", 0))
        open_val = row.get("Open", row.get("open", 0))
        if close >= open_val:
            colors.append("#26a69a")
        else:
            colors.append("#ef5350")
    return colors


def render_price_chart(df: pd.DataFrame, positions: list = None, indicators: dict = None, key: str = None):
    """
    Render interactive price chart with Plotly - stable scale that doesn't rescale with every tick

    Args:
        df: DataFrame with OHLCV data
        positions: List of position dicts with entry_price, side, entry_date
        indicators: Dict of indicator names to column names
        key: Unique key for this chart instance to prevent unnecessary re-renders
    """
    if df is None or df.empty:
        st.warning("No data available for chart")
        return

    # Prepare time column
    if "time" not in df.columns and "Date" in df.columns:
        df = df.rename(columns={"Date": "time"})
    if "date" in df.columns and "time" not in df.columns:
        df = df.rename(columns={"date": "time"})

    # Create time list once
    time_list = []
    for idx, row in df.iterrows():
        time_val = row.get("time", idx)
        time_list.append(_format_time(time_val))

    # Calculate price range for fixed y-axis scale
    all_prices = []
    for _, row in df.iterrows():
        all_prices.extend([row.get("High", row.get("high", 0)), row.get("low", row.get("Low", 0))])
    all_prices = [p for p in all_prices if pd.notna(p) and p > 0]

    if not all_prices:
        st.warning("No valid price data for chart")
        return

    price_min = min(all_prices)
    price_max = max(all_prices)
    price_padding = (price_max - price_min) * 0.1  # 10% padding
    y_range = [price_min - price_padding, price_max + price_padding]

    # Create figure with secondary y-axis for volume
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=("", ""),
        specs=[[{"type": "candlestick"}], [{"type": "bar"}]],
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=time_list,
            open=df.get("Open", df.get("open", [0] * len(df))),
            high=df.get("High", df.get("high", [0] * len(df))),
            low=df.get("Low", df.get("low", [0] * len(df))),
            close=df.get("Close", df.get("close", [0] * len(df))),
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
            increasing_fillcolor="#26a69a",
            decreasing_fillcolor="#ef5350",
            name="Price",
            showlegend=True,
            legendgroup="price",
        ),
        row=1,
        col=1,
    )

    # Add SMA indicator if available
    if "SMA_20" in df.columns:
        sma_values = df["SMA_20"].fillna(method="ffill").fillna(method="bfill")
        fig.add_trace(
            go.Scatter(
                x=time_list,
                y=sma_values,
                mode="lines",
                line=dict(color="#2196F3", width=1.5),
                name="SMA 20",
                showlegend=True,
                legendgroup="sma",
            ),
            row=1,
            col=1,
        )

    # Add position markers
    if positions:
        for pos in positions:
            entry_date = _format_time(pos.get("entry_date", ""))
            entry_price = pos.get("entry_price", 0)
            side = pos.get("side", "")

            if entry_date and entry_price > 0:
                fig.add_annotation(
                    x=entry_date,
                    y=entry_price,
                    text=(f"↑ {side.upper()}" if side.lower() == "buy" else f"↓ {side.upper()}"),
                    showarrow=True,
                    arrowhead=1,
                    arrowcolor="#26a69a" if side.lower() == "buy" else "#ef5350",
                    font=dict(color="#ffffff"),
                    bgcolor="#26a69a" if side.lower() == "buy" else "#ef5350",
                    row=1,
                    col=1,
                )

    # Volume chart
    volume_colors = create_volume_series(df)
    fig.add_trace(
        go.Bar(
            x=time_list,
            y=df.get("Volume", df.get("volume", [0] * len(df))),
            marker_color=volume_colors,
            name="Volume",
            showlegend=True,
            legendgroup="volume",
        ),
        row=2,
        col=1,
    )

    # Update layout with FIXED Y-axis scale - doesn't rescale with price movements
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#1a1a2e",
        font=dict(color="#d1d4dc", family="Inter, sans-serif"),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
        xaxis=dict(
            showgrid=True,
            gridcolor="#2b2b43",
            showline=True,
            linecolor="#2b2b43",
            rangeslider=dict(visible=False),
            type="date",
        ),
        yaxis=dict(
            title="Price",
            showgrid=True,
            gridcolor="#2b2b43",
            showline=True,
            linecolor="#2b2b43",
            fixedrange=True,  # CRITICAL: Prevents Y-axis from rescaling on data updates
            range=y_range,
            zeroline=False,
        ),
        yaxis2=dict(
            title="Volume",
            showgrid=False,
            showline=False,
            zeroline=False,
            fixedrange=True,
        ),
        margin=dict(l=60, r=60, t=60, b=60),
        height=450,
    )

    # CRITICAL: Disable autoscaling to prevent re-scaling on every price movement
    fig.update_yaxes(fixedrange=True, row=1, col=1)

    st.plotly_chart(fig, use_container_width=True, key=key or f"price_chart_{id(df)}")


def render_empty_chart(key: str = None):
    """Render placeholder chart with sample data"""
    st.info("📈 Select a symbol to view the interactive chart")

    # Generate sample data for demo - stable, not changing
    dates = pd.date_range(end=datetime.today(), periods=30, freq="D")
    base_price = 155.0
    sample_data = pd.DataFrame(
        {
            "time": dates,
            "Open": [base_price + np.random.uniform(-2, 2) for _ in range(30)],
            "High": [base_price + np.random.uniform(2, 5) for _ in range(30)],
            "Low": [base_price + np.random.uniform(-5, -2) for _ in range(30)],
            "Close": [base_price + np.random.uniform(-2, 2) for _ in range(30)],
        }
    )
    sample_data["SMA_20"] = sample_data["Close"].rolling(5).mean()

    render_price_chart(sample_data, positions=[], key=key)
