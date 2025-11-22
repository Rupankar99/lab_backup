import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# ✅ Sample data generator
def load_data():
    # Generate some sample incidents
    data = [
        {
            "id": 1,
            "source": "jira",
            "title": "Database connection timeout",
            "description": "Connection to DB timed out during peak load.",
            "priority": "High",
            "status": "Open",
            "created_at": datetime.now() - timedelta(days=2),
            "last_updated": datetime.now() - timedelta(hours=5),
            "reporter": "Alice",
            "assigned_to": "Bob",
            "jira_ticket_id": "JIRA-101",
            "jira_project": "Backend",
            "jira_issue_type": "Bug",
            "jira_url": "https://jira.example.com/browse/JIRA-101",
            "slack_channel": None,
            "slack_thread_ts": None,
            "slack_user": None,
            "slack_permalink": None,
            "pd_incident_id": None,
            "pd_service_id": None,
            "pd_escalation_policy": None,
            "pd_html_url": None,
        },
        {
            "id": 2,
            "source": "slack",
            "title": "High error rate alert",
            "description": "Slack alert: error rate > 5% for past 10 minutes.",
            "priority": "Medium",
            "status": "Investigating",
            "created_at": datetime.now() - timedelta(days=1, hours=4),
            "last_updated": datetime.now() - timedelta(hours=2),
            "reporter": "System Bot",
            "assigned_to": "Charlie",
            "jira_ticket_id": None,
            "jira_project": None,
            "jira_issue_type": None,
            "jira_url": None,
            "slack_channel": "#alerts",
            "slack_thread_ts": "172934",
            "slack_user": "alertbot",
            "slack_permalink": "https://slack.com/thread/172934",
            "pd_incident_id": None,
            "pd_service_id": None,
            "pd_escalation_policy": None,
            "pd_html_url": None,
        },
        {
            "id": 3,
            "source": "pagerduty",
            "title": "Service outage in EU region",
            "description": "PagerDuty triggered by monitoring system.",
            "priority": "Critical",
            "status": "Resolved",
            "created_at": datetime.now() - timedelta(days=3),
            "last_updated": datetime.now() - timedelta(days=1),
            "reporter": "Monitoring",
            "assigned_to": "DevOps Team",
            "jira_ticket_id": None,
            "jira_project": None,
            "jira_issue_type": None,
            "jira_url": None,
            "slack_channel": None,
            "slack_thread_ts": None,
            "slack_user": None,
            "slack_permalink": None,
            "pd_incident_id": "PD-9981",
            "pd_service_id": "svc-prod-eu",
            "pd_escalation_policy": "Primary On-call",
            "pd_html_url": "https://pagerduty.com/incidents/PD-9981",
        },
    ]

    return pd.DataFrame(data)

def show():
    st.title("🚨 Incident Dashboard")
    st.caption("Centralized view of all incidents across Jira, Slack, and PagerDuty")

    # Load data
    df = load_data()

    if df.empty:
        st.warning("No incident data found.")
        st.stop()

    # Format timestamps
    for col in ["created_at", "last_updated"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

    # Tabs for sections
    tabs = st.tabs(["📋 Master View", "🧾 Jira Incidents", "💬 Slack Alerts", "🚨 PagerDuty Incidents"])

    # 🎯 MASTER VIEW
    with tabs[0]:
        st.subheader("📋 Master Incident View")
        st.dataframe(
            df[[
                "id", "source", "title", "description", "priority", "status",
                "created_at", "last_updated", "reporter", "assigned_to"
            ]],
            use_container_width=True,
            hide_index=True
        )

    # 🧾 JIRA TAB
    with tabs[1]:
        st.subheader("🧾 Jira Incidents")
        jira_df = df[df["source"] == "jira"]

        if not jira_df.empty:
            jira_cols = [
                "jira_ticket_id", "jira_project", "jira_issue_type", "jira_url",
                "priority", "title", "status", "reporter", "assigned_to", "created_at"
            ]
            jira_cols = [col for col in jira_cols if col in jira_df.columns]
            st.dataframe(jira_df[jira_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No Jira incidents found.")

    # 💬 SLACK TAB
    with tabs[2]:
        st.subheader("💬 Slack Alerts")
        slack_df = df[df["source"] == "slack"]

        if not slack_df.empty:
            slack_cols = [
                "slack_channel", "slack_thread_ts", "slack_user", "slack_permalink",
                "title", "priority", "status", "created_at"
            ]
            slack_cols = [col for col in slack_cols if col in slack_df.columns]
            st.dataframe(slack_df[slack_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No Slack alerts found.")

    # 🚨 PAGERDUTY TAB
    with tabs[3]:
        st.subheader("🚨 PagerDuty Incidents")
        pd_df = df[df["source"] == "pagerduty"]

        if not pd_df.empty:
            pd_cols = [
                "pd_incident_id", "pd_service_id", "pd_escalation_policy", "pd_html_url",
                "title", "priority", "status", "created_at"
            ]
            pd_cols = [col for col in pd_cols if col in pd_df.columns]
            st.dataframe(pd_df[pd_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No PagerDuty incidents found.")
