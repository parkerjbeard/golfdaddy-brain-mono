from app.api.docs_generation import router as docs_router
from app.api.task_endpoints import router as tasks_router

__all__ = ["docs_router", "tasks_router"]