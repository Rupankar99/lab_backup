"""
LangGraph Multi-Agent System with MCP Server Integration
Fully fixed version: no recursion loops, deterministic routing
"""

import json
from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
import httpx

client = httpx.Client(verify=False)

# ============================================================================
# Configuration
# ============================================================================

CONFIG = {
    "tools": [
        {
            "name": "jira",
            "description": "Manages Jira tickets, issues, and project workflows",
            "mcp_server": "jira-mcp-server",
            "capabilities": [
                "create_issue",
                "update_issue",
                "search_issues",
                "get_issue_details",
                "add_comment"
            ]
        },
        {
            "name": "slack",
            "description": "Sends messages and manages Slack communications",
            "mcp_server": "slack-mcp-server",
            "capabilities": [
                "send_message",
                "get_channel_history",
                "create_channel",
                "list_channels"
            ]
        },
        {
            "name": "github",
            "description": "Manages GitHub repositories, issues, and PRs",
            "mcp_server": "github-mcp-server",
            "capabilities": [
                "create_issue",
                "list_prs",
                "create_pr",
                "get_repo_info"
            ]
        }
    ]
}

# ============================================================================
# State Definition
# ============================================================================

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_agent: str
    user_request: str
    analysis_complete: bool
    tool_results: dict
    final_response: str
    agents_to_execute: list
    agent_tasks: dict
    agents_executed: list

# ============================================================================
# MCP Mock
# ============================================================================

class MCPClient:
    def __init__(self, name: str):
        self.name = name

    async def call_tool(self, tool_name: str, params: dict):
        print(f"[MCP] {self.name} running {tool_name} with params {params}")

        if "jira" in self.name:
            return {"key": "PROJ-123", "status": "created"}
        if "slack" in self.name:
            return {"status": "sent", "channel": params.get("channel")}
        if "github" in self.name:
            return {"issue_number": 22}

        return {"status": "ok"}

# ============================================================================
# Tool Agent
# ============================================================================

class ToolAgent:
    def __init__(self, config: dict):
        self.name = config["name"]
        self.capabilities = config["capabilities"]
        self.llm = ChatOpenAI(
            base_url="https://genailab.tcs.in",
            model="azure_ai/genailab-maas-DeepSeek-V3-0324",
            api_key="sk-",
            http_client=client
        )
        self.mcp = MCPClient(self.name)

    async def execute(self, state: AgentState) -> AgentState:
        task = state["agent_tasks"][self.name]

        system_prompt = f"""
You are a {self.name} agent.  
Capabilities: {', '.join(self.capabilities)}  
Respond ONLY with JSON:
{{
  "tool": "...",
  "params": {{ ... }}
}}
"""

        response = self.llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ])

        content = response.content.strip()
        if content.startswith("```"):
            content = content[content.find("{"): content.rfind("}") + 1]

        tool_req = json.loads(content)
        result = await self.mcp.call_tool(tool_req["tool"], tool_req["params"])

        # Save result
        state["tool_results"][self.name] = result

        # Mark executed
        state["agents_executed"].append(self.name)

        # Continue routing
        state["next_agent"] = "analysis"

        state["messages"].append(AIMessage(content=f"[{self.name}] completed: {json.dumps(result)}"))
        return state

# ============================================================================
# Analysis Agent (runs ONCE)
# ============================================================================

class AnalysisAgent:
    def __init__(self, tool_configs):
        self.tool_configs = tool_configs
        self.llm = ChatOpenAI(
            base_url="https://genailab.tcs.in",
            model="azure_ai/genailab-maas-DeepSeek-V3-0324",
            api_key="sk-NDphplabEc8DR-bF5IPRzg",
            http_client=client
        )

    async def execute(self, state: AgentState) -> AgentState:
        if state["analysis_complete"]:
            # Determine next tool or finish
            remaining = [a for a in state["agents_to_execute"] if a not in state["agents_executed"]]
            if not remaining:
                # NO MORE tools → END
                state["final_response"] = "All tasks completed successfully."
                state["next_agent"] = "end"
                state["messages"].append(AIMessage(content=state["final_response"]))
            else:
                # Next tool
                state["next_agent"] = remaining[0]
                state["messages"].append(HumanMessage(content=state["agent_tasks"][remaining[0]]))
            return state

        # INITIAL ANALYSIS (runs once)
        system_prompt = f"""
You are an analysis agent coordinating multiple tools.
Respond ONLY in JSON:
{{
  "agents_needed": [...],
  "tasks": {{
     "jira": "...",
     "slack": "...",
     "github": "..."
  }},
  "reasoning": "..."
}}
"""

        response = self.llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["user_request"]}
        ])

        content = response.content.strip()
        if content.startswith("```"):
            content = content[content.find("{"): content.rfind("}") + 1]

        analysis = json.loads(content)

        # Initialize execution plan
        state["agents_to_execute"] = analysis["agents_needed"]
        state["agent_tasks"] = analysis["tasks"]
        state["agents_executed"] = []
        state["analysis_complete"] = True

        state["messages"].append(AIMessage(content=f"[Analysis] Agents: {analysis['agents_needed']}"))

        # Route to first agent
        first_agent = analysis["agents_needed"][0]
        state["next_agent"] = first_agent
        state["messages"].append(HumanMessage(content=analysis["tasks"][first_agent]))

        return state

# ============================================================================
# Graph Construction
# ============================================================================

def create_graph():
    analysis = AnalysisAgent(CONFIG["tools"])
    tools = {cfg["name"]: ToolAgent(cfg) for cfg in CONFIG["tools"]}

    g = StateGraph(AgentState)

    g.add_node("analysis", analysis.execute)

    for name, agent in tools.items():
        g.add_node(name, agent.execute)
        g.add_edge(name, "analysis")

    def router(state: AgentState):
        nxt = state["next_agent"]
        return nxt if nxt != "end" else END

    g.add_conditional_edges(
        "analysis",
        router,
        {name: name for name in tools.keys()} | {END: END}
    )

    g.set_entry_point("analysis")
    return g.compile()

# ============================================================================
# USAGE
# ============================================================================

async def main():
    graph = create_graph()

    user_request = "Create a Jira ticket, then notify Slack channel #dev-team."
    state = {
        "messages": [HumanMessage(content=user_request)],
        "next_agent": "analysis",
        "user_request": user_request,
        "analysis_complete": False,
        "tool_results": {},
        "final_response": "",
        "agents_to_execute": [],
        "agent_tasks": {},
        "agents_executed": []
    }

    result = await graph.ainvoke(state)

    print("\nFinal:", result["final_response"])
    print("Tool Results:", json.dumps(result["tool_results"], indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
