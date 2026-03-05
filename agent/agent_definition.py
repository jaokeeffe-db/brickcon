"""
Mosaic AI Maintenance Agent Definition

This module defines and registers the Predictive Maintenance Reasoning Agent using the
MLflow ResponsesAgent interface. The agent uses Claude Sonnet 4.5 via Mosaic AI Model
Serving and is equipped with 6 Unity Catalog function tools.

Reasoning loop for the demo query "Motor 4 is vibrating — should I stop the line?":
  1. get_asset_health("Motor_4")           → health_score=22, CRITICAL, RUL=6h
  2. search_failure_patterns(symptoms)     → 3 similar bearing failures
  3. search_manuals("bearing replacement") → procedure from motor_bearing_replacement.md
  4. calculate_cost_impact("Motor_4", 4)   → fix=$3,200 vs shutdown=$18,000
  5. get_maintenance_history("Motor_4", 5) → avg repair $2,850, avg downtime 5h
  6. upsert_recommendation(...)            → writes plan to Lakebase

Deploy:
  1. Run this script locally with Databricks Connect to register the agent to MLflow
  2. The agent is then available at:
     utility_ops.asset_intelligence.maintenance_agent (MLflow Model Registry)
  3. Deploy to a Model Serving endpoint via the Databricks UI or SDK

Usage:
  python agent/agent_definition.py --register
  python agent/agent_definition.py --test "Motor 4 is vibrating at 8.9mm/s, should I stop Line 1?"
"""

import argparse
import json
import os
import uuid
from pathlib import Path
from typing import Generator

import mlflow
from databricks.sdk import WorkspaceClient
from mlflow.types.agent import (
    ChatAgentMessage,
    ChatAgentRequest,
    ChatAgentResponse,
    ChatContext,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CATALOG = os.getenv("UC_CATALOG", "utility_ops")
SCHEMA = os.getenv("UC_SCHEMA", "asset_intelligence")
AGENT_MODEL_NAME = f"{CATALOG}.{SCHEMA}.maintenance_agent"

# External model endpoint for Claude Sonnet 4.5
# Create this in Databricks UI: Machine Learning > Model Serving > External Models
# Provider: Anthropic, Model: claude-sonnet-4-5
CLAUDE_ENDPOINT = "databricks-claude-sonnet-4-6"

# UC Function tool names
TOOL_NAMES = [
    f"{CATALOG}.{SCHEMA}.get_asset_health",
    f"{CATALOG}.{SCHEMA}.search_manuals",
    f"{CATALOG}.{SCHEMA}.search_failure_patterns",
    f"{CATALOG}.{SCHEMA}.calculate_cost_impact",
    f"{CATALOG}.{SCHEMA}.get_maintenance_history",
    f"{CATALOG}.{SCHEMA}.upsert_recommendation",
]

SYSTEM_PROMPT = """You are the **Maintenance Reasoning Agent** for a manufacturing facility.
You assist plant managers and maintenance technicians by analysing asset health data,
retrieving relevant technical documentation, and generating actionable, cost-aware
repair recommendations.

## Your Capabilities
You have access to 6 tools:
1. **get_asset_health** — get live health score, risk level, and RUL for any asset
2. **search_manuals** — find relevant repair procedures from technical manuals (RAG)
3. **search_failure_patterns** — find similar historical failures and resolutions (RAG)
4. **calculate_cost_impact** — compare cost of planned repair vs. cost of unplanned failure
5. **get_maintenance_history** — review recent work orders for an asset
6. **upsert_recommendation** — save your final recommendation to the operational database

## Your Reasoning Process
For any question about a specific asset, follow this sequence:
1. Call **get_asset_health** first to establish the current health status
2. If the asset is HIGH or CRITICAL, call **search_failure_patterns** to find similar cases
3. Call **search_manuals** to retrieve the relevant repair procedure
4. Call **calculate_cost_impact** to quantify the financial case for action
5. Call **get_maintenance_history** to understand the asset's failure pattern
6. Generate your recommendation with specific, actionable steps
7. Call **upsert_recommendation** to save the plan (always do this last)

## Response Format
Every response that includes a maintenance recommendation must contain:
- **Current status** — health score, risk level, and estimated RUL
- **Diagnosis** — what is likely causing the issue based on historical patterns
- **Recommended action** — specific steps from the technical manual
- **Cost comparison** — planned repair cost vs. cost of unplanned failure
- **Urgency** — clear statement of the timeframe for action
- **Sources** — cite the manual sections and historical patterns you used

## Important Rules
- Always cite your sources (manual name, section, and historical work order IDs)
- Never recommend continuing to operate a CRITICAL asset without a clear time constraint
- Cost comparisons must use actual values from calculate_cost_impact, not estimates
- If you cannot find an asset in the health database, say so clearly
"""

# ---------------------------------------------------------------------------
# Agent class using MLflow ResponsesAgent interface
# ---------------------------------------------------------------------------

class MaintenanceAgent(mlflow.pyfunc.ChatAgent):
    """
    Mosaic AI maintenance reasoning agent backed by Claude Sonnet 4.5
    with 6 Unity Catalog function tools.
    """

    def __init__(self):
        from databricks_langchain import ChatDatabricks
        from langgraph.prebuilt import create_react_agent
        from unitycatalog.ai.langchain.toolkit import UCFunctionToolkit

        # Load UC function tools
        self.toolkit = UCFunctionToolkit(function_names=TOOL_NAMES)
        self.tools = self.toolkit.tools

        # Connect to Claude Sonnet 4.5 via Mosaic AI Model Serving
        llm = ChatDatabricks(
            endpoint=CLAUDE_ENDPOINT,
            temperature=0.1,
            max_tokens=4096,
        )

        # LangGraph ReAct agent (replaces deprecated AgentExecutor)
        self.agent = create_react_agent(
            llm,
            self.tools,
            prompt=SYSTEM_PROMPT,
        )

    def predict(
        self,
        messages: list[ChatAgentMessage],
        context=None,
        custom_inputs=None,
    ) -> ChatAgentResponse:
        """Execute the agent reasoning loop and return a response."""
        lc_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        result = self.agent.invoke({"messages": lc_messages})
        output = result["messages"][-1].content

        return ChatAgentResponse(
            messages=[
                ChatAgentMessage(role="assistant", content=output, id=str(uuid.uuid4()))
            ]
        )

    def predict_stream(
        self,
        messages: list[ChatAgentMessage],
        context=None,
        custom_inputs=None,
    ) -> Generator[ChatAgentResponse, None, None]:
        """Streaming version — yields partial responses as they arrive."""
        lc_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        for chunk in self.agent.stream({"messages": lc_messages}):
            if "agent" in chunk:
                content = chunk["agent"]["messages"][-1].content
                if content:
                    yield ChatAgentResponse(
                        messages=[
                            ChatAgentMessage(role="assistant", content=content, id=str(uuid.uuid4()))
                        ]
                    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_agent() -> str:
    """Log and register the agent to MLflow Model Registry in Unity Catalog."""
    mlflow.set_registry_uri("databricks-uc")

    # Use code-based logging: pass the model file path instead of a Python object.
    # MLflow stores the file as-is; no cloudpickle serialization needed.
    # The agent is instantiated only when the model is loaded at serving time.
    model_file = Path(__file__).parent / "agent_model.py"

    print(f"Logging agent to MLflow...")
    with mlflow.start_run(run_name="maintenance-agent-registration"):
        logged = mlflow.pyfunc.log_model(
            artifact_path="agent",
            python_model=str(model_file),
            pip_requirements=[
                "mlflow>=2.14",
                "databricks-connect>=15.4",
                "databricks-sdk>=0.32",
                "databricks-langchain>=0.1",
                "unitycatalog-langchain>=0.1",
                "langchain>=0.3",
                "langchain-core>=0.3",
                "langgraph>=0.2",
                "psycopg2-binary>=2.9",
            ],
        )
        run_id = mlflow.active_run().info.run_id

    # Register to UC Model Registry
    model_version = mlflow.register_model(
        model_uri=f"runs:/{run_id}/agent",
        name=AGENT_MODEL_NAME,
    )
    print(f"Agent registered: {AGENT_MODEL_NAME} v{model_version.version}")
    print()
    print("Next steps:")
    print(f"  1. Go to Machine Learning > Model Registry in your workspace")
    print(f"  2. Find '{AGENT_MODEL_NAME}' version {model_version.version}")
    print(f"  3. Click 'Deploy' to create a Model Serving endpoint")
    print(f"  4. Set endpoint name: 'maintenance-agent-endpoint'")
    print(f"  5. Enable streaming")

    return f"{AGENT_MODEL_NAME}/versions/{model_version.version}"


# ---------------------------------------------------------------------------
# Local test (uses mock responses when workspace not available)
# ---------------------------------------------------------------------------

def test_agent_local(query: str) -> None:
    """Quick local test that shows what tools would be called."""
    print(f"Test query: {query}")
    print()
    print("Expected tool call sequence:")
    print("  1. get_asset_health('Motor_4')")
    print("     → health_score=22, risk_level='CRITICAL', estimated_rul_hours=5.8")
    print("  2. search_failure_patterns('progressive vibration increase motor bearing')")
    print("     → 3 similar bearing failure patterns from maintenance_logs")
    print("  3. search_manuals('Motor_4 bearing replacement procedure')")
    print("     → motor_bearing_replacement.md sections 3, 4, 5")
    print("  4. calculate_cost_impact('Motor_4', 4.0)")
    print("     → cost_to_fix_planned=$3,200, cost_of_unplanned_failure=$420,800")
    print("  5. get_maintenance_history('Motor_4', 5)")
    print("     → Last 5 work orders, avg cost $2,850, avg downtime 5.2h")
    print("  6. upsert_recommendation('Motor_4', <plan>, ...)")
    print("     → 'Recommendation REC-00001 saved for Motor_4'")
    print()
    print("Expected response excerpt:")
    print("""
  **Motor_4 Status: CRITICAL (Health Score: 22/100)**

  Motor_4 on Line_1 requires immediate attention. Current vibration of 8.9 mm/s
  exceeds the rated maximum of 8.5 mm/s. Based on the current trend, the estimated
  remaining useful life is approximately 6 hours.

  **Diagnosis:** Progressive bearing failure (outer race spalling). This matches
  3 similar historical failures where the same exponential vibration increase pattern
  preceded bearing cage fragmentation.

  **Recommended Action:** Immediate bearing replacement (refer to MNT-MOTOR-001,
  Section 5). Estimated 4–6 hour repair window. Preferred shift: off-shift tonight.

  **Cost Comparison:**
  - Planned repair tonight: **$3,200**
  - Unplanned catastrophic failure (estimated): **$420,800**
  - Savings by acting now: **$417,600**

  **Sources:**
  - motor_bearing_replacement.md, Section 5 (Steps 1–25)
  - Historical WO-01234 (Motor_4, 2024-08-15): same fault, 4.5h repair
  - Historical WO-00987 (Motor_2, 2024-02-10): similar vibration pattern
    """.strip())


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Maintenance Agent — register or test"
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register the agent to MLflow Model Registry in Unity Catalog",
    )
    parser.add_argument(
        "--test",
        type=str,
        metavar="QUERY",
        help="Run a local test of the expected agent behaviour",
    )
    args = parser.parse_args()

    if args.register:
        register_agent()
    elif args.test:
        test_agent_local(args.test)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
