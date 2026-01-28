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
    build_user_identifier_with_type,
    map_operation_to_relation,
)
from app.utils.resource_builder import (
    build_fga_resource_identifiers,
    build_resource_identifiers,
)
from app.utils.type_mapper import (
    FGA_SYSTEM_PROJECT,
    FGA_TYPE_LAKEKEEPER_TABLE,
    FGA_TYPE_NAMESPACE,
    FGA_TYPE_WAREHOUSE,
    api_object_id_to_fga,
    build_fga_catalog_object_id,
    build_fga_project_object_id,
    build_fga_schema_object_id,
    build_fga_table_object_id,
)

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

        Implements hierarchical permission checking:
        - Catalog permissions apply to schemas and tables within
        - Schema permissions apply to tables within
        - Table permissions apply to columns within (via FGA model)

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

            # 2. Build OpenFGA v3 object ID directly from request (no DB resolution)
            # This returns FGA format: warehouse/namespace/lakekeeper_table
            result = build_fga_resource_identifiers(
                request_data.resource,
                request_data.operation,
                raise_on_error=False,
            )

            if not result:
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

            # Extract identifiers from result tuple (now in FGA format)
            # object_id: warehouse:xxx, namespace:xxx.yyy, lakekeeper_table:xxx.yyy.zzz
            fga_object_id, fga_resource_type, resource_id = result

            # 3. Build user identifier
            user = build_user_identifier(request_data.user_id)

            # Special case: CreateCatalog
            # Check 'create' permission on the Project (parent of catalog)
            # As per deployment rules, there is only one project: FGA_SYSTEM_PROJECT
            if request_data.operation == "CreateCatalog":
                # Check 'create' permission on the Project (parent of catalog)
                # As per deployment rules, there is only one project: FGA_SYSTEM_PROJECT
                fga_object_id = build_fga_project_object_id(FGA_SYSTEM_PROJECT)

                logger.info(
                    f"CreateCatalog check: redirecting to project level "
                    f"(checking {relation} on {fga_object_id})"
                )

            # Special case: Always allow read operations on information_schema
            # information_schema is a metadata schema that should be accessible to users
            # who have access to the catalog
            resource_dict = request_data.resource
            schema_name = resource_dict.get("schema", "")
            if schema_name == "information_schema":
                # Allow read operations: select, describe, show operations
                read_operations = {
                    "SelectFromColumns",
                    "ShowTables",
                    "ShowColumns",
                    "ShowSchemas",
                    "GetColumnMask",
                }
                if request_data.operation in read_operations:
                    logger.info(
                        f"Allowing {request_data.operation} on information_schema "
                        f"(metadata schema is always accessible)"
                    )
                    return PermissionCheckResponse(allowed=True)

            # 4. Hierarchical permission checking
            # Check permission in order: catalog -> schema -> table
            # If permission exists at any level, allow access

            # Column-level permissions are inherited from table in FGA model
            # EXCEPT for 'mask' relation which is column-specific
            # So we redirect column checks to table level for all other relations
            if fga_resource_type == "column" and relation != "mask":
                logger.info(
                    f"Column-level {relation} check: redirecting to table level "
                    f"(column {relation} inherits from table in FGA model)"
                )
                # Extract table object_id from column resource
                # column format: column:catalog.schema.table.column
                # we need: lakekeeper_table:catalog.schema.table
                parts = resource_id.split(".")
                if len(parts) >= 4:
                    catalog_name, schema_name, table_name = (
                        parts[0],
                        parts[1],
                        parts[2],
                    )
                    fga_object_id = build_fga_table_object_id(
                        catalog_name, schema_name, table_name
                    )
                    fga_resource_type = FGA_TYPE_LAKEKEEPER_TABLE
                    resource_id = f"{catalog_name}.{schema_name}.{table_name}"
                else:
                    logger.warning(
                        f"Invalid column resource_id format: {resource_id}"
                    )
                    return PermissionCheckResponse(allowed=False)

            # Check at the target resource level first (using FGA object_id)
            allowed = await self.openfga.check_permission(
                user, relation, fga_object_id
            )

            if allowed:
                logger.info(
                    f"Permission check: ALLOWED at {fga_resource_type} level for user={request_data.user_id}"
                )
                return PermissionCheckResponse(allowed=True)

            # Special case: AccessCatalog and ShowSchemas operations on catalog level
            # If user doesn't have explicit 'select' permission on catalog object,
            # check if they have ANY OTHER permission on the catalog
            # or ANY permission on ANY resource within this catalog
            # ShowSchemas with catalog resource = "can user see schemas in this catalog?"
            if (
                request_data.operation in ("AccessCatalog", "ShowSchemas")
                and fga_resource_type == FGA_TYPE_WAREHOUSE
            ):
                catalog_name = resource_id

                # First, check if user has ANY permission on the warehouse itself
                # (not just 'select' which was checked above)
                for warehouse_relation in ["describe", "modify", "create"]:
                    try:
                        has_perm = await self.openfga.check_permission(
                            user, warehouse_relation, fga_object_id
                        )
                        if has_perm:
                            logger.info(
                                f"{request_data.operation}: ALLOWED - user has {warehouse_relation} "
                                f"on warehouse {catalog_name}"
                            )
                            return PermissionCheckResponse(allowed=True)
                    except Exception as e:
                        logger.debug(
                            f"Error checking {warehouse_relation} on warehouse: {e}"
                        )

                logger.info(
                    f"{request_data.operation} denied at catalog level, checking for any permissions "
                    f"within catalog {catalog_name}"
                )

                # Check if user has permissions on any schema or table in this catalog
                # Relations differ by object type:
                # - namespace: select, describe, modify, create
                # - lakekeeper_table: select, describe, modify (no create)
                try:
                    # Check namespaces with all relations
                    for check_relation in [
                        "select",
                        "describe",
                        "modify",
                        "create",
                    ]:
                        try:
                            namespace_objects = await self.openfga.list_objects(
                                user=user,
                                relation=check_relation,
                                object_type=FGA_TYPE_NAMESPACE,
                            )
                            # Check if any namespace belongs to this warehouse
                            for namespace_obj in namespace_objects:
                                # namespace format: namespace:catalog.schema
                                if namespace_obj.startswith(
                                    f"{FGA_TYPE_NAMESPACE}:{catalog_name}."
                                ):
                                    logger.info(
                                        f"{request_data.operation}: ALLOWED - user has {check_relation} "
                                        f"on {namespace_obj} in warehouse {catalog_name}"
                                    )
                                    return PermissionCheckResponse(allowed=True)
                        except Exception as e:
                            logger.debug(
                                f"No {check_relation} permission found on namespaces: {e}"
                            )

                    # Check lakekeeper_tables with only valid relations (no 'create')
                    for check_relation in [
                        "select",
                        "describe",
                        "modify",
                    ]:
                        try:
                            table_objects = await self.openfga.list_objects(
                                user=user,
                                relation=check_relation,
                                object_type=FGA_TYPE_LAKEKEEPER_TABLE,
                            )
                            # Check if any lakekeeper_table belongs to this warehouse
                            for table_obj in table_objects:
                                # lakekeeper_table format: lakekeeper_table:catalog.schema.table
                                if table_obj.startswith(
                                    f"{FGA_TYPE_LAKEKEEPER_TABLE}:{catalog_name}."
                                ):
                                    logger.info(
                                        f"{request_data.operation}: ALLOWED - user has {check_relation} "
                                        f"on {table_obj} in warehouse {catalog_name}"
                                    )
                                    return PermissionCheckResponse(allowed=True)
                        except Exception as e:
                            logger.debug(
                                f"No {check_relation} permission found on lakekeeper_tables: {e}"
                            )

                    logger.info(
                        f"{request_data.operation}: DENIED - no permissions found in warehouse {catalog_name}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Error checking catalog-level permissions: {e}, denying"
                    )

            # Special case: ShowTables operation (used by FilterTables)
            # If user has permission on ANY table within this schema, they should see tables
            # This allows users who have table-level permissions to see those tables in SHOW TABLES
            if (
                request_data.operation == "ShowTables"
                and fga_resource_type == FGA_TYPE_NAMESPACE
            ):
                parts = resource_id.split(".")
                if len(parts) >= 2:
                    catalog_name, schema_name = parts[0], parts[1]
                    schema_fqn = f"{catalog_name}.{schema_name}"

                    logger.info(
                        f"ShowTables denied at namespace level, checking for any permissions "
                        f"on tables within schema {schema_fqn}"
                    )

                    # First check if user has any permission on the namespace itself
                    for ns_relation in [
                        "select",
                        "describe",
                        "modify",
                        "create",
                    ]:
                        try:
                            has_perm = await self.openfga.check_permission(
                                user, ns_relation, fga_object_id
                            )
                            if has_perm:
                                logger.info(
                                    f"ShowTables: ALLOWED - user has {ns_relation} "
                                    f"on namespace {schema_fqn}"
                                )
                                return PermissionCheckResponse(allowed=True)
                        except Exception as e:
                            logger.debug(
                                f"Error checking {ns_relation} on namespace: {e}"
                            )

                    # Check if user has permissions on any table in this schema
                    for check_relation in ["select", "describe", "modify"]:
                        try:
                            table_objects = await self.openfga.list_objects(
                                user=user,
                                relation=check_relation,
                                object_type=FGA_TYPE_LAKEKEEPER_TABLE,
                            )
                            # Check if any table belongs to this schema
                            for table_obj in table_objects:
                                # lakekeeper_table format: lakekeeper_table:catalog.schema.table
                                if table_obj.startswith(
                                    f"{FGA_TYPE_LAKEKEEPER_TABLE}:{schema_fqn}."
                                ):
                                    logger.info(
                                        f"ShowTables: ALLOWED - user has {check_relation} "
                                        f"on {table_obj} in schema {schema_fqn}"
                                    )
                                    return PermissionCheckResponse(allowed=True)
                        except Exception as e:
                            logger.debug(
                                f"No {check_relation} permission found on tables in schema: {e}"
                            )

                    # Finally, check if user has any permission at warehouse level.
                    # This enables hierarchical behaviour for SHOW TABLES when a user
                    # has been granted access at warehouse/catalog scope only.
                    warehouse_object_id = build_fga_catalog_object_id(catalog_name)
                    for warehouse_relation in [
                        "select",
                        "describe",
                        "modify",
                        "create",
                    ]:
                        try:
                            has_perm = await self.openfga.check_permission(
                                user, warehouse_relation, warehouse_object_id
                            )
                            if has_perm:
                                logger.info(
                                    "ShowTables: ALLOWED - user has %s on warehouse %s "
                                    "-> allowing tables in schema %s via hierarchical inheritance",
                                    warehouse_relation,
                                    catalog_name,
                                    schema_fqn,
                                )
                                return PermissionCheckResponse(allowed=True)
                        except Exception as e:
                            logger.debug(
                                "Error checking %s on warehouse %s for ShowTables: %s",
                                warehouse_relation,
                                catalog_name,
                                e,
                            )

                    logger.info(
                        f"ShowTables: DENIED - no permissions found on tables/schema/warehouse for schema {schema_fqn}"
                    )

            # Special case: ShowSchemas operation (used by FilterSchemas)
            # If user has permission on ANY table within this schema, they should see the schema
            # This is similar to AccessCatalog logic but at schema level
            if (
                request_data.operation == "ShowSchemas"
                and fga_resource_type == FGA_TYPE_NAMESPACE
            ):
                parts = resource_id.split(".")
                if len(parts) >= 2:
                    catalog_name, schema_name = parts[0], parts[1]
                    schema_fqn = f"{catalog_name}.{schema_name}"

                    logger.info(
                        f"ShowSchemas denied at namespace level, checking for any permissions "
                        f"on tables within schema {schema_fqn}"
                    )

                    # First check if user has any permission on the namespace itself
                    for ns_relation in [
                        "select",
                        "describe",
                        "modify",
                        "create",
                    ]:
                        try:
                            has_perm = await self.openfga.check_permission(
                                user, ns_relation, fga_object_id
                            )
                            if has_perm:
                                logger.info(
                                    f"ShowSchemas: ALLOWED - user has {ns_relation} "
                                    f"on namespace {schema_fqn}"
                                )
                                return PermissionCheckResponse(allowed=True)
                        except Exception as e:
                            logger.debug(
                                f"Error checking {ns_relation} on namespace: {e}"
                            )

                    # Check if user has permissions on any table in this schema
                    for check_relation in ["select", "describe", "modify"]:
                        try:
                            table_objects = await self.openfga.list_objects(
                                user=user,
                                relation=check_relation,
                                object_type=FGA_TYPE_LAKEKEEPER_TABLE,
                            )
                            # Check if any table belongs to this schema
                            for table_obj in table_objects:
                                # lakekeeper_table format: lakekeeper_table:catalog.schema.table
                                if table_obj.startswith(
                                    f"{FGA_TYPE_LAKEKEEPER_TABLE}:{schema_fqn}."
                                ):
                                    logger.info(
                                        f"ShowSchemas: ALLOWED - user has {check_relation} "
                                        f"on {table_obj} in namespace {schema_fqn}"
                                    )
                                    return PermissionCheckResponse(allowed=True)
                        except Exception as e:
                            logger.debug(
                                f"No {check_relation} permission found on tables in schema: {e}"
                            )

                    # Finally, check if user has any permission at warehouse level.
                    # This enables hierarchical behaviour for SHOW SCHEMAS when a user
                    # has only been granted access at warehouse/catalog scope.
                    warehouse_object_id = build_fga_catalog_object_id(catalog_name)
                    for warehouse_relation in [
                        "select",
                        "describe",
                        "modify",
                        "create",
                    ]:
                        try:
                            has_perm = await self.openfga.check_permission(
                                user, warehouse_relation, warehouse_object_id
                            )
                            if has_perm:
                                logger.info(
                                    "ShowSchemas: ALLOWED - user has %s on warehouse %s "
                                    "-> allowing schema %s via hierarchical inheritance",
                                    warehouse_relation,
                                    catalog_name,
                                    schema_fqn,
                                )
                                return PermissionCheckResponse(allowed=True)
                        except Exception as e:
                            logger.debug(
                                "Error checking %s on warehouse %s for ShowSchemas: %s",
                                warehouse_relation,
                                catalog_name,
                                e,
                            )

                    logger.info(
                        f"ShowSchemas: DENIED - no permissions found in namespace/schema/warehouse for {schema_fqn}"
                    )

            # If not allowed at target level, check hierarchically at parent levels
            # lakekeeper_table -> check namespace -> check warehouse
            # BUT: Skip hierarchical check for certain filter operations where we intentionally
            # do NOT want inheritance (currently only columns).
            filter_operations = {
                # Used by FilterColumns
                "ShowColumns",
            }

            # For filter operations, don't do hierarchical check - rely on OpenFGA model's inheritance
            if request_data.operation in filter_operations:
                logger.info(
                    f"Permission check: DENIED at all levels for user={request_data.user_id} "
                    f"(filter operation - no hierarchical inheritance)"
                )
                # Don't return here - let it fall through to final denied
            elif fga_resource_type == FGA_TYPE_LAKEKEEPER_TABLE:
                parts = resource_id.split(".")
                if len(parts) >= 3:
                    catalog_name, schema_name = parts[0], parts[1]

                    # Check namespace level (FGA v3 format)
                    namespace_object_id = build_fga_schema_object_id(
                        catalog_name, schema_name
                    )
                    allowed = await self.openfga.check_permission(
                        user, relation, namespace_object_id
                    )

                    if allowed:
                        logger.info(
                            f"Permission check: ALLOWED at namespace level (hierarchical) for user={request_data.user_id}"
                        )
                        return PermissionCheckResponse(allowed=True)

                    # Check warehouse level (FGA v3 format)
                    warehouse_object_id = build_fga_catalog_object_id(
                        catalog_name
                    )
                    allowed = await self.openfga.check_permission(
                        user, relation, warehouse_object_id
                    )

                    if allowed:
                        logger.info(
                            f"Permission check: ALLOWED at warehouse level (hierarchical) for user={request_data.user_id}"
                        )
                        return PermissionCheckResponse(allowed=True)

            # Namespace -> check warehouse
            elif fga_resource_type == FGA_TYPE_NAMESPACE:
                parts = resource_id.split(".")
                if len(parts) >= 2:
                    catalog_name = parts[0]

                    # Check warehouse level (FGA v3 format)
                    warehouse_object_id = build_fga_catalog_object_id(
                        catalog_name
                    )
                    allowed = await self.openfga.check_permission(
                        user, relation, warehouse_object_id
                    )

                    if allowed:
                        logger.info(
                            f"Permission check: ALLOWED at warehouse level (hierarchical) for user={request_data.user_id}"
                        )
                        return PermissionCheckResponse(allowed=True)

            # If we get here, permission denied at all levels
            logger.info(
                f"Permission check: DENIED at all levels for user={request_data.user_id}"
            )
            return PermissionCheckResponse(allowed=False)

        except Exception as e:
            logger.error(f"Error checking permission: {e}", exc_info=True)
            # Fail closed - deny on error
            return PermissionCheckResponse(allowed=False)

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

        # Build API resource identifiers (for response)
        api_object_id, api_resource_type, resource_id = (
            self._build_resource_identifiers(resource, grant.relation)
        )

        # Convert to FGA format for OpenFGA communication
        fga_object_id = api_object_id_to_fga(api_object_id)

        # Build user identifier based on user_type
        user = build_user_identifier_with_type(
            grant.user_id, grant.user_type.value
        )

        # Prepare condition dict if provided
        condition_dict = None
        if grant.condition:
            condition_dict = {
                "name": grant.condition.name,
                "context": grant.condition.context.model_dump(),
            }
            logger.info(
                f"Granting permission with condition: user={user}, relation={grant.relation}, "
                f"object={fga_object_id}, condition={grant.condition.name}"
            )

        # Grant permission in OpenFGA (using FGA object_id)
        await self.openfga.grant_permission(
            user, grant.relation, fga_object_id, condition=condition_dict
        )

        if grant.condition:
            logger.info(
                f"Permission granted with condition: user={user}, relation={grant.relation}, "
                f"object={fga_object_id}, condition={grant.condition.name}"
            )
        else:
            logger.info(
                f"Permission granted: user={user}, relation={grant.relation}, object={fga_object_id}"
            )

        # Return API types for backward compatibility
        return PermissionGrantResponse(
            success=True,
            user_id=grant.user_id,
            resource_type=api_resource_type,
            resource_id=resource_id,
            object_id=api_object_id,  # Return API format for user-friendly response
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

        # Build API resource identifiers (for response)
        api_object_id, api_resource_type, resource_id = (
            self._build_resource_identifiers(resource, revoke.relation)
        )

        # Convert to FGA format for OpenFGA communication
        fga_object_id = api_object_id_to_fga(api_object_id)

        # Build user identifier based on user_type
        user = build_user_identifier_with_type(
            revoke.user_id, revoke.user_type.value
        )

        # Revoke permission in OpenFGA (using FGA object_id)
        await self.openfga.revoke_permission(
            user, revoke.relation, fga_object_id
        )
        logger.info(f"Permission revoked: user={user}, object={fga_object_id}")

        # Return API types for backward compatibility
        return PermissionRevokeResponse(
            success=True,
            user_id=revoke.user_id,
            resource_type=api_resource_type,
            resource_id=resource_id,
            object_id=api_object_id,  # Return API format for user-friendly response
            relation=revoke.relation,
        )

    def _build_resource_identifiers(
        self, resource, relation: str
    ) -> Tuple[str, str, str]:
        """
        Build resource identifiers (object_id, resource_type, resource_id)

        DEPRECATED: This method is retained for backward compatibility.
        It delegates to the unified build_resource_identifiers function.

        Args:
            resource: Resource specification
            relation: Relation/permission

        Returns:
            Tuple of (object_id, resource_type, resource_id)

        Raises:
            ValueError: If resource specification is invalid
        """
        return build_resource_identifiers(
            resource, relation, raise_on_error=True
        )
