from typing import Any, Dict
from runtime.core.redis import get_redis

class EventBus:
    def __init__(self):
        # Initialized externally via Dependency Injection
        self.redis_client = None
        
    async def publish(self, event_type: str, payload: Dict[str, Any]):
        """Publish an event to the Redis event bus."""
        import json
        if not self.redis_client:
            self.redis_client = await get_redis()
            
        await self.redis_client.publish(
            "ai_workforce_events", 
            json.dumps({
                "event": event_type,
                "payload": payload
            })
        )

# Global event bus instance
bus = EventBus()
