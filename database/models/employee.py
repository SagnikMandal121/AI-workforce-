from sqlalchemy import Column, String, Boolean, Float, Text, ForeignKey, DateTime, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.base import Base

class Employee(Base):
    __tablename__ = "employees"

    id = Column(String, primary_key=True, index=True)
    organization_id = Column(String, index=True)
    name = Column(String, nullable=False)
    avatar = Column(String)
    role = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="active") # active, inactive, testing
    system_prompt = Column(Text)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2000)
    model_provider = Column(String, default="openai")
    model_name = Column(String, default="gpt-4")
    visibility = Column(String, default="private")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tools = relationship("EmployeeTool", back_populates="employee", cascade="all, delete-orphan")
    knowledge_bases = relationship("EmployeeKnowledgeBase", back_populates="employee", cascade="all, delete-orphan")
    memory_settings = relationship("EmployeeMemorySetting", back_populates="employee", uselist=False, cascade="all, delete-orphan")
    approval_policy = relationship("EmployeeApprovalPolicy", back_populates="employee", uselist=False, cascade="all, delete-orphan")
    prompts = relationship("EmployeePrompt", back_populates="employee", cascade="all, delete-orphan")

class EmployeeTool(Base):
    __tablename__ = "employee_tools"
    
    id = Column(String, primary_key=True)
    employee_id = Column(String, ForeignKey("employees.id", ondelete="CASCADE"))
    tool_name = Column(String, nullable=False)
    
    employee = relationship("Employee", back_populates="tools")

class EmployeeKnowledgeBase(Base):
    __tablename__ = "employee_knowledge_bases"
    
    id = Column(String, primary_key=True)
    employee_id = Column(String, ForeignKey("employees.id", ondelete="CASCADE"))
    kb_id = Column(String, nullable=False)
    priority = Column(Integer, default=1)
    
    employee = relationship("Employee", back_populates="knowledge_bases")

class EmployeeMemorySetting(Base):
    __tablename__ = "employee_memory_settings"
    
    id = Column(String, primary_key=True)
    employee_id = Column(String, ForeignKey("employees.id", ondelete="CASCADE"), unique=True)
    short_term = Column(Boolean, default=True)
    long_term = Column(Boolean, default=True)
    conversation = Column(Boolean, default=True)
    retention_days = Column(Integer, default=30)
    compression_enabled = Column(Boolean, default=True)
    
    employee = relationship("Employee", back_populates="memory_settings")

class EmployeeApprovalPolicy(Base):
    __tablename__ = "employee_approval_policies"
    
    id = Column(String, primary_key=True)
    employee_id = Column(String, ForeignKey("employees.id", ondelete="CASCADE"), unique=True)
    policy_type = Column(String, default="threshold") # always, never, threshold, specific_tools
    confidence_threshold = Column(Float, default=0.90)
    escalation_email = Column(String)
    
    employee = relationship("Employee", back_populates="approval_policy")

class EmployeePrompt(Base):
    __tablename__ = "employee_prompts"
    
    id = Column(String, primary_key=True)
    employee_id = Column(String, ForeignKey("employees.id", ondelete="CASCADE"))
    prompt_type = Column(String, nullable=False) # system, company_context, knowledge, conversation
    content = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    
    employee = relationship("Employee", back_populates="prompts")
