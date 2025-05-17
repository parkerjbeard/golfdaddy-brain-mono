from fastapi import APIRouter

from app.api.v1.endpoints import users, kpi  # Add other endpoint modules here as they are created
from app.api import developer_insights_endpoints
# Example: from .endpoints import items, other_resources

api_v1_router = APIRouter()

# Include user routes
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])

# Include KPI routes
api_v1_router.include_router(kpi.router, prefix="/kpi", tags=["KPIs"])

# Developer insights routes
api_v1_router.include_router(
    developer_insights_endpoints.router,
    prefix="/insights",
    tags=["Developer Insights"],
)

# Include other resource routers here
# api_v1_router.include_router(items.router, prefix="/items", tags=["Items"])
# api_v1_router.include_router(other_resources.router, prefix="/others", tags=["Others"]) 