from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import kpi, users  # Add other endpoint modules here as they are created
from app.config.settings import settings
from app.core.database import get_db

# Documentation agent removed; related imports and endpoints have been deleted

# Example: from .endpoints import items, other_resources

api_v1_router = APIRouter()

# Include user routes
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])

# Include KPI routes
api_v1_router.include_router(kpi.router, prefix="/kpi", tags=["KPIs"])

# Include other resource routers here
# api_v1_router.include_router(items.router, prefix="/items", tags=["Items"])
# api_v1_router.include_router(other_resources.router, prefix="/others", tags=["Others"])


"""Doc-approval endpoints removed with documentation agent deletion."""
