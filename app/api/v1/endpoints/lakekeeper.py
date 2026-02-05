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

    Returns all resources in a nested structure: warehouse -> namespaces -> tables -> columns.

    **Request:**
    - `user_id`: User ID to check permissions for
    - `catalog`: Trino catalog name (e.g., 'lakekeeper_demo').
                    The 'lakekeeper_' prefix will be removed to get the Lakekeeper warehouse name.

        **Response format:**
        Nested structure with permissions at each level:
        - Warehouse: contains permissions and map of namespaces
        - Namespace: contains permissions and map of tables
        - Table: contains permissions and list of columns
        - Column: contains name and masked status

        **Example:**
        ```json
        {
        "resources": {
            "lakekeeper_demo": {
            "permissions": ["select", "describe"],
            "namespaces": {
                "finance": {
                "permissions": ["select", "modify"],
                "tables": {
                    "user": {
                    "permissions": ["select"],
                    "columns": [
                        {"name": "id", "masked": false},
                        {"name": "phone_number", "masked": true}
                    ]
                    }
                }
                }
            }
            }
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
        f"Catalog (Trino): {request_data.catalog}\n"
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
        total_warehouses = len(result.resources)
        total_namespaces = sum(
            len(wh.namespaces) if wh.namespaces else 0
            for wh in result.resources.values()
        )
        total_tables = sum(
            len(ns.tables) if ns.tables else 0
            for wh in result.resources.values()
            if wh.namespaces
            for ns in wh.namespaces.values()
        )

        logger.info(
            f"\n{'='*60}\n"
            f"[ENDPOINT] Request completed successfully\n"
            f"Summary:\n"
            f"  - Warehouses: {total_warehouses}\n"
            f"  - Namespaces: {total_namespaces}\n"
            f"  - Tables: {total_tables}\n"
            f"  - Errors encountered: {len(result.errors) if result.errors else 0}\n"
            f"{'='*60}"
        )

        # Log detailed response (truncated for large responses)
        if total_tables <= 20:
            logger.debug(f"[ENDPOINT] Response: {result.model_dump()}")
        else:
            logger.debug(
                f"[ENDPOINT] Response contains {total_tables} tables "
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
