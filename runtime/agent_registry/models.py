from sqlalchemy import Column, Integer, String, Boolean, Float, Text
from sqlalchemy.dialects.postgresql import JSONB
from runtime.core.database import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)
    description = Column(Text)
    allowed_tools = Column(JSONB, default=list)
    required_integrations = Column(JSONB, default=list)
    system_prompt = Column(Text, nullable=False)
    capabilities = Column(JSONB, default=list)
    max_context = Column(Integer, default=8000)
    temperature = Column(Float, default=0.7)
    enabled = Column(Boolean, default=True)
