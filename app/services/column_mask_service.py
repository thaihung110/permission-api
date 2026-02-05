"""
Column mask service - Business logic for column masking operations
"""

import logging
from typing import List, Optional

from app.external.openfga_client import OpenFGAManager
from app.schemas.column_mask import (
    BatchColumnMaskRequest,
    BatchColumnMaskResponse,
    ColumnMaskGrant,
    ColumnMaskGrantResponse,
    MaskEntry,
    ViewExpression,
)
from app.schemas.permission import ResourceSpec
from app.utils.operation_mapper import (
    build_user_identifier,
    build_user_identifier_with_type,
)
from app.utils.resource_builder import (
    build_fga_resource_identifiers,
    build_resource_identifiers,
)

logger = logging.getLogger(__name__)


class ColumnMaskService:
    """Service for handling column mask operations"""

    def __init__(self, openfga: OpenFGAManager):
        """
        Initialize column mask service

        Args:
            openfga: OpenFGA manager instance
        """
        self.openfga = openfga

    async def grant_column_mask(
        self, grant: ColumnMaskGrant
    ) -> ColumnMaskGrantResponse:
        """
        Grant column mask permission to user

        Args:
            grant: Column mask grant request

        Returns:
            Column mask grant response

        Raises:
            ValueError: If resource specification is invalid
        """
        logger.info(
            f"Granting column mask: user={grant.user_id}, "
            f"resource={grant.resource.model_dump(exclude_none=True)}"
        )

        # Validate resource has column
        if not grant.resource.column:
            raise ValueError(
                "Column mask grant requires column in resource. "
                'Example: {"catalog": "lakekeeper", "schema": "finance", "table": "user", "column": "email"}'
            )

        # Build column object_id using resource_builder
        # Use "mask" as the relation to ensure correct column-level identifier
        # Note: Column type is unchanged in FGA v3, but we use build_fga_resource_identifiers for consistency
        result = build_fga_resource_identifiers(
            grant.resource, "mask", raise_on_error=True
        )

        if not result:
            raise ValueError(
                "Unable to build column identifier from resource. "
                "Ensure catalog, schema, table, and column are provided."
            )

        object_id, resource_type, resource_id = result

        # Verify it's a column resource
        if resource_type != "column":
            raise ValueError(
                f"Expected column resource, got {resource_type}. "
                "Column mask requires column-level resource."
            )

        # Build user identifier based on user_type
        user = build_user_identifier_with_type(
            grant.user_id, grant.user_type.value
        )

        # Grant mask permission in OpenFGA
        await self.openfga.grant_permission(user, "mask", object_id)

        logger.info(
            f"Column mask granted: user={user}, object={object_id}, column={grant.resource.column}"
        )

        return ColumnMaskGrantResponse(
            success=True,
            user_id=grant.user_id,
            column_id=resource_id,
            object_id=object_id,
            relation="mask",
        )

    async def revoke_column_mask(
        self, grant: ColumnMaskGrant
    ) -> ColumnMaskGrantResponse:
        """
        Revoke column mask permission from user

        Args:
            grant: Column mask revoke request (reuses ColumnMaskGrant schema)

        Returns:
            Column mask revoke response

        Raises:
            ValueError: If resource specification is invalid
        """
        logger.info(
            f"Revoking column mask: user={grant.user_id}, "
            f"resource={grant.resource.model_dump(exclude_none=True)}"
        )

        # Validate resource has column
        if not grant.resource.column:
            raise ValueError(
                "Column mask revoke requires column in resource. "
                'Example: {"catalog": "lakekeeper", "schema": "finance", "table": "user", "column": "email"}'
            )

        # Build column object_id using resource_builder
        # Note: Column type is unchanged in FGA v3, but we use build_fga_resource_identifiers for consistency
        result = build_fga_resource_identifiers(
            grant.resource, "mask", raise_on_error=True
        )

        if not result:
            raise ValueError(
                "Unable to build column identifier from resource. "
                "Ensure catalog, schema, table, and column are provided."
            )

        object_id, resource_type, resource_id = result

        # Verify it's a column resource
        if resource_type != "column":
            raise ValueError(
                f"Expected column resource, got {resource_type}. "
                "Column mask requires column-level resource."
            )

        # Build user identifier based on user_type
        user = build_user_identifier_with_type(
            grant.user_id, grant.user_type.value
        )

        # Revoke mask permission in OpenFGA
        await self.openfga.revoke_permission(user, "mask", object_id)

        logger.info(
            f"Column mask revoked: user={user}, object={object_id}, column={grant.resource.column}"
        )

        return ColumnMaskGrantResponse(
            success=True,
            user_id=grant.user_id,
            column_id=resource_id,
            object_id=object_id,
            relation="mask",
        )

    async def get_masked_columns_for_user(
        self, user_id: str, table_fqn: str, tenant_id: Optional[str] = None
    ) -> List[str]:
        """
        Get list of column names that are masked for a user on a specific table

        This method checks:
        1. Direct user permissions: user -> mask -> column
        2. Tenant-based permissions: tenant#member -> mask -> column (if tenant_id is provided)

        Args:
            user_id: User identifier
            table_fqn: Fully qualified table name (format: catalog.schema.table)
            tenant_id: Optional tenant identifier

        Returns:
            List of column names that are masked
        """
        logger.info(
            f"Getting masked columns for user={user_id}, table={table_fqn}, tenant={tenant_id}"
        )

        try:
            # Build user identifier
            user = build_user_identifier(user_id)

            # Query all mask tuples for this user
            # object_id=None means get all tuples matching user and relation
            tuples = await self.openfga.read_tuples(
                user=user, relation="mask", object_id=None
            )

            # Build table prefix to filter columns
            # Format: column:catalog.schema.table.
            table_prefix = f"column:{table_fqn}."

            masked_columns = []
            for tuple_item in tuples:
                # OpenFGA SDK: object is in tuple_item.key.object
                tuple_key = getattr(tuple_item, "key", None)
                if not tuple_key:
                    continue

                object_id = getattr(tuple_key, "object", "")
                if not object_id:
                    continue

                # Filter: only columns from this table
                if object_id.startswith(table_prefix):
                    # Extract column name from object_id
                    # Format: column:catalog.schema.table.column
                    # We want just the column name (last part after last dot)
                    column_name = object_id.split(".")[-1]
                    if column_name and column_name not in masked_columns:
                        masked_columns.append(column_name)
                        logger.debug(
                            f"Found masked column: {column_name} for user={user_id}, table={table_fqn}"
                        )

            # If tenant_id is provided, also check tenant-based masks
            if tenant_id:
                is_member = await self.openfga.check_tenant_membership(
                    user_id, tenant_id
                )
                if is_member:
                    logger.debug(
                        f"User {user_id} is member of tenant {tenant_id}, checking tenant-based masks"
                    )
                    # Query tenant#member mask tuples
                    tenant_user = f"tenant:{tenant_id}#member"
                    tenant_tuples = await self.openfga.read_tuples(
                        user=tenant_user, relation="mask", object_id=None
                    )

                    for tuple_item in tenant_tuples:
                        tuple_key = getattr(tuple_item, "key", None)
                        if not tuple_key:
                            continue

                        object_id = getattr(tuple_key, "object", "")
                        if not object_id:
                            continue

                        # Filter: only columns from this table
                        if object_id.startswith(table_prefix):
                            column_name = object_id.split(".")[-1]
                            if (
                                column_name
                                and column_name not in masked_columns
                            ):
                                masked_columns.append(column_name)
                                logger.debug(
                                    f"Found tenant-based masked column: {column_name} for tenant={tenant_id}, table={table_fqn}"
                                )
                else:
                    logger.warning(
                        f"User {user_id} is NOT a member of tenant {tenant_id}, skipping tenant masks"
                    )

            logger.info(
                f"Found {len(masked_columns)} masked columns for user={user_id}, table={table_fqn}: {masked_columns}"
            )

            return masked_columns

        except Exception as e:
            logger.error(
                f"Error getting masked columns for user={user_id}, table={table_fqn}: {e}",
                exc_info=True,
            )
            # Return empty list on error (fail gracefully)
            return []

    async def batch_check_column_masks(
        self, request: BatchColumnMaskRequest
    ) -> BatchColumnMaskResponse:
        """
        Batch check which columns need masking for a user.

        This method processes multiple columns in a single request and returns
        which columns need masking with their viewExpression.

        Args:
            request: Batch column mask request from Trino

        Returns:
            Batch column mask response with mask entries for columns that need masking
        """
        logger.info(
            f"Batch checking column masks: user={request.input.context.identity.user}, "
            f"columns={len(request.input.action.filterResources)}"
        )

        try:
            # Extract user_id and groups (tenants) from context
            user_id = request.input.context.identity.user
            groups = request.input.context.identity.groups  # List of tenant IDs
            user = build_user_identifier(user_id)

            logger.info(
                f"Batch checking column masks: user={user_id}, "
                f"columns={len(request.input.action.filterResources)}, "
                f"tenants(groups)={groups}"
            )

            # CRITICAL: Verify user is member of at least one tenant in groups
            # Reject if groups is empty - user must belong to at least one tenant
            if not groups:
                logger.warning(
                    f"Access denied: User {user_id} has empty groups. "
                    "User must belong to at least one tenant."
                )
                # REJECT - no tenants in groups
                return BatchColumnMaskResponse(result=[])

            # Check membership in OpenFGA, don't trust the request
            is_member_of_any_tenant = False
            for tenant_id in groups:
                is_member = await self.openfga.check_tenant_membership(
                    user_id, tenant_id
                )
                if is_member:
                    is_member_of_any_tenant = True
                    logger.info(
                        f"User {user_id} verified as member of tenant {tenant_id}"
                    )
                    break  # Found at least one membership

            if not is_member_of_any_tenant:
                logger.warning(
                    f"Access denied: User {user_id} is not a member of any tenant in groups {groups}. "
                    "Membership verification failed in OpenFGA."
                )
                # REJECT - user doesn't belong to any tenant
                return BatchColumnMaskResponse(result=[])

            # Validate operation
            if request.input.action.operation != "GetColumnMask":
                logger.warning(
                    f"Unexpected operation: {request.input.action.operation}, "
                    "expected 'GetColumnMask'"
                )

            mask_entries = []

            # Process each column in filterResources
            for index, filter_resource in enumerate(
                request.input.action.filterResources
            ):
                column = filter_resource.column

                try:
                    # Build resource spec from column object
                    resource_spec = ResourceSpec(
                        catalog=column.catalogName,
                        schema=column.schemaName,
                        table=column.tableName,
                        column=column.columnName,
                    )

                    # Build column object_id using resource_builder (FGA v3 format)
                    result = build_fga_resource_identifiers(
                        resource_spec, "mask", raise_on_error=False
                    )

                    if not result:
                        logger.debug(
                            f"Could not build identifier for column {column.columnName} "
                            f"at index {index}, skipping"
                        )
                        continue

                    object_id, resource_type, resource_id = result

                    # Verify it's a column resource
                    if resource_type != "column":
                        logger.debug(
                            f"Expected column resource, got {resource_type} "
                            f"for column {column.columnName} at index {index}, skipping"
                        )
                        continue

                    # Check if user has mask permission on this column
                    # Need to check: direct user + all tenants in groups
                    has_mask = False

                    # 1. Check direct user permission
                    has_mask = await self.openfga.check_permission(
                        user, "mask", object_id
                    )

                    if has_mask:
                        logger.debug(
                            f"Column {column.columnName} has direct user mask"
                        )

                    # 2. If not masked yet, check each tenant in groups
                    if not has_mask and groups:
                        for tenant_id in groups:
                            tenant_user = f"tenant:{tenant_id}#member"
                            has_tenant_mask = (
                                await self.openfga.check_permission(
                                    tenant_user, "mask", object_id
                                )
                            )
                            if has_tenant_mask:
                                has_mask = True
                                logger.debug(
                                    f"Column {column.columnName} has mask via tenant {tenant_id}"
                                )
                                break  # Found mask, no need to check other tenants

                    logger.debug(
                        f"Column check result: column={column.columnName}, "
                        f"index={index}, object_id={object_id}, has_mask={has_mask}"
                    )

                    if has_mask:
                        # Build SQL expression - mask entire column value
                        # Format: '*****' (simple string literal that masks everything)
                        mask_expression = "'*****'"

                        logger.info(
                            f"Column {column.columnName} at index {index} needs masking. "
                            f"Expression: {mask_expression}"
                        )

                        # Add mask entry with SQL expression
                        mask_entries.append(
                            MaskEntry(
                                index=index,
                                viewExpression=ViewExpression(
                                    expression=mask_expression
                                ),
                            )
                        )
                    else:
                        logger.debug(
                            f"Column {column.columnName} at index {index} does not need masking"
                        )

                except Exception as e:
                    logger.warning(
                        f"Error processing column {column.columnName} at index {index}: {e}",
                        exc_info=True,
                    )
                    # Continue processing other columns even if one fails
                    continue

            logger.info(
                f"Batch column mask check completed: user={user_id}, "
                f"total_columns={len(request.input.action.filterResources)}, "
                f"masked_columns={len(mask_entries)}"
            )

            # Log the response for debugging
            if mask_entries:
                result_details = [
                    {
                        "index": entry.index,
                        "expression": entry.viewExpression.expression,
                    }
                    for entry in mask_entries
                ]
                logger.info(f"Returning mask entries: {result_details}")
            else:
                logger.info("No columns need masking, returning empty result")

            return BatchColumnMaskResponse(result=mask_entries)

        except Exception as e:
            logger.error(
                f"Error in batch column mask check: {e}",
                exc_info=True,
            )
            # Return empty result on error (fail gracefully)
            return BatchColumnMaskResponse(result=[])
