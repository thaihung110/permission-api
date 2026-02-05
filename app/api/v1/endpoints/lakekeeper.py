"""
Lakekeeper endpoints - API for listing Lakekeeper resources with permissions
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas.lakekeeper import ListResourcesResponse
from app.services.lakekeeper_service import LakekeeperService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/list-resources", response_model=ListResourcesResponse)
async def list_resources(
    request: Request,
    user_id: str = Query(..., description="User ID to check permissions for"),
    catalog: str = Query(
        ...,
        description="Trino catalog name (e.g., 'lakekeeper_demo'). The 'lakekeeper_' prefix will be removed to get the Lakekeeper warehouse name.",
    ),
):
    """
    List all Lakekeeper resources with user permissions for a specific catalog

    Fetches namespaces and tables from Lakekeeper for the specified catalog,
    then checks which permissions [create, modify, select, describe]
    the specified user has on each resource.

    Returns warehouse with nested namespaces and tables.

    **Query Parameters:**
    - `user_id`: User ID to check permissions for
    - `catalog`: Trino catalog name (e.g., 'lakekeeper_demo')

    **Response format:**
    ```json
    {
      "name": "lakekeeper_demo",
      "permissions": ["select", "describe"],
      "namespaces": [
        {
          "name": "finance",
          "permissions": ["select", "modify"],
          "tables": [
            {
              "name": "user",
              "permissions": ["select"],
              "columns": [
                {"name": "id", "masked": false},
                {"name": "phone_number", "masked": true}
              ],
              "row_filters": [
                {
                  "attribute_name": "region",
                  "filter_expression": "region IN ('north', 'south')"
                }
              ]
            }
          ]
        }
      ],
      "errors": []
    }
    ```
    """
    logger.info(
        f"\n{'='*60}\n"
        f"[ENDPOINT] GET /lakekeeper/list-resources\n"
        f"User ID: {user_id}\n"
        f"Catalog (Trino): {catalog}\n"
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
        result = await service.list_resources_with_permissions(user_id, catalog)

        # Log summary
        total_namespaces = len(result.namespaces) if result.namespaces else 0
        total_tables = sum(
            len(ns.tables) if ns.tables else 0
            for ns in (result.namespaces or [])
        )

        logger.info(
            f"\n{'='*60}\n"
            f"[ENDPOINT] Request completed successfully\n"
            f"Summary:\n"
            f"  - Warehouse: {result.name}\n"
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
