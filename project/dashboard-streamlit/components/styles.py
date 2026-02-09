"""
Custom Styles Module
Consistent styling across all pages
"""

from contextlib import contextmanager

import streamlit as st


def apply_global_styles():
    """Apply global custom styles"""
    st.markdown(
        """
    <style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global styles */
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    /* Headings */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        color: #f1f5f9;
    }
    
    /* Metrics styling */
    div[data-testid="stMetric"] {
        background: rgba(0, 212, 255, 0.05);
        border: 1px solid rgba(0, 212, 255, 0.2);
        border-radius: 12px;
        padding: 15px;
    }
    
    div[data-testid="stMetric"] label {
        color: #94a3b8;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #00d4ff;
        font-size: 24px;
        font-weight: 600;
    }
    
    /* Cards */
    .card {
        background: rgba(20, 20, 32, 0.8);
        border: 1px solid rgba(0, 212, 255, 0.15);
        border-radius: 16px;
        padding: 20px;
        margin: 10px 0;
    }
    
    /* DataFrames */
    div[data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
    }
    
    /* Buttons */
    div.stButton > button {
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    /* Tabs */
    div[data-testid="stTabs"] {
        background: transparent;
    }
    
    div[data-testid="stTabs"] button {
        border-radius: 8px 8px 0 0;
        background: rgba(0, 0, 0, 0.2);
    }
    
    div[data-testid="stTabs"] button[aria-selected="true"] {
        background: rgba(0, 212, 255, 0.1);
        border-bottom: 2px solid #00d4ff;
    }
    
    /* Expanders */
    div[data-testid="stExpander"] {
        border: 1px solid rgba(0, 212, 255, 0.15);
        border-radius: 12px;
        overflow: hidden;
    }
    
    div[data-testid="stExpander"] summary {
        background: rgba(0, 0, 0, 0.2);
        padding: 12px 16px;
    }
    
    /* Form inputs */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div {
        border-radius: 8px;
        border: 1px solid rgba(0, 212, 255, 0.2);
        background: rgba(0, 0, 0, 0.3);
    }
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #00d4ff;
        box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
    }
    
    /* Sliders */
    div.stSlider > div > div > div[role="slider"] {
        background: #00d4ff;
    }
    
    /* Dividers */
    hr {
        border-color: rgba(0, 212, 255, 0.15);
    }
    
    /* Tables */
    table {
        border-collapse: separate;
        border-spacing: 0;
    }
    
    th {
        background: rgba(0, 0, 0, 0.3) !important;
        color: #94a3b8 !important;
        text-transform: uppercase;
        font-size: 11px;
        letter-spacing: 1px;
    }
    
    td {
        background: transparent !important;
    }
    
    tr:hover td {
        background: rgba(0, 212, 255, 0.05) !important;
    }
    
    /* Success/Error/Info messages */
    div[data-testid="stSuccess"] {
        background: rgba(0, 255, 136, 0.1);
        border: 1px solid rgba(0, 255, 136, 0.3);
        border-radius: 8px;
    }
    
    div[data-testid="stError"] {
        background: rgba(255, 82, 82, 0.1);
        border: 1px solid rgba(255, 82, 82, 0.3);
        border-radius: 8px;
    }
    
    div[data-testid="stInfo"] {
        background: rgba(0, 212, 255, 0.1);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 8px;
    }
    
    /* Spinner */
    div[data-testid="stSpinner"] {
        text-align: center;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.2);
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(0, 212, 255, 0.3);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(0, 212, 255, 0.5);
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, icon: str = "📈"):
    """Render a styled page header"""
    st.markdown(
        f"""
    <div style="margin-bottom: 20px;">
        <h1 style="margin-bottom: 5px;">{icon} {title}</h1>
        <div style="height: 2px; background: linear-gradient(90deg, #00d4ff, transparent); width: 100px;"></div>
    </div>
    """,
        unsafe_allow_html=True,
    )


@contextmanager
def render_card(title: str):
    """Render a styled card as a context manager."""
    st.markdown(
        f"""
    <div class="card">
        <h3 style="margin: 0 0 10px 0; color: #00d4ff;">{title}</h3>
    """,
        unsafe_allow_html=True,
    )
    yield
    st.markdown("</div>", unsafe_allow_html=True)


def render_signal_badge(signal: str) -> str:
    """Render a colored signal badge"""
    colors = {"BUY": "#26a69a", "SELL": "#ef5350", "HOLD": "#94a3b8"}
    color = colors.get(signal.upper(), "#94a3b8")
    return (
        f'<span style="background: {color}; color: white; padding: 4px 12px; '
        f'border-radius: 20px; font-weight: 600;">{signal}</span>'
    )
