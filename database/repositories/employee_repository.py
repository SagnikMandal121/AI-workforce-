from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Optional, List

from database.models.employee import Employee, EmployeeTool, EmployeeKnowledgeBase, EmployeeMemorySetting, EmployeeApprovalPolicy, EmployeePrompt

class EmployeeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_employee_by_id(self, employee_id: str) -> Optional[Employee]:
        stmt = select(Employee).options(
            selectinload(Employee.tools),
            selectinload(Employee.knowledge_bases),
            selectinload(Employee.memory_settings),
            selectinload(Employee.approval_policy),
            selectinload(Employee.prompts)
        ).where(Employee.id == employee_id)
        
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_employees(self) -> List[Employee]:
        stmt = select(Employee)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_employee(self, employee: Employee) -> Employee:
        self.session.add(employee)
        await self.session.commit()
        await self.session.refresh(employee)
        return employee

    async def delete_employee(self, employee_id: str) -> bool:
        employee = await self.get_employee_by_id(employee_id)
        if employee:
            await self.session.delete(employee)
            await self.session.commit()
            return True
        return False
