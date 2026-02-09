"""
Streamlit Authentication Module
Simple password-based authentication
"""

import hashlib
import os
from functools import wraps
from typing import Optional

import streamlit as st


class AuthManager:
    """Simple authentication manager"""

    def __init__(self):
        self.password_configured = True
        self.password_hash = self._get_password_hash()
        self.username = "admin"

    def _get_password_hash(self) -> Optional[str]:
        """Get password from environment or Vault"""
        # Try environment first
        password = os.getenv("DASHBOARD_PASSWORD")

        if not password:
            # Try Vault
            try:
                import hvac

                client = hvac.Client(
                    url=os.getenv("VAULT_URL", "http://localhost:8200"),
                    token=os.getenv("VAULT_TOKEN", ""),
                )
                if client.is_authenticated():
                    secret = client.read("secret/data/dashboard")
                    if secret and "data" in secret:
                        password = secret["data"]["data"].get("password")
            except Exception:
                password = None

        if not password:
            self.password_configured = False
            return None

        return hashlib.sha256(password.encode()).hexdigest()

    def login(self) -> bool:
        """Show login form - Fixed for proper rendering"""
        st.set_page_config(
            page_title="Shadow Alpha - Trading Terminal",
            page_icon="👻",
            layout="centered",
        )

        st.markdown(
            """
        <style>
        section[data-testid="stSidebar"] {
            display: none !important;
        }
        
        .stApp {
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 50%, #0f0f1a 100%) !important;
        }
        
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            max-width: 450px !important;
            margin: 0 auto !important;
        }
        
        .stTextInput > div > div > input {
            background: rgba(0, 0, 0, 0.5) !important;
            border: 1px solid rgba(0, 212, 255, 0.3) !important;
            border-radius: 8px !important;
            color: #fff !important;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #00d4ff !important;
        }
        
        .stButton > button {
            background: linear-gradient(135deg, #00d4ff 0%, #7b2cbf 100%) !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
        
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        <div style="text-align: center; margin-bottom: 0.5rem;">
            <h1 style="font-family: 'Orbitron', sans-serif; font-size: 42px; 
               background: linear-gradient(90deg, #00d4ff, #7b2cbf); 
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;
               margin: 0; letter-spacing: 4px;">SHADOW</h1>
            <h2 style="font-family: 'Orbitron', sans-serif; font-size: 36px;
               background: linear-gradient(90deg, #00d4ff, #7b2cbf);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;
               margin: 0; letter-spacing: 4px;">ALPHA</h2>
            <p style="color: #8892b0; font-size: 12px; letter-spacing: 6px; 
               text-transform: uppercase; margin-top: 5px;">Trading Terminal</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        with st.container():
            col1, col2, col3 = st.columns([1, 8, 1])
            with col2:
                st.markdown(
                    """
                <div style="background: rgba(20, 20, 35, 0.95); border: 1px solid rgba(0, 212, 255, 0.3);
                    border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 15px;">
                    <span style="color: #00d4ff; font-size: 14px; letter-spacing: 2px;">
                        ▸ ACCESS TERMINAL ◂
                    </span>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                with st.form("login_form", clear_on_submit=True):
                    if not self.password_configured:
                        st.error(
                            "Dashboard password is not configured. Set "
                            "`DASHBOARD_PASSWORD` or store `password` at "
                            "`secret/data/dashboard` in Vault."
                        )
                        return False

                    username = st.text_input(
                        "Username",
                        value="admin",
                        label_visibility="collapsed",
                        placeholder="Username",
                    )
                    password = st.text_input(
                        "Password",
                        type="password",
                        label_visibility="collapsed",
                        placeholder="Password",
                    )

                    submitted = st.form_submit_button("▶ AUTHENTICATE", use_container_width=True)

                    if submitted:
                        if self._verify_password(username, password):
                            st.session_state["authenticated"] = True
                            st.session_state["username"] = username
                            st.rerun()
                        else:
                            st.error("Access Denied")

        st.markdown(
            """
        <div style="text-align: center; margin-top: 15px; color: #64748b; font-size: 11px;">
            <span style="display: inline-block; width: 6px; height: 6px; background: #00ff88; 
               border-radius: 50%; margin-right: 5px; animation: blink 1.5s infinite;"></span>
            Systems Operational
        </div>
        <style>@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }</style>
        """,
            unsafe_allow_html=True,
        )

        return st.session_state.get("authenticated", False)

    def _verify_password(self, username: str, password: str) -> bool:
        """Verify username and password"""
        if not self.password_hash or username != self.username:
            return False

        input_hash = hashlib.sha256(password.encode()).hexdigest()
        return input_hash == self.password_hash

    def check_auth(self):
        """Check if user is authenticated"""
        if not st.session_state.get("authenticated", False):
            self.login()
            st.stop()

    def logout(self):
        """Logout user"""
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.rerun()


def require_auth(func):
    """Decorator to require authentication"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = AuthManager()
        auth.check_auth()
        return func(*args, **kwargs)

    return wrapper
