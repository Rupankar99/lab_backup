import uuid
import streamlit as st
import pandas as pd
from datetime import datetime
import random
from incident_db.db.connection import get_connection
from incident_db.models.classifier_output import ClassifierOutputsModel
from task_queue.producer import Producer

conn = get_connection()
classifier_output = ClassifierOutputsModel(conn)
    
@st.cache_data
def get_pending_data():
    data = classifier_output.find_unapproved_inc()
    return pd.DataFrame(data)

@st.dialog("Approve Record")
def approval_dialog(record):
    st.write(f"**Payload ID:** {record['payload_id']}")
    st.write(f"**Environment:** {record['environment']}")
    st.write(f"**Current Severity:** {record['severity_id']}")
    st.write(f"**Corrective Action:** {record['corrective_action']}")

    st.divider()

    # final_severity = st.selectbox(
    #     "Final Severity",
    #     ["S4", "", "Medium", "Low"],
    #     index=["S4", "S3", "S2", "S1"].index(record['severity_id'])
    # )

    approver_suggestion = st.text_area("Approver Notes", height=100)

    if st.button("Approve", type="primary", key="approve_suggestion"):

        st.write(approver_suggestion)
        st.write(st.session_state.id)

        try:
            classifier_output.update_by_id(id=int(record['id']),approved_corrective_action=approver_suggestion,approved_by="ADMIN",approved_ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),is_llm_correction_approved=1)
            st.success("Approved successfully")
            
            record_json = record.to_dict() if hasattr(record, "to_dict") else dict(record)
            record_json.update({
                "approved_corrective_action": approver_suggestion,
                "approved_by": st.session_state.id,
                "approved_ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            import json
            json_data = json.dumps(record_json)

            print(record_json,"record_json")
         
            # Rupankar Code
            # Send JSON to producer
            producer1 = Producer([
                {"task": "llm_invoke", "data": json_data}
            ])

            producer1.start()
            producer1.join()

        except Exception as e:
            import traceback
            st.error(f"❌ Error: {e}")
            st.code(traceback.format_exc())
        finally:
            pass
            # st.rerun()

def show():
    st.title("Admin Approvals")

    if 'approved_ids' not in st.session_state:
        st.session_state.approved_ids = []
    if 'approval_data' not in st.session_state:
        st.session_state.approval_data = []

    tab1, tab2 = st.tabs(["Pending", "Approved"])

    with tab1:
        df = get_pending_data()
        print(df, "df data")

        if 'id' in df.columns:
            approved_ids = st.session_state.get('approved_ids', [])
            df = df[~df['id'].isin(approved_ids)]
        else:
            print("⚠️ Warning: 'id' column not found in df. Skipping filter.")
        col1, col2, col3 = st.columns(3)
        col1.metric("Pending", len(df))
        col2.metric("Critical", len(df[df['severity_id']=='Critical']))
        
        col1, col2, col3 = st.columns(3)
        env = col1.selectbox("Environment", ["All"] + df['environment'].unique().tolist())
        sev = col2.selectbox("Severity", ["All"] + df['severity_id'].unique().tolist())
        src = col3.selectbox("Source", ["All"] + df['source_type'].unique().tolist())

        # if env != "All":
        #     df = df[df['Environment'] == env]
        # if sev != "All":
        #     df = df[df['Severity'] == sev]
        # if src != "All":
        #     df = df[df['Source'] == src]

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "bert_score": st.column_config.NumberColumn(format="%.2f"),
                "rule_score": st.column_config.NumberColumn(format="%.2f"),
            }
        )

        record_id = st.number_input("Enter ID to approve", min_value=1, step=1)

        if st.button("Approve", type="primary"):
            record = df[df['id'] == record_id]
            if not record.empty:
                approval_dialog(record.iloc[0])
            else:
                st.error("Record not found in pending list")

    with tab2:
        if st.session_state.approval_data:
            approved_df = pd.DataFrame(st.session_state.approval_data)
            st.dataframe(approved_df, use_container_width=True, hide_index=True)

            csv = approved_df.to_csv(index=False).encode('utf-8')
            st.download_button("Export CSV", csv, "approved.csv", "text/csv")
        else:
            st.info("No approved records")
