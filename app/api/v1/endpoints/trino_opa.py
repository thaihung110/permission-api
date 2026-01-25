"""
Trino OPA compatible endpoints

These endpoints mimic the OPA API that Trino expects for access control.
This allows our permission API to act as a drop-in replacement for OPA.

Trino configuration:
    access-control.name=opa
    opa.policy.uri=http://permission-api:8000/api/v1/allow
    opa.policy.batched-uri=http://permission-api:8000/api/v1/batch
"""

import logging
from typing import List

from fastapi import APIRouter, Request

from app.schemas.permission import PermissionCheckRequest
from app.schemas.trino_opa import (
    TrinoBatchRequest,
    TrinoBatchResponse,
    TrinoOpaRequest,
    TrinoOpaResponse,
    extract_resource_from_batch_item,
    extract_resource_from_trino,
)
from app.services.permission_service import PermissionService

router = APIRouter()
logger = logging.getLogger(__name__)


# Operations that should always be allowed (system/session operations)
ALWAYS_ALLOW_OPERATIONS = {
    "ExecuteQuery",
    "ExecuteTableProcedure",
    "ReadSystemInformation",
    "WriteSystemInformation",
    "SetCatalogSessionProperty",
    "SetSystemSessionProperty",
    "ImpersonateUser",
    "ViewQueryOwnedBy",
    "KillQueryOwnedBy",
    "ExecuteFunction",
}

# Operations that can be checked without resources
NO_RESOURCE_OPERATIONS = {
    "ExecuteQuery",
    "ReadSystemInformation",
    "WriteSystemInformation",
}


@router.post("/allow", response_model=TrinoOpaResponse)
async def trino_allow(
    request_data: TrinoOpaRequest,
    request: Request,
):
    """
    Single permission check endpoint for Trino.

    This endpoint mimics OPA's `/v1/data/trino/allow` endpoint.
    Trino sends authorization requests here and expects a {"result": true/false} response.

    Example request body:
    {
        "input": {
            "context": {
                "identity": {"user": "alice", "groups": []},
                "softwareStack": {"trinoVersion": "476"}
            },
            "action": {
                "operation": "SelectFromColumns",
                "resource": {
                    "table": {
                        "catalogName": "lakekeeper",
                        "schemaName": "finance",
                        "tableName": "user",
                        "columns": ["id", "name"]
                    }
                }
            }
        }
    }
    """
    import json

    operation = request_data.input.action.operation
    user_id = request_data.input.context.identity.user

    # Pretty log the request
    request_dict = request_data.model_dump(mode="json", exclude_none=True)
    logger.info(
        f"\n{'='*60}\n"
        f"[ALLOW] REQUEST\n"
        f"{'='*60}\n"
        f"User: {user_id}\n"
        f"Operation: {operation}\n"
        f"Full Request:\n{json.dumps(request_dict, indent=2)}\n"
        f"{'='*60}"
    )

    # Always allow certain operations
    if operation in ALWAYS_ALLOW_OPERATIONS:
        response = TrinoOpaResponse(result=True)
        logger.info(
            f"\n{'='*60}\n"
            f"[ALLOW] RESPONSE (always allowed)\n"
            f"{'='*60}\n"
            f"Operation: {operation}\n"
            f"Result: {response.result}\n"
            f"{'='*60}"
        )
        return response

    try:
        # Extract resource from Trino format
        resource = extract_resource_from_trino(
            request_data.input.action.resource
        )

        logger.debug(
            f"[ALLOW] Extracted resource: {resource} for operation {operation}"
        )

        # Convert to internal format
        internal_request = PermissionCheckRequest(
            user_id=user_id,
            operation=operation,
            resource=resource,
        )

        # Call permission service
        openfga = request.app.state.openfga
        service = PermissionService(openfga)
        result = await service.check_permission(internal_request)

        response = TrinoOpaResponse(result=result.allowed)

        # Pretty log the response
        logger.info(
            f"\n{'='*60}\n"
            f"[ALLOW] RESPONSE\n"
            f"{'='*60}\n"
            f"User: {user_id}\n"
            f"Operation: {operation}\n"
            f"Resource: {resource}\n"
            f"Result: {response.result}\n"
            f"{'='*60}"
        )

        return response

    except Exception as e:
        logger.error(
            f"\n{'='*60}\n"
            f"[ALLOW] ERROR\n"
            f"{'='*60}\n"
            f"User: {user_id}\n"
            f"Operation: {operation}\n"
            f"Error: {e}\n"
            f"{'='*60}",
            exc_info=True,
        )
        # Fail closed - deny on error
        return TrinoOpaResponse(result=False)


@router.post("/batch", response_model=TrinoBatchResponse)
async def trino_batch(
    request: Request,
):
    """
    Batch permission check endpoint for Trino.

    This endpoint mimics OPA's `/v1/data/trino/batch` endpoint.
    Used for FilterCatalogs, FilterSchemas, FilterTables, FilterColumns operations.

    Returns a list of indices of resources that are allowed.

    Example request body:
    {
        "input": {
            "context": {
                "identity": {"user": "alice", "groups": []},
                "softwareStack": {"trinoVersion": "476"}
            },
            "action": {
                "operation": "FilterCatalogs",
                "filterResources": [
                    {"resource": {"catalog": {"name": "lakekeeper"}}},
                    {"resource": {"catalog": {"name": "system"}}},
                    {"resource": {"catalog": {"name": "private_catalog"}}}
                ]
            }
        }
    }

    Example response:
    {"result": [0, 1]}  // indices 0 and 1 are allowed, 2 is denied
    """
    import json

    # Read raw request body for logging
    try:
        raw_body = await request.body()
        raw_json = raw_body.decode("utf-8")
        body_dict = json.loads(raw_json)
    except Exception as e:
        logger.error(
            f"\n{'='*60}\n"
            f"[BATCH] ERROR - Failed to read/parse request\n"
            f"{'='*60}\n"
            f"Error: {e}\n"
            f"{'='*60}"
        )
        return TrinoBatchResponse(result=[])

    # Pretty log the request
    logger.info(
        f"\n{'='*60}\n"
        f"[BATCH] REQUEST\n"
        f"{'='*60}\n"
        f"{json.dumps(body_dict, indent=2)}\n"
        f"{'='*60}"
    )

    # Try to validate with Pydantic
    try:
        request_data = TrinoBatchRequest(**body_dict)
    except Exception as e:
        logger.error(
            f"\n{'='*60}\n"
            f"[BATCH] ERROR - Pydantic validation failed\n"
            f"{'='*60}\n"
            f"Error: {e}\n"
            f"Body: {raw_json[:1000]}\n"
            f"{'='*60}"
        )
        return TrinoBatchResponse(result=[])

    operation = request_data.input.action.operation
    user_id = request_data.input.context.identity.user
    filter_resources = request_data.input.action.filterResources

    logger.info(
        f"[BATCH] Processing: user={user_id}, operation={operation}, "
        f"resources_count={len(filter_resources)}"
    )

    allowed_indices: List[int] = []
    check_details = []  # Track details for logging

    try:
        openfga = request.app.state.openfga
        service = PermissionService(openfga)

        # Map batch operation to individual operation
        individual_operation = _map_filter_operation(operation)

        for index, item in enumerate(filter_resources):
            try:
                # Extract resource from the filter item (resources are at root level)
                resource = extract_resource_from_batch_item(item)
                item_operation = individual_operation

                # Convert to internal format
                internal_request = PermissionCheckRequest(
                    user_id=user_id,
                    operation=item_operation,
                    resource=resource,
                )

                # Check permission
                result = await service.check_permission(internal_request)

                if result.allowed:
                    allowed_indices.append(index)
                    check_details.append(f"  [{index}] {resource} -> ALLOWED")
                else:
                    check_details.append(f"  [{index}] {resource} -> DENIED")

            except Exception as e:
                check_details.append(f"  [{index}] ERROR: {e}")
                continue

        response = TrinoBatchResponse(result=allowed_indices)

        # Pretty log the response
        logger.info(
            f"\n{'='*60}\n"
            f"[BATCH] RESPONSE\n"
            f"{'='*60}\n"
            f"User: {user_id}\n"
            f"Operation: {operation} -> {individual_operation}\n"
            f"Results ({len(allowed_indices)}/{len(filter_resources)} allowed):\n"
            + "\n".join(check_details)
            + "\n"
            f"Response: {json.dumps(response.model_dump(), indent=2)}\n"
            f"{'='*60}"
        )

        return response

    except Exception as e:
        logger.error(
            f"\n{'='*60}\n"
            f"[BATCH] ERROR\n"
            f"{'='*60}\n"
            f"User: {user_id}\n"
            f"Operation: {operation}\n"
            f"Error: {e}\n"
            f"{'='*60}",
            exc_info=True,
        )
        return TrinoBatchResponse(result=[])


def _map_filter_operation(batch_operation: str) -> str:
    """
    Map batch filter operation to individual operation.

    Batch operations are used for filtering lists of resources.
    Each has a corresponding individual check operation.
    """
    mapping = {
        "FilterCatalogs": "AccessCatalog",
        "FilterSchemas": "ShowSchemas",
        "FilterTables": "ShowTables",
        "FilterColumns": "ShowColumns",
        "FilterViewQueryOwnedBy": "ViewQueryOwnedBy",
    }
    return mapping.get(batch_operation, batch_operation)
