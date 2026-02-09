"""
Analytics Page
Performance tracking and statistics
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

st.set_page_config(page_title="Shadow Alpha - Analytics", page_icon="👻", layout="wide")


def _build_trade_dataframe(trades: list[dict]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "symbol",
                "side",
                "qty",
                "filled_avg_price",
                "signed_notional",
            ]
        )

    trade_df = pd.DataFrame(trades).copy()
    trade_df["timestamp"] = pd.to_datetime(
        trade_df.get("filled_at").fillna(trade_df.get("submitted_at")), errors="coerce"
    )
    trade_df["qty"] = pd.to_numeric(trade_df.get("qty"), errors="coerce").fillna(0.0)
    trade_df["filled_avg_price"] = pd.to_numeric(trade_df.get("filled_avg_price"), errors="coerce").fillna(0.0)
    trade_df["notional"] = trade_df["qty"] * trade_df["filled_avg_price"]
    trade_df["side"] = trade_df["side"].astype(str).str.lower()
    trade_df["signed_notional"] = trade_df["notional"].where(trade_df["side"] == "sell", -trade_df["notional"])
    trade_df = trade_df.sort_values("timestamp")
    return trade_df


def main() -> None:
    apply_global_styles()
    render_page_header("Analytics", "📊")
    st.title("📊 Analytics")
    st.markdown("### Live Portfolio & Trade Statistics")

    api = st.session_state.get("api_client") or TradingAPIClient(DashboardConfig.FASTAPI_BASE)

    try:
        account = api.get_account()
        positions = api.get_positions()
        trades = api.get_trade_history(limit=100)
    except Exception as exc:
        st.warning(f"Analytics are unavailable because the API could not be reached: {exc}")
        st.markdown("---")
        render_system_pulse()
        return

    trade_df = _build_trade_dataframe(trades)
    total_positions_value = sum(float(position.get("market_value", 0.0)) for position in positions)
    total_trades = len(trade_df)
    gross_sells = trade_df.loc[trade_df["side"] == "sell", "notional"].sum() if not trade_df.empty else 0.0
    gross_buys = trade_df.loc[trade_df["side"] == "buy", "notional"].sum() if not trade_df.empty else 0.0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Portfolio Value", f"${float(account.get('portfolio_value', 0)):,.2f}")
    with col2:
        st.metric("Cash", f"${float(account.get('cash', 0)):,.2f}")
    with col3:
        st.metric(
            "Open Positions",
            f"{len(positions)}",
            delta=f"${total_positions_value:,.2f} invested",
        )
    with col4:
        st.metric("Filled Orders", f"{total_trades}")

    st.markdown("---")
    chart_col, stats_col = st.columns(2)

    with chart_col:
        st.subheader("📈 Cumulative Trade Notional")
        if trade_df.empty:
            st.info("No filled trade history is available yet.")
        else:
            chart_data = trade_df[["timestamp", "signed_notional"]].dropna()
            chart_data["cumulative_notional"] = chart_data["signed_notional"].cumsum()
            st.line_chart(chart_data.set_index("timestamp")["cumulative_notional"])

    with stats_col:
        st.subheader("🎯 Flow Summary")
        summary = pd.DataFrame(
            [
                ("Gross Buy Notional", f"${gross_buys:,.2f}"),
                ("Gross Sell Notional", f"${gross_sells:,.2f}"),
                ("Net Trade Notional", f"${gross_sells - gross_buys:,.2f}"),
                ("Buying Power", f"${float(account.get('buying_power', 0)):,.2f}"),
            ],
            columns=["Metric", "Value"],
        )
        st.table(summary)

    st.markdown("---")
    positions_col, trades_col = st.columns(2)

    with positions_col:
        st.subheader("📋 Current Positions")
        if positions:
            positions_df = pd.DataFrame(positions)[
                [
                    "symbol",
                    "qty",
                    "avg_entry_price",
                    "current_price",
                    "market_value",
                    "unrealized_pl",
                ]
            ]
            st.dataframe(positions_df, use_container_width=True, hide_index=True)
        else:
            st.info("No open positions.")

    with trades_col:
        st.subheader("🧾 Recent Filled Orders")
        if trade_df.empty:
            st.info("No filled orders yet.")
        else:
            display_df = trade_df[["timestamp", "symbol", "side", "qty", "filled_avg_price", "notional"]].tail(15)
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    render_system_pulse()


if __name__ == "__main__":
    main()
