"""
Row filter endpoints
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.row_filter import RowFilterRequest, RowFilterResponse
from app.services.row_filter_service import RowFilterService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/row-filter", response_model=RowFilterResponse)
async def get_row_filter(
    request_data: RowFilterRequest,
    request: Request,
):
    """
    Get row filter SQL expression for user on table

    This endpoint is called by OPA to get row filters for Trino queries.

    Example:
        POST /permissions/row-filter
        {
          "user_id": "sale_nam",
          "resource": {
            "catalog_name": "prod",
            "schema_name": "public",
            "table_name": "customers"
          }
        }

    Response:
        {
          "filter_expression": "region IN ('mien_bac')",
          "has_filter": true
        }
    """
    logger.info(
        f"[ENDPOINT] Received row filter request: "
        f"user={request_data.user_id}, resource={request_data.resource}"
    )

    try:
        # Build table FQN
        resource = request_data.resource
        catalog_name = resource.get("catalog_name")
        schema_name = resource.get("schema_name")
        table_name = resource.get("table_name")

        if not all([catalog_name, schema_name, table_name]):
            logger.warning(
                f"Invalid resource specification: {resource}. "
                "Missing catalog_name, schema_name, or table_name"
            )
            # Fail closed - deny all
            return RowFilterResponse(filter_expression="1=0", has_filter=True)

        table_fqn = f"{catalog_name}.{schema_name}.{table_name}"

        # Get OpenFGA manager from app state
        openfga = request.app.state.openfga
        service = RowFilterService(openfga)

        # Build row filter SQL
        filter_sql = await service.build_row_filter_sql(
            request_data.user_id, table_fqn
        )

        has_filter = filter_sql is not None

        logger.info(
            f"[ENDPOINT] Returning row filter: "
            f"user={request_data.user_id}, table={table_fqn}, "
            f"filter={filter_sql}, has_filter={has_filter}"
        )

        return RowFilterResponse(
            filter_expression=filter_sql, has_filter=has_filter
        )

    except Exception as e:
        logger.error(
            f"Error getting row filter: {e}",
            exc_info=True,
        )
        # Fail closed - deny all on error
        return RowFilterResponse(filter_expression="1=0", has_filter=True)
