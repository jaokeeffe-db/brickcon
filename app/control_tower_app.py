"""
Maintenance Control Tower — Databricks App (Streamlit)

A plant manager's dashboard for the Predictive Maintenance demo. Shows:
  - Asset floor map: 22 assets colour-coded by risk level (live from Lakebase)
  - Active alerts: CRITICAL and HIGH disruption events
  - AI chat interface: routes queries to the Mosaic AI maintenance agent
  - Cost comparison view: planned repair vs. unplanned failure cost

Run locally (with .env configured):
  streamlit run app/control_tower_app.py

Deploy to Databricks Apps:
  See app.yaml and databricks.yml for deployment configuration.

Environment variables (from .env or Databricks App secrets):
  LAKEBASE_HOST, LAKEBASE_PORT, LAKEBASE_DATABASE, LAKEBASE_USER, LAKEBASE_PASSWORD
  DATABRICKS_HOST, DATABRICKS_TOKEN
  AGENT_ENDPOINT_NAME (default: maintenance-agent-endpoint)
"""

import os
import time
from datetime import datetime

import psycopg2
import psycopg2.extras
import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Maintenance Control Tower",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENT_ENDPOINT = os.getenv("AGENT_ENDPOINT_NAME", "maintenance-agent-endpoint")

LAKEBASE_CONFIG = {
    "host": os.getenv("LAKEBASE_HOST"),
    "port": int(os.getenv("LAKEBASE_PORT", "5432")),
    "dbname": os.getenv("LAKEBASE_DATABASE", "databricks_postgres"),
    "user": os.getenv("LAKEBASE_USER"),
    "password": os.getenv("LAKEBASE_PASSWORD"),
    "sslmode": "require",
    "connect_timeout": 5,
}

# Risk level → colour mapping for the floor map
RISK_COLOURS = {
    "CRITICAL": "#FF4444",
    "HIGH":     "#FF8C00",
    "MEDIUM":   "#FFD700",
    "LOW":      "#22C55E",
    "UNKNOWN":  "#94A3B8",
}

RISK_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH":     "🟠",
    "MEDIUM":   "🟡",
    "LOW":      "🟢",
    "UNKNOWN":  "⚪",
}

# ---------------------------------------------------------------------------
# Data loading (Lakebase)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)  # Refresh every 30 seconds
def load_asset_health() -> list[dict]:
    """Load live asset health from Lakebase asset_health_live table."""
    if not LAKEBASE_CONFIG["host"]:
        return _mock_asset_health()
    try:
        conn = psycopg2.connect(**LAKEBASE_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT asset_id, health_score, risk_level, current_vibration,
                       current_temp, rated_max_vibration, estimated_rul_hours,
                       production_line_id, criticality_tier, last_updated
                FROM asset_health_live
                ORDER BY health_score ASC
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        st.warning(f"Could not connect to Lakebase: {e}. Showing mock data.")
        return _mock_asset_health()
    finally:
        if "conn" in locals():
            conn.close()


@st.cache_data(ttl=30)
def load_active_disruptions() -> list[dict]:
    """Load active disruption events from Lakebase."""
    if not LAKEBASE_CONFIG["host"]:
        return _mock_disruptions()
    try:
        conn = psycopg2.connect(**LAKEBASE_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT disruption_id, asset_id, risk_level, impacted_line_id,
                       detection_timestamp, estimated_rul_hours,
                       estimated_downtime_cost, recommended_action, status
                FROM asset_disruption
                WHERE status = 'ACTIVE'
                ORDER BY risk_level DESC, detection_timestamp DESC
                LIMIT 10
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        return _mock_disruptions()
    finally:
        if "conn" in locals():
            conn.close()


@st.cache_data(ttl=60)
def load_recent_recommendations() -> list[dict]:
    """Load the 5 most recent AI-generated recommendations."""
    if not LAKEBASE_CONFIG["host"]:
        return []
    try:
        conn = psycopg2.connect(**LAKEBASE_CONFIG)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT rec_id, asset_id, recommendation_text,
                       cost_to_fix, cost_of_downtime, urgency_hours,
                       net_recommendation, created_at
                FROM maintenance_recommendations
                ORDER BY created_at DESC
                LIMIT 5
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        if "conn" in locals():
            conn.close()


# ---------------------------------------------------------------------------
# Mock data (used when Lakebase is not yet configured)
# ---------------------------------------------------------------------------

def _mock_asset_health() -> list[dict]:
    assets = [
        ("Motor_4",     "CRITICAL", 22.0,  8.93, 38.1, 8.5,  5.8,  "Line_1", 1),
        ("Compressor_1","HIGH",     42.0,  8.2,  72.0, 10.0, 18.0, "Line_1", 1),
        ("Pump_2",      "HIGH",     55.0,  4.1,  71.5, 5.5,  32.0, "Line_2", 2),
        ("Motor_6",     "MEDIUM",   68.0,  4.5,  68.2, 8.0,  None, "Line_3", 3),
        ("Motor_1",     "LOW",      85.0,  1.8,  38.2, 9.0,  None, "Line_1", 2),
        ("Motor_2",     "LOW",      88.0,  1.6,  35.4, 8.0,  None, "Line_1", 2),
        ("Motor_3",     "LOW",      90.0,  2.1,  40.1, 9.5,  None, "Line_2", 2),
        ("Pump_1",      "LOW",      92.0,  1.4,  31.5, 6.0,  None, "Line_1", 2),
        ("Turbine_1",   "LOW",      95.0,  2.8,  55.0, 12.0, None, "Line_4", 1),
        ("Turbine_2",   "LOW",      94.0,  2.9,  54.5, 12.0, None, "Line_4", 1),
    ]
    return [
        {
            "asset_id": a[0], "risk_level": a[1], "health_score": a[2],
            "current_vibration": a[3], "current_temp": a[4],
            "rated_max_vibration": a[5], "estimated_rul_hours": a[6],
            "production_line_id": a[7], "criticality_tier": a[8],
            "last_updated": datetime.now(),
        }
        for a in assets
    ]


def _mock_disruptions() -> list[dict]:
    return [
        {
            "disruption_id": 1,
            "asset_id": "Motor_4",
            "risk_level": "CRITICAL",
            "impacted_line_id": "Line_1",
            "detection_timestamp": datetime.now(),
            "estimated_rul_hours": 5.8,
            "estimated_downtime_cost": 420800.0,
            "recommended_action": "SCHEDULE_IMMEDIATE",
            "status": "ACTIVE",
        },
        {
            "disruption_id": 2,
            "asset_id": "Compressor_1",
            "risk_level": "HIGH",
            "impacted_line_id": "Line_1",
            "detection_timestamp": datetime.now(),
            "estimated_rul_hours": 18.0,
            "estimated_downtime_cost": 85000.0,
            "recommended_action": "SCHEDULE_PLANNED",
            "status": "ACTIVE",
        },
    ]


# ---------------------------------------------------------------------------
# Agent query
# ---------------------------------------------------------------------------

def query_agent(user_message: str, history: list[dict]) -> str:
    """Send a message to the Mosaic AI maintenance agent endpoint."""
    try:
        client = WorkspaceClient()
        messages = [
            ChatMessage(role=ChatMessageRole.USER if m["role"] == "user" else ChatMessageRole.ASSISTANT,
                       content=m["content"])
            for m in history
        ]
        messages.append(ChatMessage(role=ChatMessageRole.USER, content=user_message))

        response = client.serving_endpoints.query(
            name=AGENT_ENDPOINT,
            messages=messages,
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except Exception as e:
        return (
            f"**Demo mode** — Agent endpoint not yet deployed.\n\n"
            f"*Error: {e}*\n\n"
            f"**Simulated response for '{user_message}':**\n\n"
            f"Motor_4 on Line_1 is in **CRITICAL** condition (Health Score: 22/100). "
            f"Current vibration of 8.9 mm/s exceeds the rated maximum of 8.5 mm/s. "
            f"Estimated Remaining Useful Life: **5.8 hours**.\n\n"
            f"**Recommendation: SCHEDULE_IMMEDIATE**\n\n"
            f"Planned bearing replacement cost: **$3,200**\n"
            f"Cost if line fails unplanned tonight: **$420,800**\n"
            f"Savings by acting now: **$417,600**\n\n"
            f"Refer to `motor_bearing_replacement.md` Section 5 for the full procedure."
        )


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------

def render_floor_map(health_data: list[dict]) -> None:
    """Render the asset floor map as a grid of colour-coded tiles."""
    st.subheader("Asset Floor Map")

    # Group by production line
    lines: dict[str, list] = {}
    for asset in health_data:
        line = asset.get("production_line_id", "Unknown")
        lines.setdefault(line, []).append(asset)

    for line_id in sorted(lines.keys()):
        st.markdown(f"**{line_id}**")
        cols = st.columns(min(len(lines[line_id]), 6))
        for i, asset in enumerate(sorted(lines[line_id], key=lambda a: a["health_score"])):
            colour = RISK_COLOURS.get(asset["risk_level"], RISK_COLOURS["UNKNOWN"])
            emoji = RISK_EMOJI.get(asset["risk_level"], "⚪")
            hs = asset.get("health_score", 0)
            rul = asset.get("estimated_rul_hours")
            rul_text = f"{rul:.1f}h RUL" if rul is not None else "—"

            with cols[i % 6]:
                st.markdown(
                    f"""
                    <div style="
                        background-color: {colour}22;
                        border: 2px solid {colour};
                        border-radius: 8px;
                        padding: 8px;
                        text-align: center;
                        margin-bottom: 8px;
                    ">
                        <div style="font-size: 1.2em;">{emoji}</div>
                        <div style="font-weight: bold; font-size: 0.85em;">{asset['asset_id']}</div>
                        <div style="color: {colour}; font-weight: bold;">{hs:.0f}/100</div>
                        <div style="font-size: 0.75em; color: #666;">{rul_text}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.markdown("---")


def render_alerts(disruptions: list[dict]) -> None:
    """Render the active disruption events panel."""
    if not disruptions:
        st.success("No active disruptions. All assets operating normally.")
        return

    for d in disruptions:
        colour = RISK_COLOURS.get(d["risk_level"], "#888")
        emoji = RISK_EMOJI.get(d["risk_level"], "⚪")
        cost = d.get("estimated_downtime_cost")
        cost_text = f"${cost:,.0f} at risk" if cost else ""
        rul = d.get("estimated_rul_hours")
        rul_text = f"RUL: {rul:.1f}h" if rul else ""

        with st.container(border=True):
            cols = st.columns([0.1, 0.6, 0.3])
            with cols[0]:
                st.markdown(f"## {emoji}")
            with cols[1]:
                st.markdown(
                    f"**{d['asset_id']}** — {d['risk_level']} on {d['impacted_line_id']}\n\n"
                    f"{d.get('recommended_action', '')} · {rul_text}"
                )
            with cols[2]:
                st.markdown(f"**{cost_text}**")
                if st.button("Ask AI →", key=f"ask_{d['disruption_id']}"):
                    st.session_state["prefill_query"] = (
                        f"What should I do about {d['asset_id']}? "
                        f"It is showing {d['risk_level']} risk on {d['impacted_line_id']}."
                    )


def render_cost_comparison(health_data: list[dict]) -> None:
    """Render the cost comparison table for at-risk assets."""
    at_risk = [a for a in health_data if a.get("risk_level") in {"CRITICAL", "HIGH"}]
    if not at_risk:
        st.info("No at-risk assets to compare.")
        return

    # Build table data
    rows = []
    for a in at_risk:
        # Approximate costs from health data (full data comes from gold_cost_impact in production)
        rul = a.get("estimated_rul_hours") or 0
        line_output = {"Line_1": 52000, "Line_2": 48000, "Line_3": 35000, "Line_4": 61000}.get(
            a.get("production_line_id", "Line_1"), 52000
        )
        unplanned = round(rul * line_output + 3200 * 1.5, 0)
        rows.append({
            "Asset": a["asset_id"],
            "Line": a.get("production_line_id", "—"),
            "Health Score": f"{a['health_score']:.0f}/100",
            "RUL (hrs)": f"{rul:.1f}" if rul else "—",
            "Plan Now ($)": "$3,200",
            "Unplanned Cost ($)": f"${unplanned:,.0f}",
            "Action": a.get("risk_level", "—"),
        })

    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main app layout
# ---------------------------------------------------------------------------

def main():
    # Header
    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        st.title("Maintenance Control Tower")
        st.caption("Powered by Databricks Data Intelligence Platform · Unity Catalog · Mosaic AI")
    with col2:
        st.markdown(f"**Last refresh:** {datetime.now().strftime('%H:%M:%S')}")
        if st.button("Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    # Load data
    health_data = load_asset_health()
    disruptions = load_active_disruptions()

    # Top metrics strip
    total = len(health_data)
    critical_count = sum(1 for a in health_data if a.get("risk_level") == "CRITICAL")
    high_count = sum(1 for a in health_data if a.get("risk_level") == "HIGH")
    low_count = sum(1 for a in health_data if a.get("risk_level") == "LOW")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Assets", total)
    m2.metric("CRITICAL", critical_count, delta=f"-{critical_count} need action" if critical_count else None, delta_color="inverse")
    m3.metric("HIGH", high_count, delta=f"-{high_count} watch" if high_count else None, delta_color="inverse")
    m4.metric("LOW (Healthy)", low_count)
    m5.metric("Active Alerts", len(disruptions))

    st.divider()

    # Main content: two columns
    left_col, right_col = st.columns([0.55, 0.45])

    with left_col:
        tab1, tab2, tab3 = st.tabs(["Floor Map", "Active Alerts", "Cost Analysis"])
        with tab1:
            render_floor_map(health_data)
        with tab2:
            st.subheader("Active Disruptions")
            render_alerts(disruptions)
        with tab3:
            st.subheader("Cost-to-Fix vs Unplanned Failure")
            render_cost_comparison(health_data)

    with right_col:
        st.subheader("AI Maintenance Assistant")
        st.caption("Ask about any asset — get diagnosis, repair plan, and cost analysis")

        # Initialise chat history
        if "messages" not in st.session_state:
            st.session_state["messages"] = []

        # Handle prefilled query from alert button
        if "prefill_query" in st.session_state:
            prefill = st.session_state.pop("prefill_query")
        else:
            prefill = ""

        # Chat history display
        chat_container = st.container(height=420)
        with chat_container:
            if not st.session_state["messages"]:
                st.markdown(
                    "_Ask me anything — e.g. "Motor 4 is vibrating. Should I stop Line 1?"_"
                )
            for msg in st.session_state["messages"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        # Input
        user_input = st.chat_input(
            "Ask about an asset...",
            key="chat_input",
        ) or prefill

        if user_input:
            # Show user message
            st.session_state["messages"].append({"role": "user", "content": user_input})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(user_input)

            # Get agent response
            with chat_container:
                with st.chat_message("assistant"):
                    with st.spinner("Reasoning..."):
                        response = query_agent(user_input, st.session_state["messages"][:-1])
                    st.markdown(response)

            st.session_state["messages"].append({"role": "assistant", "content": response})
            st.rerun()

        # Quick query buttons
        st.markdown("**Quick queries:**")
        q_col1, q_col2 = st.columns(2)
        with q_col1:
            if st.button("Motor 4 status?"):
                st.session_state["prefill_query"] = (
                    "What is the current health status of Motor_4 and what should I do?"
                )
                st.rerun()
            if st.button("Cost to fix Motor 4?"):
                st.session_state["prefill_query"] = (
                    "What is the cost comparison for repairing Motor_4 now vs. waiting for a failure?"
                )
                st.rerun()
        with q_col2:
            if st.button("Which lines are at risk?"):
                st.session_state["prefill_query"] = (
                    "Which production lines are at risk and what is the financial exposure?"
                )
                st.rerun()
            if st.button("Clear chat"):
                st.session_state["messages"] = []
                st.rerun()


if __name__ == "__main__":
    main()
