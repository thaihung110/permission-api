"""
Permission management endpoints
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.permission import (
    PermissionCheckRequest,
    PermissionCheckResponse,
    PermissionGrant,
    PermissionGrantResponse,
    PermissionRevoke,
    PermissionRevokeResponse,
)
from app.services.permission_service import PermissionService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/check", response_model=PermissionCheckResponse)
async def check_permission(
    request_data: PermissionCheckRequest,
    request: Request,
):
    """
    Check if user has permission to perform operation on resource

    This endpoint is called by OPA to validate Trino queries.
    """
    logger.info(
        f"[ENDPOINT] Received permission check request: "
        f"user={request_data.user_id}, operation={request_data.operation}, "
        f"resource={request_data.resource}"
    )
    openfga = request.app.state.openfga
    service = PermissionService(openfga)
    result = await service.check_permission(request_data)
    logger.info(
        f"[ENDPOINT] Returning permission check result: allowed={result.allowed}"
    )
    return result


@router.post("/grant", response_model=PermissionGrantResponse)
async def grant_permission(
    grant: PermissionGrant,
    request: Request,
):
    """
    Grant permission to user on resource.

    This endpoint now builds OpenFGA object_id directly from the textual
    identifiers in the request body, without resolving resources in the
    Lakekeeper database.

    Examples:
    - Catalog-level (standalone):
        {"user_id": "alice", "resource": {"catalog": "lakekeeper"}, "relation": "select"}

    - CreateCatalog (relation='create' with empty resource is treated as CreateCatalog):
        {"user_id": "alice", "resource": {"catalog": "lakekeeper"}, "relation": "create"}
        Note: When resource is empty and relation is "create", catalog name is required in resource.

    - Schema-level (requires catalog):
        {"user_id": "alice", "resource": {"catalog": "lakekeeper", "schema": "finance"}, "relation": "select"}

    - Table-level (requires catalog and schema):
    {"user_id": "alice", "resource": {"catalog": "lakekeeper", "schema": "finance", "table": "user"}, "relation": "select"}

    OpenFGA object_id conventions:
    - catalog:<catalog_name>
    - schema:<catalog>.<schema_name> (catalog required)
    - table:<catalog>.<schema_name>.<table_name> (catalog and schema required)
    """
    try:
        openfga = request.app.state.openfga
        service = PermissionService(openfga)
        return await service.grant_permission(grant)
    except ValueError as e:
        logger.warning(f"Invalid permission grant request: {e}")
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error granting permission: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to grant permission: {str(e)}")


@router.post("/revoke", response_model=PermissionRevokeResponse)
async def revoke_permission(
    revoke: PermissionRevoke,
    request: Request,
):
    """
    Revoke permission from user on resource.

    This endpoint mirrors the grant logic and uses the same object_id
    conventions, without resolving resources in the Lakekeeper database.
    """
    try:
        openfga = request.app.state.openfga
        service = PermissionService(openfga)
        return await service.revoke_permission(revoke)
    except ValueError as e:
        logger.warning(f"Invalid permission revoke request: {e}")
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error revoking permission: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to revoke permission: {str(e)}")
