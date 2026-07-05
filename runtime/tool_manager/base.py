from typing import Any, Dict
from abc import ABC, abstractmethod

class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass
        
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Any:
        """Executes the tool with the given parameters."""
        pass
        
    @abstractmethod
    async def validate(self, params: Dict[str, Any]) -> bool:
        """Validates the input parameters before execution."""
        pass
        
    @abstractmethod
    async def health(self) -> bool:
        """Checks if the tool's external dependencies (if any) are reachable."""
        pass
        
    async def retry(self, params: Dict[str, Any], retries: int = 3) -> Any:
        """Wrapper around execute with simple retry logic."""
        import asyncio
        for attempt in range(retries):
            try:
                return await self.execute(params)
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                await asyncio.sleep(2 ** attempt)
