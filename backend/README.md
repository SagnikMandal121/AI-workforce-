# Backend

The backend directory contains all business logic APIs and Services.

**Principles:**
- Handles authentication, organizations, and user management.
- Provides configurations to the `runtime` (like employee setups) via services.
- Never runs agentic execution; that belongs to `runtime`.
- Communicates directly with the `database`.

**Structure:**
- `api/`: FastAPI routes for different domains (e.g. auth, employees, conversations).
- `services/`: Business logic layer.
- `core/`: Core dependencies and configurations.
