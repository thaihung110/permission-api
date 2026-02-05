"""
Lakekeeper endpoints - API for listing Lakekeeper resources with permissions
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.lakekeeper import ListResourcesRequest, ListResourcesResponse
from app.services.lakekeeper_service import LakekeeperService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/list-resources",
    response_model=ListResourcesResponse,
    response_model_exclude_none=True,
)
async def list_resources(
    request_data: ListResourcesRequest,
    request: Request,
):
    """
    List all Lakekeeper resources with user permissions for a specific catalog

    Fetches namespaces and tables from Lakekeeper for the specified catalog,
    then checks which permissions [create, modify, select, describe]
    the specified user has on each resource.

    Returns all resources in flat list format.

    **Request:**
    - `user_id`: User ID to check permissions for
    - `catalog`: Trino catalog name (e.g., 'lakekeeper_demo').
                 The 'lakekeeper_' prefix will be removed to get the Lakekeeper warehouse name.

    **Response format:**
    Flat list of resources with:
    - `name`: Resource path (warehouse, warehouse.namespace, warehouse.namespace.table, etc.)
    - `permissions`: Array of permissions
    - `row_filters`: Array of row filter policies (tables only)

    **Example:**
    ```json
    {
      "resources": [
        {"name": "lakekeeper_demo", "permissions": ["select", "describe"]},
        {"name": "lakekeeper_demo.finance", "permissions": ["select", "modify"]},
        {
          "name": "lakekeeper_demo.finance.user",
          "permissions": ["select"],
          "row_filters": [
            {"attribute_name": "region", "filter_expression": "region IN ('north')"}
          ]
        },
        {"name": "lakekeeper_demo.finance.user.id", "permissions": []},
        {"name": "lakekeeper_demo.finance.user.phone_number", "permissions": ["mask"]}
      ],
      "errors": null
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

        # Log summary - count resources by type (based on dots in name)
        total_resources = len(result.resources)
        warehouses = sum(1 for r in result.resources if "." not in r.name)
        namespaces = sum(1 for r in result.resources if r.name.count(".") == 1)
        tables = sum(1 for r in result.resources if r.name.count(".") == 2)
        columns = sum(1 for r in result.resources if r.name.count(".") == 3)

        logger.info(
            f"\n{'='*60}\n"
            f"[ENDPOINT] Request completed successfully\n"
            f"Summary:\n"
            f"  - Total resources: {total_resources}\n"
            f"  - Warehouses: {warehouses}\n"
            f"  - Namespaces: {namespaces}\n"
            f"  - Tables: {tables}\n"
            f"  - Columns: {columns}\n"
            f"  - Errors encountered: {len(result.errors) if result.errors else 0}\n"
            f"{'='*60}"
        )

        # Log detailed response (truncated for large responses)
        if total_resources <= 50:
            logger.debug(f"[ENDPOINT] Response: {result.model_dump()}")
        else:
            logger.debug(
                f"[ENDPOINT] Response contains {total_resources} resources "
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
