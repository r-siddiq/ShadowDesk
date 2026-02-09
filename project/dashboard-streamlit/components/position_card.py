"""
Position Card Component
Display position information with P&L
"""

import pandas as pd
import streamlit as st


def render_position_card(position: dict):
    """
    Render a single position card

    Args:
        position: Dict with symbol, qty, entry_price, current_price, etc.
    """
    symbol = position.get("symbol", "")
    qty = int(position.get("qty", 0))
    entry_price = float(position.get("avg_entry_price", position.get("entry_price", 0)))
    current_price = float(position.get("current_price", 0))

    # Calculate P&L
    market_value = current_price * qty
    cost_basis = entry_price * qty
    pnl = market_value - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

    # Color based on P&L
    pnl_color = "#26a69a" if pnl >= 0 else "#ef5350"
    pnl_prefix = "+" if pnl >= 0 else ""

    with st.container():
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

        with col1:
            st.markdown(f"**{symbol}**")
            st.caption(f"{qty} shares")

        with col2:
            st.markdown(f"Entry: ${entry_price:.2f}")
            st.markdown(f"Current: ${current_price:.2f}")

        with col3:
            st.markdown("P&L:")
            st.markdown(f":{pnl_color}[{pnl_prefix}${pnl:.2f} ({pnl_prefix}{pnl_pct:.2f}%)]")

        with col4:
            # Quick action button
            if st.button("Close", key=f"close_{symbol}"):
                return "close"

    return None


def render_positions_table(positions: list) -> pd.DataFrame:
    """
    Render positions as a table

    Returns:
        DataFrame of positions
    """
    if not positions:
        st.info("No open positions")
        return pd.DataFrame()

    # Convert to DataFrame for display
    data = []
    for pos in positions:
        entry = float(pos.get("avg_entry_price", pos.get("entry_price", 0)))
        current = float(pos.get("current_price", 0))
        qty = int(pos.get("qty", 0))
        pnl = (current - entry) * qty
        pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0

        data.append(
            {
                "Symbol": pos.get("symbol", ""),
                "Qty": qty,
                "Entry": f"${entry:.2f}",
                "Current": f"${current:.2f}",
                "P&L": f"${pnl:.2f}",
                "P&L %": f"{pnl_pct:.2f}%",
                "Side": pos.get("side", "").upper(),
            }
        )

    df = pd.DataFrame(data)

    # Display with formatting
    st.dataframe(df, use_container_width=True, hide_index=True)

    return df
