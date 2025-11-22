import streamlit as st
from dotenv import load_dotenv
from pages import (
    dashboard,
    incident_analysis_crew,
    reports_incidents,
    reports_alerts,
    settings,
    workflow_visual,
    login,
    admin_approvals,
    incident_alerts
)

load_dotenv()
st.set_page_config(page_title="Incident IQ", page_icon="🚨", layout="wide")

if 'user_logged_in' not in st.session_state:
    st.session_state.user_logged_in = False
    st.session_state.username = None

# if not logged in, show login page only
if not st.session_state.user_logged_in:
    login.show()
    st.stop()

# Top user info (kept minimal)
col1, col2 = st.columns([6, 1])
with col2:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:8px;">
      <div style="background:#8B5CF6;color:white;width:32px;height:32px;border-radius:50%;
                  display:flex;align-items:center;justify-content:center;font-weight:600;">
        {st.session_state.username[0].upper() if st.session_state.username else "U"}
      </div>
      <div style="font-weight:500;">{st.session_state.username or "User"}</div>
    </div>
    """, unsafe_allow_html=True)

pages = [
    st.Page("pages/dashboard.py", title="Dashboard", icon="📊"),
    st.Page("pages/incident_analysis_crew.py", title="Analyze Incident", icon="🔍"),
    st.Page("pages/reports_incidents.py", title="Incidents Report", icon="📋"),
    st.Page("pages/incident_alerts.py", title="Alerts Report", icon="🔔"),
    st.Page("pages/admin_approvals.py", title="Approve Suggestions", icon="🔔"),
    st.Page("pages/workflow_visual.py", title="Workflow Visualization", icon="🧩"),
    st.Page("pages/settings.py", title="Settings", icon="⚙️"),
]

with st.sidebar:
    st.markdown("<h1 style='font-size:20px'>Incident IQ</h1>", unsafe_allow_html=True)
    st.divider()

page = st.navigation(pages)
title = getattr(page, "title", "Dashboard")

# Route by title and call each module's .show()
if title == "Dashboard":
    dashboard.show()
elif title == "Analyze Incident":
    incident_analysis_crew.show()
elif title == "Incidents Report":
    reports_incidents.show()
elif title == "Approve Suggestions":
    admin_approvals.show()
elif title == "Alerts Report":
    incident_alerts.show()
elif title == "Workflow Visualization":
    workflow_visual.show()
elif title == "Settings":
    settings.show()
elif title == "Incident Dashboard":
    incident_alerts.show()
elif title == "Logout" or title == "🔐 Logout":
    st.session_state.user_logged_in = False
    st.session_state.username = None
    st.experimental_rerun()
