from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from database.base import get_db
from database.repositories.employee_repository import EmployeeRepository
from backend.services.employee_service import EmployeeService

router = APIRouter(prefix="/employees", tags=["Employee Management"])

def get_employee_service(db: AsyncSession = Depends(get_db)) -> EmployeeService:
    repo = EmployeeRepository(db)
    return EmployeeService(repo)

@router.post("/")
async def create_employee(data: Dict[str, Any], service: EmployeeService = Depends(get_employee_service)):
    return await service.create_employee(data)

@router.get("/{employee_id}")
async def get_employee(employee_id: str, service: EmployeeService = Depends(get_employee_service)):
    emp = await service.repo.get_employee_by_id(employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp

@router.delete("/{employee_id}")
async def delete_employee(employee_id: str, service: EmployeeService = Depends(get_employee_service)):
    success = await service.repo.delete_employee(employee_id)
    if not success:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"status": "deleted"}

@router.post("/{employee_id}/clone")
async def clone_employee(employee_id: str, new_name: str, service: EmployeeService = Depends(get_employee_service)):
    try:
        return await service.clone_employee(employee_id, new_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{employee_id}/prompt-preview")
async def preview_prompt(employee_id: str, context: Dict[str, Any], service: EmployeeService = Depends(get_employee_service)):
    try:
        prompt = await service.build_prompt(employee_id, context)
        return {"prompt": prompt}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
