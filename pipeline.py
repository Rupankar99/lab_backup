"""
Live Pipeline Visualization Component
"""
import streamlit as st
import time
from typing import List, Dict

def render_pipeline(stages: List[Dict], current_stage: int = 0):
    """
    Render a live pipeline with stages

    Args:
        stages: List of stage dicts with keys: name, icon, description
        current_stage: Index of currently active stage (0-based)
    """

    stage_html = ""

    for idx, stage in enumerate(stages):
        # Determine stage status
        if idx < current_stage:
            status = "completed"
            icon_class = "✓"
        elif idx == current_stage:
            status = "active"
            icon_class = stage.get("icon", "⚙️")
        else:
            status = "inactive"
            icon_class = stage.get("icon", "○")

        # Add connector except for last stage
        connector = ""
        if idx < len(stages) - 1:
            connector_status = "active" if idx < current_stage else ""
            connector = f'<div class="pipeline-connector {connector_status}"></div>'

        stage_html += f"""
        <div class="pipeline-stage {status}">
            <div class="pipeline-icon">{icon_class}</div>
            <div class="pipeline-label">{stage['name']}</div>
            {connector}
        </div>
        """

    pipeline_html = f"""
    <div class="pipeline-container">
        {stage_html}
    </div>
    """

    st.markdown(pipeline_html, unsafe_allow_html=True)


def run_pipeline_animation(stages: List[Dict], duration_per_stage: int = 2):
    """
    Run an animated pipeline with progress through stages

    Args:
        stages: List of pipeline stages
        duration_per_stage: Seconds to spend on each stage
    """

    pipeline_placeholder = st.empty()
    status_placeholder = st.empty()

    for idx, stage in enumerate(stages):
        # Update pipeline visualization
        with pipeline_placeholder.container():
            render_pipeline(stages, current_stage=idx)

        # Update status message
        status_placeholder.info(f"⚙️ **{stage['name']}**: {stage.get('description', 'Processing...')}")

        # Simulate processing time
        time.sleep(duration_per_stage)

    # Final completed state
    with pipeline_placeholder.container():
        render_pipeline(stages, current_stage=len(stages))

    status_placeholder.success(f"✅ **Pipeline Complete!** All {len(stages)} stages finished successfully.")


def create_incident_pipeline():
    """Create the incident analysis pipeline stages"""
    return [
        {
            "name": "Data Collection",
            "icon": "🔍",
            "description": "Gathering logs, metrics, and alerts from all sources"
        },
        {
            "name": "Classification",
            "icon": "🎯",
            "description": "Classifying incident severity and priority"
        },
        {
            "name": "RAG Analysis",
            "icon": "📚",
            "description": "Searching knowledge base for similar incidents"
        },
        {
            "name": "Agentic MCP",
            "icon": "🤖",
            "description": "AI agents diagnosing root cause and generating solutions"
        },
        {
            "name": "Remediation",
            "icon": "🛠️",
            "description": "Creating action plan and escalation path"
        },
        {
            "name": "Ticketing",
            "icon": "📋",
            "description": "Creating incident ticket and notifications"
        }
    ]
