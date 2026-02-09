"""
Shadow Alpha - Autonomous Trading Dashboard
Main Streamlit Application
"""

import os
import sys

import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Add project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dashboard.components.pulse import render_system_pulse
from dashboard.config import DashboardConfig
from dashboard.utils.api_client import TradingAPIClient
from dashboard.utils.auth import AuthManager


def init_session_state():
    """Initialize session state variables"""
    if "api_client" not in st.session_state:
        st.session_state.api_client = TradingAPIClient(DashboardConfig.FASTAPI_BASE)

    if "risk_params" not in st.session_state:
        st.session_state.risk_params = DashboardConfig.get_risk_params()

    if "refresh_counter" not in st.session_state:
        st.session_state.refresh_counter = 0


def render_login_page():
    """Render login - delegates to auth module"""
    auth = AuthManager()
    auth.check_auth()  # Shows login if not authenticated, stops if failed


def render_sidebar():
    """Render sidebar with quick stats"""
    # Custom sidebar CSS
    st.markdown(
        """
    <style>
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0a0f 0%, #141420 100%);
        border-right: 1px solid rgba(0, 212, 255, 0.2);
    }
    
    /* Sidebar title */
    .sidebar-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 18px;
        color: #00d4ff;
        letter-spacing: 3px;
        text-align: center;
        padding: 10px 0;
        text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
    }
    
    /* Sidebar nav links */
    .nav-link {
        padding: 12px 16px;
        margin: 4px 0;
        border-radius: 10px;
        color: #94a3b8;
        transition: all 0.3s ease;
    }
    
    .nav-link:hover {
        background: rgba(0, 212, 255, 0.1);
        color: #00d4ff;
    }
    
    /* Connection status */
    .status-box {
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        margin: 10px 0;
    }
    
    .status-connected {
        background: rgba(0, 255, 136, 0.1);
        border: 1px solid rgba(0, 255, 136, 0.3);
        color: #00ff88;
    }
    
    .status-disconnected {
        background: rgba(255, 82, 82, 0.1);
        border: 1px solid rgba(255, 82, 82, 0.3);
        color: #ff5252;
    }
    
    /* Quick stat boxes */
    .stat-box {
        background: rgba(0, 212, 255, 0.05);
        border: 1px solid rgba(0, 212, 255, 0.2);
        border-radius: 10px;
        padding: 15px;
        text-align: center;
    }
    
    .stat-label {
        color: #64748b;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .stat-value {
        color: #00d4ff;
        font-size: 20px;
        font-weight: 600;
    }
    
    /* Logout button */
    .logout-btn {
        background: rgba(255, 82, 82, 0.1);
        border: 1px solid rgba(255, 82, 82, 0.3);
        color: #ff5252;
        border-radius: 10px;
        width: 100%;
        padding: 10px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        # Logo
        st.markdown('<div class="sidebar-title">▸ SHADOW ALPHA ◂</div>', unsafe_allow_html=True)
        st.markdown("---")

        # Auto-refresh
        st_autorefresh(interval=DashboardConfig.REFRESH_INTERVAL * 1000, key="refresh")

        # Connection status
        try:
            st.session_state.api_client.get_health()
            st.markdown(
                '<div class="status-box status-connected">● Systems Online</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            st.markdown(
                '<div class="status-box status-disconnected">● Demo Mode</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Quick stats
        try:
            account = st.session_state.api_client.get_account()

            st.markdown('<div class="stat-box">', unsafe_allow_html=True)
            st.markdown('<div class="stat-label">Portfolio Value</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="stat-value">${float(account.get("portfolio_value", 0)):,.2f}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown('<div class="stat-label">Cash</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="stat-value" style="font-size:16px;">${float(account.get("cash", 0)):,.0f}</div>',
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown('<div class="stat-label">Positions</div>', unsafe_allow_html=True)
                try:
                    positions = st.session_state.api_client.get_positions()
                    st.markdown(
                        f'<div class="stat-value" style="font-size:16px;">{len(positions)}</div>',
                        unsafe_allow_html=True,
                    )
                except Exception:
                    st.markdown(
                        '<div class="stat-value" style="font-size:16px;">0</div>',
                        unsafe_allow_html=True,
                    )
        except Exception:
            st.markdown('<div class="stat-box">', unsafe_allow_html=True)
            st.markdown('<div class="stat-label">Demo Account</div>', unsafe_allow_html=True)
            st.markdown('<div class="stat-value">$100,000</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")

        # Navigation with icons
        st.markdown("### NAVIGATION")

        nav_items = [
            ("pages/1_Dashboard.py", "🏠", "Dashboard"),
            ("pages/2_Signals.py", "💡", "Signals"),
            ("pages/3_Trade_Execution.py", "📝", "Trade Execution"),
            ("pages/4_Analytics.py", "📊", "Analytics"),
            ("pages/5_Settings.py", "⚙️", "Settings"),
        ]

        for path, icon, label in nav_items:
            st.page_link(path, label=f"{icon} {label}")

        st.markdown("---")

        # Logout
        if st.button("🚪 Disconnect", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()


def main():
    """Main application"""
    # Set page config
    st.set_page_config(
        page_title="Shadow Alpha - Trading Terminal",
        page_icon="👻",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Authentication check - shows login if needed
    render_login_page()

    # Only authenticated users see sidebar
    init_session_state()
    render_sidebar()

    # Main content
    st.title("🏠 Dashboard")
    st.markdown("Welcome to Shadow Alpha Trading Terminal")

    # Show system pulse at bottom
    render_system_pulse()


if __name__ == "__main__":
    main()
