"""
Column mask endpoints
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.column_mask import (
    ColumnMaskGrant,
    ColumnMaskGrantResponse,
    ColumnMaskListRequest,
    ColumnMaskListResponse,
)
from app.services.column_mask_service import ColumnMaskService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/grant", response_model=ColumnMaskGrantResponse)
async def grant_column_mask(
    grant: ColumnMaskGrant,
    request: Request,
):
    """
    Grant column mask permission to user on a specific column.

    This endpoint grants the 'mask' relation on a column resource, which
    indicates that the column should be masked when the user queries the table.

    Example:
        POST /column-mask/grant
        {
          "user_id": "analyst",
          "resource": {
            "catalog": "lakekeeper_bronze",
            "schema": "finance",
            "table": "user",
            "column": "email"
          }
        }

    Response:
        {
          "success": true,
          "user_id": "analyst",
          "column_id": "lakekeeper_bronze.finance.user.email",
          "object_id": "column:lakekeeper_bronze.finance.user.email",
          "relation": "mask"
        }
    """
    try:
        logger.info(
            f"[ENDPOINT] Received column mask grant request: "
            f"user={grant.user_id}, resource={grant.resource.model_dump(exclude_none=True)}"
        )

        openfga = request.app.state.openfga
        service = ColumnMaskService(openfga)
        result = await service.grant_column_mask(grant)

        logger.info(
            f"[ENDPOINT] Column mask granted: user={grant.user_id}, column={result.column_id}"
        )

        return result

    except ValueError as e:
        logger.warning(f"Invalid request for column mask grant: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error granting column mask: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to grant column mask: {str(e)}"
        )


@router.post("/revoke", response_model=ColumnMaskGrantResponse)
async def revoke_column_mask(
    grant: ColumnMaskGrant,
    request: Request,
):
    """
    Revoke column mask permission from user on a specific column.

    This endpoint revokes the 'mask' relation on a column resource.

    Example:
        POST /column-mask/revoke
        {
          "user_id": "analyst",
          "resource": {
            "catalog": "lakekeeper_bronze",
            "schema": "finance",
            "table": "user",
            "column": "email"
          }
        }

    Response:
        {
          "success": true,
          "user_id": "analyst",
          "column_id": "lakekeeper_bronze.finance.user.email",
          "object_id": "column:lakekeeper_bronze.finance.user.email",
          "relation": "mask"
        }
    """
    try:
        logger.info(
            f"[ENDPOINT] Received column mask revoke request: "
            f"user={grant.user_id}, resource={grant.resource.model_dump(exclude_none=True)}"
        )

        openfga = request.app.state.openfga
        service = ColumnMaskService(openfga)
        result = await service.revoke_column_mask(grant)

        logger.info(
            f"[ENDPOINT] Column mask revoked: user={grant.user_id}, column={result.column_id}"
        )

        return result

    except ValueError as e:
        logger.warning(f"Invalid request for column mask revoke: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error revoking column mask: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to revoke column mask: {str(e)}"
        )


@router.post("/list", response_model=ColumnMaskListResponse)
async def list_masked_columns(
    request_data: ColumnMaskListRequest,
    request: Request,
):
    """
    Get list of columns that are masked for a user on a specific table.

    This endpoint queries OpenFGA to find all columns with 'mask' relation
    for the specified user on the specified table.

    Example:
        POST /column-mask/list
        {
          "user_id": "analyst",
          "resource": {
            "catalog_name": "lakekeeper_bronze",
            "schema_name": "finance",
            "table_name": "user"
          }
        }

    Response:
        {
          "user_id": "analyst",
          "table_fqn": "lakekeeper_bronze.finance.user",
          "masked_columns": ["email", "phone_number"],
          "count": 2
        }
    """
    table_fqn = ""  # Initialize for exception handling
    try:
        logger.info(
            f"[ENDPOINT] Received column mask list request: "
            f"user={request_data.user_id}, resource={request_data.resource}"
        )

        # Build table FQN from resource
        resource = request_data.resource
        catalog_name = resource.get("catalog_name") or resource.get("catalog")
        schema_name = resource.get("schema_name") or resource.get("schema")
        table_name = resource.get("table_name") or resource.get("table")

        if not all([catalog_name, schema_name, table_name]):
            logger.warning(
                f"Invalid resource specification: {resource}. "
                "Missing catalog_name, schema_name, or table_name"
            )
            raise HTTPException(
                status_code=400,
                detail="Resource must include catalog_name, schema_name, and table_name",
            )

        table_fqn = f"{catalog_name}.{schema_name}.{table_name}"

        # Get OpenFGA manager from app state
        openfga = request.app.state.openfga
        service = ColumnMaskService(openfga)

        # Get masked columns
        masked_columns = await service.get_masked_columns_for_user(
            request_data.user_id, table_fqn
        )

        logger.info(
            f"[ENDPOINT] Returning masked columns: "
            f"user={request_data.user_id}, table={table_fqn}, "
            f"count={len(masked_columns)}, columns={masked_columns}"
        )

        return ColumnMaskListResponse(
            user_id=request_data.user_id,
            table_fqn=table_fqn,
            masked_columns=masked_columns,
            count=len(masked_columns),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing masked columns: {e}", exc_info=True)
        # Return empty list on error (fail gracefully)
        return ColumnMaskListResponse(
            user_id=request_data.user_id,
            table_fqn=table_fqn,
            masked_columns=[],
            count=0,
        )
