# Database

The database directory contains all persistence logic and schemas.

**Principles:**
- Isolated from the runtime execution. The `runtime` must never directly access these models.
- Used exclusively by the `backend` services and scripts.
- Multi-tenancy is enforced at this layer for all tenant-specific entities.

**Structure:**
- `models/`: SQLAlchemy ORM models.
- `repositories/`: Data access objects (DAOs) abstraction.
- `schemas/`: Pydantic validation schemas.
- `migrations/`: Alembic migrations.
