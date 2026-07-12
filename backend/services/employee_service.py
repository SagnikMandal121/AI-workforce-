import uuid
from typing import Dict, Any, List
from database.repositories.employee_repository import EmployeeRepository
from database.models.employee import Employee, EmployeePrompt, EmployeeMemorySetting, EmployeeApprovalPolicy

class EmployeeService:
    def __init__(self, repo: EmployeeRepository):
        self.repo = repo

    async def create_employee(self, data: Dict[str, Any]) -> Employee:
        emp_id = str(uuid.uuid4())
        new_emp = Employee(
            id=emp_id,
            name=data.get("name"),
            role=data.get("role"),
            system_prompt=data.get("system_prompt", ""),
        )
        
        # Setup defaults
        new_emp.memory_settings = EmployeeMemorySetting(id=str(uuid.uuid4()), employee_id=emp_id)
        new_emp.approval_policy = EmployeeApprovalPolicy(id=str(uuid.uuid4()), employee_id=emp_id)
        
        return await self.repo.create_employee(new_emp)

    async def clone_employee(self, original_id: str, new_name: str) -> Employee:
        original = await self.repo.get_employee_by_id(original_id)
        if not original:
            raise ValueError("Employee not found")
            
        emp_id = str(uuid.uuid4())
        cloned = Employee(
            id=emp_id,
            name=new_name,
            role=original.role,
            system_prompt=original.system_prompt,
            temperature=original.temperature,
            max_tokens=original.max_tokens,
            model_provider=original.model_provider,
            model_name=original.model_name
        )
        # We would also clone the relationships here (tools, knowledge, memory, policies, prompts)
        return await self.repo.create_employee(cloned)

    async def build_prompt(self, employee_id: str, context: Dict[str, Any]) -> str:
        employee = await self.repo.get_employee_by_id(employee_id)
        if not employee:
            raise ValueError("Employee not found")
            
        base_prompt = employee.system_prompt
        # Process dynamic variables like {company_name} or {user_query}
        for key, value in context.items():
            base_prompt = base_prompt.replace(f"{{{key}}}", str(value))
            
        # Append additional prompt parts (company context, conversation context)
        for prompt_part in employee.prompts:
            base_prompt += f"\n\n{prompt_part.content}"
            
        return base_prompt
