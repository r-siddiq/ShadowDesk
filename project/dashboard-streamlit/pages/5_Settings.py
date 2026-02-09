"""
Settings Page
Configure risk parameters, API keys, and watchlist
"""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

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

st.set_page_config(page_title="Shadow Alpha - Settings", page_icon="👻", layout="wide")


def main():
    apply_global_styles()
    render_page_header("Settings", "⚙️")
    st.title("⚙️ Settings")
    st.markdown("### Configure Trading Parameters")

    params = st.session_state.get("risk_params", DashboardConfig.get_risk_params())

    tab1, tab2, tab3, tab4 = st.tabs(["Risk Parameters", "Watchlist", "API Keys", "System"])

    with tab1:
        st.subheader("🎚️ Risk Parameters")
        st.caption("Configure risk management settings")

        with st.form("risk_params_form"):
            col1, col2 = st.columns(2)

            with col1:
                max_positions = st.number_input(
                    "Max Concurrent Positions",
                    min_value=1,
                    max_value=20,
                    value=params.get("max_positions", 10),
                )

                position_size_pct = (
                    st.slider(
                        "Position Size (% of portfolio)",
                        min_value=0.5,
                        max_value=10.0,
                        value=params.get("position_size_pct", 2.0) * 100,
                        step=0.5,
                    )
                    / 100
                )

                stop_loss_pct = (
                    st.slider(
                        "Stop Loss %",
                        min_value=5,
                        max_value=30,
                        value=int(params.get("stop_loss_pct", 0.15) * 100),
                    )
                    / 100
                )

            with col2:
                max_total_risk = (
                    st.slider(
                        "Max Total Risk (% of portfolio)",
                        min_value=10,
                        max_value=50,
                        value=int(params.get("max_total_risk", 0.25) * 100),
                    )
                    / 100
                )

                min_confidence = (
                    st.slider(
                        "Minimum Signal Confidence %",
                        min_value=40,
                        max_value=90,
                        value=int(params.get("min_confidence", 0.60) * 100),
                    )
                    / 100
                )

            submitted = st.form_submit_button("Save Parameters", type="primary")

            if submitted:
                params["max_positions"] = max_positions
                params["position_size_pct"] = position_size_pct
                params["stop_loss_pct"] = stop_loss_pct
                params["max_total_risk"] = max_total_risk
                params["min_confidence"] = min_confidence

                if DashboardConfig.save_risk_params(params):
                    st.session_state["risk_params"] = params
                    st.success("Parameters saved to Vault")
                else:
                    st.session_state["risk_params"] = params
                    st.success("Parameters saved locally")

        st.markdown("#### Current Values")
        current_data = {
            "Parameter": [
                "Max Positions",
                "Position Size",
                "Stop Loss",
                "Max Total Risk",
                "Min Confidence",
            ],
            "Value": [
                f"{params.get('max_positions', 10)}",
                f"{params.get('position_size_pct', 0.02)*100:.1f}%",
                f"{params.get('stop_loss_pct', 0.15)*100:.0f}%",
                f"{params.get('max_total_risk', 0.25)*100:.0f}%",
                f"{params.get('min_confidence', 0.60)*100:.0f}%",
            ],
        }
        st.table(pd.DataFrame(current_data))

    with tab2:
        st.subheader("📋 Watchlist")
        st.caption("Manage symbols to trade")

        watchlist = params.get("watchlist", DashboardConfig.DEFAULT_WATCHLIST)

        col1, col2 = st.columns([3, 1])
        with col1:
            new_symbol = st.text_input("Add Symbol", placeholder="e.g., AAPL").upper()
        with col2:
            if st.button("Add") and new_symbol:
                if new_symbol not in watchlist:
                    watchlist.append(new_symbol)
                    params["watchlist"] = watchlist
                    DashboardConfig.save_risk_params(params)
                    st.rerun()

        st.markdown("#### Current Watchlist")

        cols = st.columns(6)
        for i, symbol in enumerate(watchlist):
            with cols[i % 6]:
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"**{symbol}**")
                with col_b:
                    if st.button("×", key=f"remove_{symbol}"):
                        watchlist.remove(symbol)
                        params["watchlist"] = watchlist
                        DashboardConfig.save_risk_params(params)
                        st.rerun()

        with st.expander("Quick Add Popular Symbols"):
            popular = ["SPY", "QQQ", "IWM", "DIA", "TLT", "GLD", "SLV", "USO"]
            selected = st.multiselect("Select", popular)
            if st.button("Add Selected") and selected:
                for sym in selected:
                    if sym not in watchlist:
                        watchlist.append(sym)
                params["watchlist"] = list(set(watchlist))
                DashboardConfig.save_risk_params(params)
                st.rerun()

    with tab3:
        st.subheader("🔑 API Configuration")
        st.caption("Configure broker API keys")

        alpaca_keys = DashboardConfig.get_alpaca_keys()

        with st.form("api_keys_form"):
            api_key = st.text_input("Alpaca API Key", value=alpaca_keys.get("api_key", ""), type="password")
            secret_key = st.text_input(
                "Alpaca Secret Key",
                value=alpaca_keys.get("secret_key", ""),
                type="password",
            )

            save_keys = st.form_submit_button("Save API Keys", type="primary")

            if save_keys and api_key and secret_key:
                if DashboardConfig.save_alpaca_keys(api_key, secret_key):
                    st.success("API keys saved to Vault")
                else:
                    st.error("Failed to save to Vault")

        st.markdown("#### Status")
        if alpaca_keys.get("api_key"):
            st.success("API keys configured")
        else:
            st.warning("API keys not configured")

        st.info("Get your API keys from https://app.alpaca.markets/")

    with tab4:
        st.subheader("⚙️ System Settings")

        st.slider(
            "Dashboard Refresh Rate (seconds)",
            min_value=1,
            max_value=30,
            value=DashboardConfig.REFRESH_INTERVAL,
        )

        st.radio("Theme", ["Light", "Dark"], horizontal=True)

        st.slider(
            "System Pulse Log Lines",
            min_value=5,
            max_value=20,
            value=DashboardConfig.LOG_LINES,
        )

        st.markdown("#### Connection Test")

        col_a, col_b = st.columns(2)

        with col_a:
            if st.button("Test FastAPI Connection"):
                try:
                    api = TradingAPIClient(DashboardConfig.FASTAPI_BASE)
                    api.get_health()
                    st.success("✓ FastAPI connected")
                except Exception as e:
                    st.error(f"✗ FastAPI error: {e}")

        with col_b:
            if st.button("Test Vault Connection"):
                try:
                    import hvac

                    client = hvac.Client(url=DashboardConfig.VAULT_URL, token=DashboardConfig.VAULT_TOKEN)
                    if client.is_authenticated():
                        st.success("✓ Vault connected")
                    else:
                        st.error("✗ Vault authentication failed")
                except Exception as e:
                    st.error(f"✗ Vault error: {e}")

    st.markdown("---")
    render_system_pulse()


if __name__ == "__main__":
    main()
