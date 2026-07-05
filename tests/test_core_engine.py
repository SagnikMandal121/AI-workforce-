import pytest
from fastapi.testclient import TestClient
from runtime.main import app
from runtime.workflow_engine.graph import app_graph
from runtime.workflow_engine.state import WorkflowState

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_langgraph_workflow_mock():
    # Test the basic graph compilation and execution
    initial_state = WorkflowState(
        task_id="task-123",
        user_input="Test execution pipeline",
        agent_id="agent-001",
        context=[],
        memory=[],
        plan=[],
        current_step_index=0,
        final_output=None,
        errors=[]
    )
    
    final_state = await app_graph.ainvoke(initial_state)
    
    # Verify planner was called and generated steps
    assert len(final_state["plan"]) == 3
    # Verify executor ran through the steps
    assert final_state["current_step_index"] == 3
    assert final_state["plan"][2]["status"] == "completed"
    assert final_state["final_output"] == "All steps completed"
