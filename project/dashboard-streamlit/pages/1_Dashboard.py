"""
Dashboard Page
Portfolio overview and quick stats
"""

import os
import sys

import streamlit as st

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.position_card import render_positions_table
from dashboard.components.pulse import render_system_pulse
from dashboard.components.styles import apply_global_styles, render_card, render_page_header
from dashboard.config import DashboardConfig
from dashboard.utils.api_client import TradingAPIClient
from dashboard.utils.auth import AuthManager

# Force authentication - check before anything else
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state.get("authenticated", False):
    st.switch_page("app.py")

auth = AuthManager()

st.set_page_config(page_title="Shadow Alpha - Dashboard", page_icon="👻", layout="wide")


def main():
    # Apply global styles
    apply_global_styles()

    render_page_header("Dashboard", "🏠")

    # Initialize API client
    api = st.session_state.get("api_client") or TradingAPIClient(DashboardConfig.FASTAPI_BASE)

    # Fetch data
    try:
        account = api.get_account()
        positions = api.get_positions()
    except Exception as e:
        st.warning(f"Live API data unavailable: {e}")
        account = {
            "portfolio_value": 0.0,
            "cash": 0.0,
            "buying_power": 0.0,
            "pattern_day_trader": False,
            "trading_blocked": False,
        }
        positions = []

    # Top metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        with render_card("Portfolio Value"):
            st.metric(
                "Portfolio Value",
                f"${float(account.get('portfolio_value', 0)):,.2f}",
                delta=None,
            )

    with col2:
        cash = float(account.get("cash", 0))
        with render_card("Cash"):
            st.metric("Cash", f"${cash:,.2f}")

    with col3:
        buying_power = float(account.get("buying_power", 0))
        with render_card("Buying Power"):
            st.metric("Buying Power", f"${buying_power:,.2f}")

    with col4:
        # Calculate open positions value
        positions_value = sum(p.get("market_value", 0) for p in positions)
        with render_card("Positions"):
            st.metric("Positions", len(positions), f"${positions_value:,.2f} invested")

    st.markdown("---")

    # Positions section
    col_left, col_right = st.columns([2, 1])

    with col_left:
        with render_card("Open Positions"):
            st.subheader("📊 Open Positions")
            if positions:
                render_positions_table(positions)
            else:
                st.info("No open positions")

    with col_right:
        with render_card("Quick Actions"):
            st.subheader("📈 Quick Actions")

            if st.button("🔄 Refresh Data", use_container_width=True):
                st.rerun()

            if st.button("📊 Run Trading Cycle", use_container_width=True):
                with st.spinner("Running trading cycle..."):
                    try:
                        watchlist = st.session_state.get("risk_params", {}).get(
                            "watchlist", DashboardConfig.DEFAULT_WATCHLIST
                        )
                        result = api.run_trading_cycle(watchlist)
                        executions = result.get("executions", [])
                        successful = sum(1 for execution in executions if execution.get("status") == "success")
                        st.success(
                            f"Trading cycle complete: {successful} executed, " f"{len(result.get('errors', []))} errors"
                        )
                    except Exception as e:
                        st.error(f"Trading cycle failed: {e}")

            if st.button("📋 Get Signals", use_container_width=True):
                st.info("Go to the Signals page to view trading signals")

    st.markdown("---")

    # Recent trades section
    with render_card("Recent Trades"):
        st.subheader("📜 Recent Trades")
        try:
            trades = api.get_trade_history(limit=5)
            if trades:
                for trade in trades:
                    with st.container():
                        col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 2])
                        with col_a:
                            side = trade.get("side", "").upper()
                            color = "#26a69a" if side == "BUY" else "#ef5350"
                            st.markdown(f":{color}[**{side}**] {trade.get('symbol', '')}")
                        with col_b:
                            st.caption(f"Qty: {trade.get('qty', 0)}")
                        with col_c:
                            st.caption(f"${trade.get('filled_avg_price', 0):.2f}")
                        with col_d:
                            st.caption(trade.get("filled_at", "")[:19])
            else:
                st.info("No recent trades")
        except Exception as e:
            st.warning(f"Recent trade history is unavailable: {e}")

    # System Pulse at bottom
    st.markdown("---")
    render_system_pulse()


if __name__ == "__main__":
    main()
