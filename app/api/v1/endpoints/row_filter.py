"""
Row filter endpoints
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.row_filter import (
    RowFilterPolicyGrant,
    RowFilterPolicyGrantResponse,
    RowFilterPolicyListRequest,
    RowFilterPolicyListResponse,
    RowFilterRequest,
    RowFilterResponse,
)
from app.services.row_filter_service import RowFilterService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/query", response_model=RowFilterResponse)
async def get_row_filter(
    request_data: RowFilterRequest,
    request: Request,
):
    """
    Get row filter SQL expression for user on table

    This endpoint is called by OPA to get row filters for Trino queries.

    Example:
        POST /row-filter/query
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


@router.post("/grant", response_model=RowFilterPolicyGrantResponse)
async def grant_row_filter_policy(
    grant: RowFilterPolicyGrant,
    request: Request,
):
    """
    Grant row filter policy to user on a specific table with attribute filter.

    This endpoint grants the 'viewer' relation with condition 'has_attribute_access'
    on a row_filter_policy resource, which defines row-level filtering rules.

    Example:
        POST /row-filter/grant
        {
          "user_id": "sale_nam",
          "resource": {
            "catalog": "lakekeeper_bronze",
            "schema": "finance",
            "table": "user"
          },
          "attribute_name": "region",
          "allowed_values": ["mien_bac"]
        }

    Response:
        {
          "success": true,
          "user_id": "sale_nam",
          "policy_id": "user_region_filter",
          "object_id": "row_filter_policy:user_region_filter",
          "table_fqn": "lakekeeper_bronze.finance.user",
          "attribute_name": "region",
          "relation": "viewer"
        }
    """
    try:
        logger.info(
            f"[ENDPOINT] Received row filter policy grant request: "
            f"user={grant.user_id}, resource={grant.resource.model_dump(exclude_none=True)}, "
            f"attribute={grant.attribute_name}"
        )

        openfga = request.app.state.openfga
        service = RowFilterService(openfga)
        result = await service.grant_row_filter_policy(grant)

        logger.info(
            f"[ENDPOINT] Row filter policy granted: user={grant.user_id}, policy={result.policy_id}"
        )

        return result

    except ValueError as e:
        logger.warning(f"Invalid request for row filter policy grant: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error granting row filter policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to grant row filter policy: {str(e)}",
        )


@router.post("/revoke", response_model=RowFilterPolicyGrantResponse)
async def revoke_row_filter_policy(
    grant: RowFilterPolicyGrant,
    request: Request,
):
    """
    Revoke row filter policy from user on a specific table.

    This endpoint revokes the 'viewer' relation on a row_filter_policy resource
    and removes the table-to-policy link.

    Example:
        POST /row-filter/revoke
        {
          "user_id": "sale_nam",
          "resource": {
            "catalog": "lakekeeper_bronze",
            "schema": "finance",
            "table": "user"
          },
          "attribute_name": "region",
          "allowed_values": []
        }

    Response:
        {
          "success": true,
          "user_id": "sale_nam",
          "policy_id": "user_region_filter",
          "object_id": "row_filter_policy:user_region_filter",
          "table_fqn": "lakekeeper_bronze.finance.user",
          "attribute_name": "region",
          "relation": "viewer"
        }
    """
    try:
        logger.info(
            f"[ENDPOINT] Received row filter policy revoke request: "
            f"user={grant.user_id}, resource={grant.resource.model_dump(exclude_none=True)}, "
            f"attribute={grant.attribute_name}"
        )

        openfga = request.app.state.openfga
        service = RowFilterService(openfga)
        result = await service.revoke_row_filter_policy(grant)

        logger.info(
            f"[ENDPOINT] Row filter policy revoked: user={grant.user_id}, policy={result.policy_id}"
        )

        return result

    except ValueError as e:
        logger.warning(f"Invalid request for row filter policy revoke: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error revoking row filter policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to revoke row filter policy: {str(e)}",
        )


@router.post("/list", response_model=RowFilterPolicyListResponse)
async def list_row_filter_policies(
    request_data: RowFilterPolicyListRequest,
    request: Request,
):
    """
    Get list of row filter policies that user has access to on a specific table.

    This endpoint queries OpenFGA to find all policies with 'viewer' relation
    for the specified user on the specified table.

    Example:
        POST /row-filter/list
        {
          "user_id": "sale_nam",
          "resource": {
            "catalog_name": "lakekeeper_bronze",
            "schema_name": "finance",
            "table_name": "user"
          }
        }

    Response:
        {
          "user_id": "sale_nam",
          "table_fqn": "lakekeeper_bronze.finance.user",
          "policies": [
            {
              "policy_id": "user_region_filter",
              "attribute_name": "region",
              "allowed_values": ["mien_bac"]
            }
          ],
          "count": 1
        }
    """
    table_fqn = ""  # Initialize for exception handling
    try:
        logger.info(
            f"[ENDPOINT] Received row filter policy list request: "
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
        service = RowFilterService(openfga)

        # Get user's policies
        policies = await service.get_user_policies_for_table(
            request_data.user_id, table_fqn
        )

        logger.info(
            f"[ENDPOINT] Returning row filter policies: "
            f"user={request_data.user_id}, table={table_fqn}, "
            f"count={len(policies)}"
        )

        return RowFilterPolicyListResponse(
            user_id=request_data.user_id,
            table_fqn=table_fqn,
            policies=policies,
            count=len(policies),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing row filter policies: {e}", exc_info=True)
        # Return empty list on error (fail gracefully)
        return RowFilterPolicyListResponse(
            user_id=request_data.user_id,
            table_fqn=table_fqn,
            policies=[],
            count=0,
        )
