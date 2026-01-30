"""
Lakekeeper endpoints - API for listing Lakekeeper resources with permissions
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.lakekeeper import ListResourcesRequest, ListResourcesResponse
from app.services.lakekeeper_service import LakekeeperService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/list-resources", response_model=ListResourcesResponse)
async def list_resources(
    request_data: ListResourcesRequest,
    request: Request,
):
    """
    List all Lakekeeper resources with user permissions for a specific catalog

    Fetches namespaces and tables from Lakekeeper for the specified catalog,
    then checks which permissions [create, modify, select, describe]
    the specified user has on each resource.

    Returns all resources including those where the user has no permissions
    (indicated by empty permission list).

    **Request:**
    - `user_id`: User ID to check permissions for
    - `catalog`: Warehouse name (catalog name) to list resources for

    **Response format:**
    - Key: resource path
      - Warehouse: `catalog`
      - Namespace: `catalog.namespace_name`
      - Table: `catalog.namespace_name.table_name`
    - Value: list of permissions the user has on that resource

    **Example:**
    ```json
    {
      "resources": {
        "demo": ["select", "describe"],
        "demo.finance": ["select", "modify"],
        "demo.finance.user": ["select"],
        "demo.sales": []
      },
      "errors": []
    }
    ```
    """
    logger.info(
        f"\n{'='*60}\n"
        f"[ENDPOINT] POST /lakekeeper/list-resources\n"
        f"Request body: {request_data.model_dump()}\n"
        f"User ID: {request_data.user_id}\n"
        f"Catalog: {request_data.catalog}\n"
        f"{'='*60}"
    )

    try:
        # Get dependencies from app state
        openfga = request.app.state.openfga
        lakekeeper = request.app.state.lakekeeper

        logger.info("[ENDPOINT] Dependencies retrieved from app.state")
        logger.info(f"  - OpenFGA: {openfga}")
        logger.info(f"  - Lakekeeper: {lakekeeper}")

        # Create service and process request
        logger.info(
            "[ENDPOINT] Creating LakekeeperService and processing request..."
        )
        service = LakekeeperService(openfga, lakekeeper)
        result = await service.list_resources_with_permissions(
            request_data.user_id, request_data.catalog
        )

        # Log summary
        resources_with_permissions = {
            k: v for k, v in result.resources.items() if v
        }
        resources_without_permissions = {
            k: v for k, v in result.resources.items() if not v
        }

        logger.info(
            f"\n{'='*60}\n"
            f"[ENDPOINT] Request completed successfully\n"
            f"Summary:\n"
            f"  - Total resources: {len(result.resources)}\n"
            f"  - Resources with permissions: {len(resources_with_permissions)}\n"
            f"  - Resources without permissions: {len(resources_without_permissions)}\n"
            f"  - Errors encountered: {len(result.errors) if result.errors else 0}\n"
            f"{'='*60}"
        )

        # Log detailed response (truncated for large responses)
        if len(result.resources) <= 50:
            logger.debug(f"[ENDPOINT] Response: {result.model_dump()}")
        else:
            logger.debug(
                f"[ENDPOINT] Response contains {len(result.resources)} resources "
                f"(too large to log in full)"
            )

        return result

    except Exception as e:
        logger.error(
            f"\n{'='*60}\n"
            f"[ENDPOINT] ✗ Request failed\n"
            f"Error: {e}\n"
            f"{'='*60}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list resources: {str(e)}",
        )
