import streamlit as st
import requests
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Document Q&A Assistant", page_icon="📄", layout="centered")

if "token" not in st.session_state:
    st.session_state.token = None

if st.session_state.token:
    st.success("You are logged in. Use the sidebar to navigate.")
    if st.button("Logout"):
        st.session_state.token = None
        st.rerun()
    st.stop()

st.title("📄 Document Q&A Assistant")
st.subheader("Login")

tab_login, tab_signup = st.tabs(["Login", "Create Account"])

with tab_login:
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if not username or not password:
            st.error("Please enter both username and password.")
        else:
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/auth/login",
                    json={"username": username, "password": password},
                    timeout=10,
                )
                if resp.status_code == 200:
                    st.session_state.token = resp.json()["access_token"]
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Login failed."))
            except Exception as e:
                st.error(f"Could not connect to backend: {e}")

with tab_signup:
    st.info("Account creation requires an admin secret provided by your administrator.")
    with st.form("signup_form"):
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        admin_secret = st.text_input("Admin Secret", type="password")
        signup_submitted = st.form_submit_button("Create Account")

    if signup_submitted:
        if not new_username or not new_password or not admin_secret:
            st.error("All fields are required.")
        else:
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/auth/signup",
                    json={"username": new_username, "password": new_password, "admin_secret": admin_secret},
                    timeout=10,
                )
                if resp.status_code == 200:
                    st.session_state.token = resp.json()["access_token"]
                    st.success("Account created and logged in!")
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Signup failed."))
            except Exception as e:
                st.error(f"Could not connect to backend: {e}")
