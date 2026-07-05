from langgraph.graph import StateGraph, END
from typing import Literal

from runtime.workflow_engine.state import WorkflowState
from runtime.planner.planner import planner_node
from runtime.executor.executor import executor_node

def should_continue(state: WorkflowState) -> Literal["executor_node", "__end__"]:
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    
    if idx >= len(plan):
        return "__end__"
    return "executor_node"

def build_graph():
    workflow = StateGraph(WorkflowState)
    
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("executor_node", executor_node)
    
    workflow.set_entry_point("planner_node")
    
    workflow.add_conditional_edges(
        "planner_node",
        should_continue,
        {
            "executor_node": "executor_node",
            "__end__": END
        }
    )
    
    workflow.add_conditional_edges(
        "executor_node",
        should_continue,
        {
            "executor_node": "executor_node",
            "__end__": END
        }
    )
    
    return workflow.compile()

app_graph = build_graph()
