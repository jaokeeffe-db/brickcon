"""
MLflow ChatAgent entry point — code-based logging.

This file is stored by MLflow as code (not pickled). It is re-imported at
serving time to reconstruct the agent. Do NOT run this file directly.

Register via:  python agent/agent_definition.py --register
"""

import os
import uuid
from typing import Generator

import mlflow
from mlflow.types.agent import ChatAgentMessage, ChatAgentResponse

# ---------------------------------------------------------------------------
# Configuration (mirrors agent_definition.py)
# ---------------------------------------------------------------------------

CATALOG = os.getenv("UC_CATALOG", "utility_ops")
SCHEMA = os.getenv("UC_SCHEMA", "asset_intelligence")

CLAUDE_ENDPOINT = "databricks-claude-sonnet-4-6"

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
# Agent class
# ---------------------------------------------------------------------------


class MaintenanceAgent(mlflow.pyfunc.ChatAgent):
    """
    Mosaic AI maintenance reasoning agent backed by Claude Sonnet 4.6
    with 6 Unity Catalog function tools.
    """

    def __init__(self):
        from databricks_langchain import ChatDatabricks, UCFunctionToolkit
        from langgraph.prebuilt import create_react_agent

        self.toolkit = UCFunctionToolkit(function_names=TOOL_NAMES)
        self.tools = self.toolkit.tools

        llm = ChatDatabricks(
            endpoint=CLAUDE_ENDPOINT,
            temperature=0.1,
            max_tokens=4096,
        )

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
        lc_messages = [{"role": m.role, "content": m.content} for m in messages]
        result = self.agent.invoke({"messages": lc_messages})
        output = result["messages"][-1].content
        return ChatAgentResponse(
            messages=[ChatAgentMessage(role="assistant", content=output, id=str(uuid.uuid4()))]
        )

    def predict_stream(
        self,
        messages: list[ChatAgentMessage],
        context=None,
        custom_inputs=None,
    ) -> Generator[ChatAgentResponse, None, None]:
        lc_messages = [{"role": m.role, "content": m.content} for m in messages]
        for chunk in self.agent.stream({"messages": lc_messages}):
            if "agent" in chunk:
                content = chunk["agent"]["messages"][-1].content
                if content:
                    yield ChatAgentResponse(
                        messages=[ChatAgentMessage(role="assistant", content=content, id=str(uuid.uuid4()))]
                    )


# ---------------------------------------------------------------------------
# MLflow entry point — called when the model is loaded at serving time
# ---------------------------------------------------------------------------

mlflow.models.set_model(MaintenanceAgent())
