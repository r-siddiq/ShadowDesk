"""
Signals Page
View ML-generated trading signals
"""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.chart import render_empty_chart
from dashboard.components.pulse import render_system_pulse
from dashboard.components.styles import apply_global_styles, render_page_header
from dashboard.config import DashboardConfig
from dashboard.utils.api_client import TradingAPIClient
from dashboard.utils.auth import AuthManager

# Force authentication - check before anything else
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state.get("authenticated", False):
    st.switch_page("app.py")

auth = AuthManager()

st.set_page_config(page_title="Shadow Alpha - Signals", page_icon="👻", layout="wide")


def get_mock_signals():
    """Generate mock signals for demo"""
    import random

    symbols = DashboardConfig.DEFAULT_WATCHLIST[:20]
    signals = []

    for sym in symbols:
        signal = random.choice(["BUY", "SELL", "HOLD"])
        confidence = random.randint(45, 95) if signal != "HOLD" else random.randint(30, 55)
        price = round(random.uniform(50, 500), 2)
        change = round(random.uniform(-5, 5), 2)

        signals.append(
            {
                "symbol": sym,
                "signal": signal,
                "confidence": confidence,
                "current_price": price,
                "change_pct": change,
            }
        )

    return signals


def main():
    apply_global_styles()
    render_page_header("Trading Signals", "💡")

    api = st.session_state.get("api_client") or TradingAPIClient(DashboardConfig.FASTAPI_BASE)

    # Controls
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        min_confidence = st.slider(
            "Minimum Confidence",
            0,
            100,
            60,
            help="Filter signals below this confidence",
        )

    with col2:
        signal_filter = st.selectbox("Signal Type", ["All", "BUY", "SELL", "HOLD"])

    with col3:
        st.caption("")
        if st.button("🔄 Refresh Signals"):
            st.rerun()

    # Get signals
    try:
        risk_params = st.session_state.get("risk_params", DashboardConfig.get_risk_params())
        watchlist = risk_params.get("watchlist", DashboardConfig.DEFAULT_WATCHLIST)
        signals = api.get_signals_batch(watchlist, min_confidence=min_confidence / 100)
    except Exception as e:
        st.warning(f"Live signals are unavailable: {e}")
        signals = []

    # Filter signals
    if signal_filter != "All":
        signals = [s for s in signals if s.get("signal", "").upper() == signal_filter.upper()]

    # Display signals
    if signals:
        # Create DataFrame for display - keep numeric values as numbers
        data = []
        for s in signals:
            data.append(
                {
                    "Symbol": s.get("symbol", ""),
                    "Signal": s.get("signal", "HOLD"),
                    "Confidence": s.get("confidence", 0) * 100,
                    "Price": s.get("current_price", 0),
                    "Change": s.get("change_pct", 0),
                }
            )

        df = pd.DataFrame(data)

        # Color code by signal
        def highlight_signals(row):
            color = "#e8f5e9" if row["Signal"] == "BUY" else "#ffebee" if row["Signal"] == "SELL" else "#f5f5f5"
            return [f"background-color: {color}" for _ in row]

        # Format columns for display only when rendering
        display_df = df.copy()
        display_df["Confidence"] = display_df["Confidence"].apply(lambda x: f"{x:.0f}%")
        display_df["Price"] = display_df["Price"].apply(lambda x: f"${x:.2f}")
        display_df["Change"] = display_df["Change"].apply(lambda x: f"{x:+.2f}%")

        st.dataframe(
            display_df.style.apply(highlight_signals, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        # Signal counts
        buy_count = sum(1 for s in signals if s.get("signal", "").upper() == "BUY")
        sell_count = sum(1 for s in signals if s.get("signal", "").upper() == "SELL")
        hold_count = sum(1 for s in signals if s.get("signal", "").upper() == "HOLD")

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("BUY Signals", buy_count)
        col_b.metric("SELL Signals", sell_count)
        col_c.metric("HOLD Signals", hold_count)

    else:
        st.info("No signals match your criteria")

    st.markdown("---")

    # Interactive chart section
    st.subheader("📈 Interactive Chart")

    col_left, col_right = st.columns([1, 2])

    with col_left:
        selected_symbol = st.selectbox("Select Symbol", DashboardConfig.DEFAULT_WATCHLIST[:10], index=0)

        st.markdown("#### Technical Indicators")
        st.checkbox("SMA 20", value=True)
        st.checkbox("Volume", value=True)

    with col_right:
        st.info(
            f"Live price history for {selected_symbol} is not exposed by the FastAPI "
            "service yet. Chart rendering is disabled until that endpoint exists."
        )
        render_empty_chart(key=f"empty_chart_{selected_symbol}")

    # System Pulse
    st.markdown("---")
    render_system_pulse()


if __name__ == "__main__":
    main()
