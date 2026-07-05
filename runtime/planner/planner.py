import json
import uuid
from typing import Dict, Any

from runtime.workflow_engine.state import WorkflowState, PlanStep

async def planner_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Takes the user input and context, and generates an execution plan.
    (This is a simplified mock implementation. In a real system, this would call an LLM.)
    """
    user_input = state.get("user_input", "")
    
    # In a full implementation, we'd prompt the LLM to generate a JSON array of steps
    # For now, we return a mock plan based on the input
    
    mock_plan = [
        PlanStep(
            id=str(uuid.uuid4()),
            action="Retrieve context",
            tool="KnowledgeSearch",
            inputs={"query": user_input},
            status="pending",
            result=None
        ),
        PlanStep(
            id=str(uuid.uuid4()),
            action="Draft response",
            tool="LLM",
            inputs={"prompt": "Draft a response based on context"},
            status="pending",
            result=None
        ),
        PlanStep(
            id=str(uuid.uuid4()),
            action="Send message",
            tool="Email", # or Slack, etc.
            inputs={"message": "{draft_result}"},
            status="requires_approval", # requires human approval step
            result=None
        )
    ]
    
    return {"plan": mock_plan, "current_step_index": 0}
