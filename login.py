from pathlib import Path
import sys
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from incident_db.db.connection import get_connection
from incident_db.models.user import UserModel

conn = get_connection()
users = UserModel(conn)

def show():
    # st.set_page_config(page_title="Login | Incident IQ", page_icon="🔐", layout="centered")
    st.title("🔐 Login to Incident IQ")

    email = st.text_input("Email", value="svk@epoch.com")
    password = st.text_input("Password", type="password", value="souvik123")

    if st.button("Login"):
        user = UserModel(conn)
        user_data = user.authenticate(email, password)

        st.write(user_data)

        if user_data['is_loggedin']:
            st.session_state.user_logged_in = user_data['is_loggedin']
            st.session_state.username = user_data['name']
            st.session_state.id = user_data['id']
            st.success("✅ Login successful")
            st.rerun()  # redirect to dashboard
        else:
            st.error("❌ Invalid email or password")
