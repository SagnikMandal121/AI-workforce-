from typing import Dict, Any
from runtime.workflow_engine.state import WorkflowState

async def executor_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Executes the current step in the plan.
    """
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    
    if idx >= len(plan):
        return {"final_output": "All steps completed"}
        
    step = plan[idx]
    
    # Check if approval is needed
    if step["status"] == "requires_approval":
        # In a real system, we'd pause here or notify a human
        # For this mock, we assume approved if it reaches here
        step["status"] = "running"
        
    # Execute the tool (mocked)
    step["result"] = f"Executed {step['tool']} with {step['inputs']}"
    step["status"] = "completed"
    
    # Return updated state
    return {"plan": plan, "current_step_index": idx + 1}
