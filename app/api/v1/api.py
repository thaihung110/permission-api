"""
API Router - Combines all v1 endpoints
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    column_mask,
    health,
    lakekeeper,
    permissions,
    row_filter,
    trino_opa,
)

api_router = APIRouter()

# Include health endpoint without prefix (at root level)
api_router.include_router(health.router, tags=["Health"])

# Include permission endpoints with /permissions prefix
api_router.include_router(
    permissions.router, prefix="/permissions", tags=["Permissions"]
)

# Include row filter endpoints with /row-filter prefix
api_router.include_router(
    row_filter.router, prefix="/row-filter", tags=["Row Filter Policies"]
)

# Include column mask endpoints with /column-mask prefix
api_router.include_router(
    column_mask.router, prefix="/column-mask", tags=["Column Masks"]
)

# Include Lakekeeper endpoints with /lakekeeper prefix
api_router.include_router(
    lakekeeper.router, prefix="/lakekeeper", tags=["Lakekeeper Resources"]
)

# Include Trino OPA compatible endpoints at root level
# These endpoints mimic OPA's API format for Trino access control
# Full path: /api/v1/allow and /api/v1/batch
api_router.include_router(trino_opa.router, tags=["Trino OPA Compatible"])
