"""
Row filter endpoints
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.row_filter import (
    BatchRowFilterInput,
    BatchRowFilterRequest,
    BatchRowFilterResponse,
    RowFilterAction,
    RowFilterContext,
    RowFilterIdentityContext,
    RowFilterPolicyGrant,
    RowFilterPolicyGrantResponse,
    RowFilterPolicyListRequest,
    RowFilterPolicyListResponse,
    RowFilterRequest,
    RowFilterResource,
    RowFilterResponse,
    TableResource,
)
from app.services.row_filter_service import RowFilterService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/query", response_model=BatchRowFilterResponse)
async def get_row_filter(
    request: Request,
):
    """
    Get row filter SQL expression for user on table (Trino integration).

    This endpoint accepts both old format and OPA format, auto-converts to OPA format,
    and returns the SQL filter expression.

    Supports 2 formats:

    1. Old format (auto-converted):
        {
            "user_id": "hung",
            "resource": {
                "catalog_name": "lakekeeper_bronze",
                "schema_name": "finance",
                "table_name": "user"
            }
        }

    2. OPA format:
        {
            "input": {
            "context": {
                "identity": {"user": "hung", "groups": []},
                "softwareStack": {"trinoVersion": "467"}
            },
            "action": {
                "operation": "GetRowFilters",
                "resource": {
                "table": {
                    "catalogName": "lakekeeper_bronze",
                    "schemaName": "finance",
                    "tableName": "user"
                }
                }
            }
            }
        }

    Response:
        {
            "result": [
                {"expression": "region IN ('north')"}
            ]
        }
    """
    try:
        # Read raw request body
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8") if body_bytes else "{}"
        body_dict = json.loads(body_str) if body_str else {}

        logger.info(
            f"[ENDPOINT] Received row filter request:\n"
            f"request_body=\n{json.dumps(body_dict, indent=2)}"
        )

        # Auto-detect format and convert to OPA format
        if "input" in body_dict:
            # Already OPA format
            logger.info("[ENDPOINT] Detected OPA format")
            batch_request = BatchRowFilterRequest(**body_dict)
        else:
            # Old format - convert to OPA format
            logger.info(
                "[ENDPOINT] Detected old format, converting to OPA format"
            )
            user_id = body_dict.get("user_id", "")
            resource = body_dict.get("resource", {})
            catalog_name = resource.get("catalog_name", "")
            schema_name = resource.get("schema_name", "")
            table_name = resource.get("table_name", "")

            if not all([user_id, catalog_name, schema_name, table_name]):
                logger.error(
                    f"[ENDPOINT] Invalid request: missing required fields"
                )
                return BatchRowFilterResponse(result=[])

            # Convert to OPA format
            batch_request = BatchRowFilterRequest(
                input=BatchRowFilterInput(
                    context=RowFilterContext(
                        identity=RowFilterIdentityContext(
                            user=user_id,
                            groups=[],
                        ),
                        softwareStack={},
                    ),
                    action=RowFilterAction(
                        operation="GetRowFilters",
                        resource=RowFilterResource(
                            table=TableResource(
                                catalogName=catalog_name,
                                schemaName=schema_name,
                                tableName=table_name,
                            )
                        ),
                    ),
                )
            )

        # Extract info for logging
        user_id = batch_request.input.context.identity.user
        table_name = batch_request.input.action.resource.table.tableName

        logger.info(
            f"[ENDPOINT] Processing row filter: user={user_id}, table={table_name}"
        )

        openfga = request.app.state.openfga
        service = RowFilterService(openfga)
        result = await service.batch_get_row_filters(batch_request)

        # Log response
        response_body = result.model_dump_json(indent=2)
        logger.info(
            f"[ENDPOINT] Row filter completed:\n"
            f"user={user_id}, table={table_name}, "
            f"has_filter={len(result.result) > 0}\n"
            f"response_body=\n{response_body}"
        )

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {e}", exc_info=True)
        return BatchRowFilterResponse(result=[])
    except Exception as e:
        logger.error(f"Error in row filter check: {e}", exc_info=True)
        return BatchRowFilterResponse(result=[])


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
          "policy_id": "lakekeeper_bronze.finance.user.region",
          "object_id": "row_filter_policy:lakekeeper_bronze.finance.user.region",
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
          "policy_id": "lakekeeper_bronze.finance.user.region",
          "object_id": "row_filter_policy:lakekeeper_bronze.finance.user.region",
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
              "policy_id": "lakekeeper_bronze.finance.user.region",
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
