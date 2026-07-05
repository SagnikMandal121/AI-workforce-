from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from pydantic import BaseModel

from runtime.core.database import get_db
from runtime.agent_registry.models import Agent

router = APIRouter(prefix="/agents", tags=["Agent Registry"])

class AgentCreate(BaseModel):
    id: str
    name: str
    role: str
    description: str = ""
    system_prompt: str
    allowed_tools: List[str] = []
    required_integrations: List[str] = []
    capabilities: List[str] = []
    max_context: int = 8000
    temperature: float = 0.7
    enabled: bool = True

class AgentResponse(AgentCreate):
    pass

@router.post("/", response_model=AgentResponse)
async def create_agent(agent: AgentCreate, db: AsyncSession = Depends(get_db)):
    db_agent = Agent(**agent.model_dump())
    db.add(db_agent)
    try:
        await db.commit()
        await db.refresh(db_agent)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Agent ID might already exist")
    return db_agent

@router.get("/", response_model=List[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent))
    return result.scalars().all()

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
