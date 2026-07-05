from typing import TypedDict, List, Dict, Any, Optional
from enum import Enum

class PlanStep(TypedDict):
    id: str
    action: str
    tool: Optional[str]
    inputs: Dict[str, Any]
    status: str # pending, running, completed, failed, requires_approval
    result: Optional[Any]

class WorkflowState(TypedDict):
    task_id: str
    user_input: str
    agent_id: str
    context: List[str] # retrieved knowledge
    memory: List[Dict[str, Any]] # conversation memory
    plan: List[PlanStep]
    current_step_index: int
    final_output: Optional[str]
    errors: List[str]
