"""
System Pulse Component
Real-time log streamer
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from utils.logger import get_logs


def render_system_pulse(num_lines: int = 8, expanded: bool = True):
    """
    Render the System Pulse expander with live logs

    Args:
        num_lines: Number of log lines to display
        expanded: Whether the expander is expanded by default
    """
    # Auto-refresh
    st_autorefresh(interval=2000, key="pulse_refresh")

    with st.expander("💓 System Pulse", expanded=expanded):
        logs = get_logs(num_lines=num_lines, use_mock=True)

        # Display logs with styling
        for log in reversed(logs):
            # Color code based on content
            if "ERROR" in log or "error" in log:
                st.markdown(
                    f"<span style='color: #ef5350;'>{log}</span>",
                    unsafe_allow_html=True,
                )
            elif "BUY" in log:
                st.markdown(
                    f"<span style='color: #26a69a;'>{log}</span>",
                    unsafe_allow_html=True,
                )
            elif "SELL" in log:
                st.markdown(
                    f"<span style='color: #ef5350;'>{log}</span>",
                    unsafe_allow_html=True,
                )
            elif "signal" in log.lower() or "SIGNAL" in log:
                st.markdown(
                    f"<span style='color: #7e57c2;'>{log}</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<span style='color: #78909c;'>{log}</span>",
                    unsafe_allow_html=True,
                )


def render_connection_status(api_client):
    """Render connection status indicator"""
    try:
        api_client.get_health()
        return True, "🟢 Connected"
    except Exception as e:
        return False, f"🔴 Disconnected: {str(e)[:50]}"
