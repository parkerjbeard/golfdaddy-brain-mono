from fastapi import APIRouter

from app.api import daily_report_endpoints, raci_matrix, zapier_endpoints
from app.api.v1.endpoints import kpi, users

api_v1_router = APIRouter()

# Include user routes
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])

# Include KPI routes
api_v1_router.include_router(kpi.router, prefix="/kpi", tags=["KPIs"])

# Include RACI matrices routes
api_v1_router.include_router(raci_matrix.router)

# Include Zapier dashboard routes
api_v1_router.include_router(zapier_endpoints.router)

# Include Daily Reports routes
api_v1_router.include_router(daily_report_endpoints.router)
