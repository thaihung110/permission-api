"""
Permission service - Business logic for permission management
"""

import logging
from typing import Optional, Tuple

from app.external.openfga_client import OpenFGAManager
from app.schemas.permission import (
    PermissionCheckRequest,
    PermissionCheckResponse,
    PermissionGrant,
    PermissionGrantResponse,
    PermissionRevoke,
    PermissionRevokeResponse,
)
from app.utils.operation_mapper import (
    build_user_identifier,
    map_operation_to_relation,
)
from app.utils.resource_builder import build_object_id_from_resource

logger = logging.getLogger(__name__)


class PermissionService:
    """Service for handling permission operations"""

    def __init__(self, openfga: OpenFGAManager):
        """
        Initialize permission service

        Args:
            openfga: OpenFGA manager instance
        """
        self.openfga = openfga

    async def check_permission(
        self, request_data: PermissionCheckRequest
    ) -> PermissionCheckResponse:
        """
        Check if user has permission to perform operation on resource

        This is called by OPA to validate Trino queries.

        Args:
            request_data: Permission check request

        Returns:
            Permission check response with allowed flag
        """
        logger.info(
            f"Permission check: user={request_data.user_id}, "
            f"operation={request_data.operation}, resource={request_data.resource}"
        )

        try:
            # 1. Map operation to OpenFGA relation
            relation = map_operation_to_relation(request_data.operation)
            if not relation:
                logger.warning(
                    f"Unknown operation: {request_data.operation}, denying"
                )
                return PermissionCheckResponse(allowed=False)

            # 2. Build OpenFGA object ID directly from request (no DB resolution)
            object_id = build_object_id_from_resource(
                request_data.resource, request_data.operation
            )

            if not object_id:
                # Special handling for operations that require specific resources
                if request_data.operation == "CreateSchema":
                    logger.warning(
                        f"CreateSchema requires catalog in resource: {request_data.resource}, denying"
                    )
                elif request_data.operation == "CreateTable":
                    logger.warning(
                        f"CreateTable requires catalog and schema in resource: {request_data.resource}, denying"
                    )
                else:
                    logger.warning(
                        f"Unable to build object_id from resource: {request_data.resource}, denying"
                    )
                return PermissionCheckResponse(allowed=False)

            # 3. Build user identifier
            user = build_user_identifier(request_data.user_id)

            # 4. Check permission in OpenFGA with hierarchical checking
            # For table operations, check both schema and table permissions
            allowed = await self._check_permission_hierarchical(
                user,
                relation,
                object_id,
                request_data.resource,
                request_data.operation,
            )

            logger.info(
                f"Permission check result: allowed={allowed} for user={request_data.user_id}"
            )

            return PermissionCheckResponse(allowed=allowed)

        except Exception as e:
            logger.error(f"Error checking permission: {e}", exc_info=True)
            # Fail closed - deny on error
            return PermissionCheckResponse(allowed=False)

    async def _check_permission_hierarchical(
        self,
        user: str,
        relation: str,
        object_id: str,
        resource: dict,
        operation: str,
    ) -> bool:
        """
        Check permission hierarchically - check parent resources first

        For table operations with columns, this checks:
        1. Schema (namespace) permission
        2. Table permission
        3. Column permissions (for SelectFromColumns operation)

        All checks must pass for the operation to be allowed.

        Args:
            user: User identifier
            relation: OpenFGA relation
            object_id: Target object ID
            resource: Resource dict from request
            operation: Operation name

        Returns:
            True if all hierarchical checks pass
        """
        try:
            # Extract resource components
            # Handle both flat structure and nested table structure
            table_resource = resource.get("table")

            # Check if we have nested structure (table is a dict with catalogName, etc.)
            if table_resource and isinstance(table_resource, dict):
                # Nested structure from Trino (e.g., from mask check)
                catalog_name = table_resource.get("catalogName")
                schema_name = table_resource.get("schemaName")
                table_name = table_resource.get("tableName")
                columns = table_resource.get("columns", [])
            else:
                # Flat structure (direct keys from OPA build_resource)
                catalog_name = resource.get("catalog_name") or resource.get(
                    "catalog"
                )
                schema_name = resource.get("schema_name") or resource.get(
                    "schema"
                )
                table_name = resource.get("table_name") or resource.get("table")
                columns = resource.get("columns", [])

            # For MaskColumn operation, check mask permission on the specific column
            if operation == "MaskColumn":
                logger.info(
                    f"Checking MASK permission on column: user={user}, relation={relation}, column={object_id}"
                )

                allowed = await self.openfga.check_permission(
                    user, relation, object_id
                )

                if not allowed:
                    logger.info(
                        f"Column MASK permission denied (no mask applied): user={user}, column={object_id}"
                    )
                    return False

                logger.info(
                    f"Column MASK permission granted (mask will be applied): user={user}, column={object_id}"
                )
                return True

            # Debug: Log extracted values
            logger.info(
                f"Extracted resource components: catalog={catalog_name}, schema={schema_name}, "
                f"table={table_name}, columns={columns}, operation={operation}"
            )

            # For table operations, check schema permission first
            if table_name and schema_name and catalog_name:
                # Build schema object ID
                schema_object_id = f"namespace:{catalog_name}.{schema_name}"

                logger.info(
                    f"Hierarchical check - First checking schema: user={user}, relation={relation}, schema={schema_object_id}"
                )

                # Check schema permission
                schema_allowed = await self.openfga.check_permission(
                    user, relation, schema_object_id
                )

                if not schema_allowed:
                    logger.warning(
                        f"Schema permission denied: user={user}, schema={schema_object_id}, relation={relation}"
                    )
                    return False

                logger.info(
                    f"Schema permission granted: user={user}, schema={schema_object_id}"
                )

            # Check the target resource permission (table)
            logger.info(
                f"Checking target resource: user={user}, relation={relation}, object={object_id}"
            )

            allowed = await self.openfga.check_permission(
                user, relation, object_id
            )

            if not allowed:
                logger.warning(
                    f"Table permission denied: user={user}, table={object_id}, relation={relation}"
                )
                return False

            logger.info(
                f"Table permission granted: user={user}, table={object_id}"
            )

            # For SelectFromColumns, check permission on each column
            if operation == "SelectFromColumns" and columns:
                logger.info(
                    f"Checking column permissions for {len(columns)} columns: {columns}"
                )

                for column_name in columns:
                    column_object_id = f"column:{catalog_name}.{schema_name}.{table_name}.{column_name}"

                    logger.info(
                        f"Checking column SELECT permission: user={user}, column={column_object_id}"
                    )

                    # Must have 'select' permission on column
                    column_select_allowed = await self.openfga.check_permission(
                        user, relation, column_object_id
                    )

                    if not column_select_allowed:
                        logger.warning(
                            f"Column SELECT permission denied: user={user}, column={column_object_id}"
                        )
                        return False

                    # Check if column should be masked
                    column_mask_allowed = await self.openfga.check_permission(
                        user, "mask", column_object_id
                    )

                    if column_mask_allowed:
                        logger.info(
                            f"Column permission: user={user}, column={column_name} - SELECT granted, MASK enabled (data will be masked)"
                        )
                    else:
                        logger.info(
                            f"Column permission: user={user}, column={column_name} - SELECT granted (show normal data)"
                        )

                logger.info(
                    f"All column SELECT permissions granted for user={user}"
                )

            return True

        except Exception as e:
            logger.error(
                f"Error in hierarchical permission check: {e}", exc_info=True
            )
            return False

    async def grant_permission(
        self, grant: PermissionGrant
    ) -> PermissionGrantResponse:
        """
        Grant permission to user on resource

        Args:
            grant: Permission grant request

        Returns:
            Permission grant response

        Raises:
            ValueError: If resource specification is invalid
        """
        logger.info(
            f"Granting permission: user={grant.user_id}, "
            f"resource={grant.resource.model_dump(exclude_none=True)}, relation={grant.relation}"
        )

        resource = grant.resource
        object_id, resource_type, resource_id = (
            self._build_resource_identifiers(resource, grant.relation)
        )

        # Build user identifier
        user = build_user_identifier(grant.user_id)

        # Grant permission in OpenFGA
        await self.openfga.grant_permission(user, grant.relation, object_id)

        logger.info(
            f"Permission granted: user={user}, relation={grant.relation}, object={object_id}"
        )

        return PermissionGrantResponse(
            success=True,
            user_id=grant.user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            object_id=object_id,
            relation=grant.relation,
        )

    async def revoke_permission(
        self, revoke: PermissionRevoke
    ) -> PermissionRevokeResponse:
        """
        Revoke permission from user on resource

        Args:
            revoke: Permission revoke request

        Returns:
            Permission revoke response

        Raises:
            ValueError: If resource specification is invalid
        """
        logger.info(
            f"Revoking permission: user={revoke.user_id}, "
            f"resource={revoke.resource.model_dump(exclude_none=True)}, relation={revoke.relation}"
        )

        resource = revoke.resource
        object_id, resource_type, resource_id = (
            self._build_resource_identifiers(resource, revoke.relation)
        )

        # Build user identifier
        user = build_user_identifier(revoke.user_id)

        # Revoke permission in OpenFGA
        await self.openfga.revoke_permission(user, revoke.relation, object_id)

        logger.info(f"Permission revoked: user={user}, object={object_id}")

        return PermissionRevokeResponse(
            success=True,
            user_id=revoke.user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            object_id=object_id,
            relation=revoke.relation,
        )

    def _build_resource_identifiers(
        self, resource, relation: str
    ) -> Tuple[str, str, str]:
        """
        Build resource identifiers (object_id, resource_type, resource_id)

        Args:
            resource: Resource specification
            relation: Relation/permission

        Returns:
            Tuple of (object_id, resource_type, resource_id)

        Raises:
            ValueError: If resource specification is invalid
        """
        # Get schema (support both schema and namespace for backward compatibility)
        schema_name = resource.schema or resource.namespace

        # Priority: catalog (standalone) > column > table > schema
        # Special handling for CreateCatalog: when resource is empty and relation is create,
        # treat as CreateCatalog operation
        if (
            relation == "create"
            and not resource.catalog
            and not schema_name
            and not resource.table
        ):
            # CreateCatalog with empty resource
            object_id = "catalog:system"
            resource_type = "catalog"
            resource_id = "system"
            return object_id, resource_type, resource_id

        if resource.catalog and not schema_name and not resource.table:
            # Catalog-level permission (standalone)
            catalog_name = resource.catalog
            object_id = f"catalog:{catalog_name}"
            resource_type = "catalog"
            resource_id = catalog_name

        elif resource.column:
            # Column-level permission (requires catalog, schema, and table)
            if not (resource.catalog and schema_name and resource.table):
                raise ValueError(
                    "Column-level permission requires catalog, schema, table, and column. "
                    'Example: {"catalog": "lakekeeper", "schema": "finance", "table": "user", "column": "email"}'
                )
            catalog_name = resource.catalog
            table_name = resource.table
            column_name = resource.column
            object_id = f"column:{catalog_name}.{schema_name}.{table_name}.{column_name}"
            resource_type = "column"
            resource_id = (
                f"{catalog_name}.{schema_name}.{table_name}.{column_name}"
            )

        elif resource.table and schema_name:
            # Table-level permission (requires catalog and schema)
            if not resource.catalog:
                raise ValueError(
                    "Table-level permission requires catalog, schema, and table. "
                    'Example: {"catalog": "lakekeeper", "schema": "finance", "table": "user"}'
                )
            catalog_name = resource.catalog
            table_name = resource.table
            object_id = f"table:{catalog_name}.{schema_name}.{table_name}"
            resource_type = "table"
            resource_id = f"{catalog_name}.{schema_name}.{table_name}"

        elif schema_name:
            # Schema-level permission (requires catalog)
            if not resource.catalog:
                raise ValueError(
                    "Schema-level permission requires catalog and schema. "
                    'Example: {"catalog": "lakekeeper", "schema": "finance"}'
                )
            catalog_name = resource.catalog
            object_id = f"namespace:{catalog_name}.{schema_name}"
            resource_type = "schema"
            resource_id = f"{catalog_name}.{schema_name}"

        else:
            raise ValueError(
                "Resource must specify at least one of: catalog (standalone), "
                "schema (with catalog), or table (with catalog and schema)."
            )

        return object_id, resource_type, resource_id
