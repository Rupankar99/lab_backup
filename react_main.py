import os
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
import httpx

client = httpx.Client(verify=False)

# --- Initialize LLM ---
llm = ChatOpenAI(
    base_url="https://genailab.tcs.in",
    model="azure_ai/genailab-maas-DeepSeek-V3-0324",
    api_key="sk-NDphplabEc8DR-bF5IPRzg",
    http_client=client
)

# --- Define Shared State ---
class AgentState(TypedDict):
    user_query: str
    answer: str

# --- Define Mock Search Tool for ReAct ---
@tool
def mock_search_tool(query: str) -> dict:
    """
    A mock search tool that simulates searching online resources.
    """
    print(f"--- Mock Search Tool Called with query: {query} ---")
    return {"query": query, "result": f"Top result for '{query}'"}

# --- Define Math Agent ---
def math_agent(state: AgentState) -> AgentState:
    print("--- Math Node ---")
    prompt = f"Solve this math problem and return only the answer: {state['user_query']}"
    response = llm.invoke(prompt)
    state['answer'] = response.content.strip()
    return state

# --- Define Search Agent as ReAct ---
def search_agent(state: AgentState) -> AgentState:
    print("--- Search Node (ReAct Agent) ---")
    agent = create_react_agent(llm, [mock_search_tool])
    result = agent.invoke({"messages": state["user_query"]})
    # Extract final message content
    state['answer'] = result["messages"][-1].content
    return state

# --- Define Router Agent ---
def router_agent(state: AgentState) -> AgentState:
    print("--- Router Node ---")
    state['user_query'] = input("Input user query: ")
    return state

# --- Define Agents DocString ---
agent_docs = {
    "search_agent": search_agent.__doc__,
    "math_agent": math_agent.__doc__
}

# --- Define Routing Logic ---
def routing_logic(state: AgentState) -> Literal["math_agent", "search_agent"]:
    prompt = f"""
    You are a router agent. Your task is to choose the best agent for the job.
    Here is the user query: {state['user_query']}

    You can choose from the following agents:
    - math_agent: {agent_docs['math_agent']}
    - search_agent: {agent_docs['search_agent']}

    Which agent should handle this query? Respond with just the agent name.
    """
    response = llm.invoke(prompt)
    decision = response.content.strip().lower()
    return "math_agent" if "math" in decision else "search_agent"

# --- Build the Graph ---
workflow = StateGraph(AgentState)
workflow.add_node("router_agent", router_agent)
workflow.add_node("search_agent", search_agent)
workflow.add_node("math_agent", math_agent)

workflow.add_edge(START, "router_agent")
workflow.add_conditional_edges("router_agent", routing_logic)
workflow.add_edge("search_agent", END)
workflow.add_edge("math_agent", END)

app = workflow.compile()

# --- Run the App ---
if __name__ == "__main__":
    final_state = app.invoke({})
    print("\n--- FINAL ANSWER ---")
    print(final_state["answer"])
    print(final_state)
