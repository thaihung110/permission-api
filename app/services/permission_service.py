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
from app.utils.resource_builder import build_resource_identifiers

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

            # 2. Build OpenFGA object ID directly from request (no DB resolution)
            result = build_resource_identifiers(
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

            # Extract identifiers from result tuple
            object_id, resource_type, resource_id = result

            # 3. Build user identifier
            user = build_user_identifier(request_data.user_id)

            # 4. Hierarchical permission checking
            # Check permission in order: catalog -> schema -> table
            # If permission exists at any level, allow access

            # Column-level permissions are inherited from table in FGA model
            # EXCEPT for 'mask' relation which is column-specific
            # So we redirect column checks to table level for all other relations
            if resource_type == "column" and relation != "mask":
                logger.info(
                    f"Column-level {relation} check: redirecting to table level "
                    f"(column {relation} inherits from table in FGA model)"
                )
                # Extract table object_id from column resource
                # column format: column:catalog.schema.table.column
                # we need: table:catalog.schema.table
                parts = resource_id.split(".")
                if len(parts) >= 4:
                    catalog_name, schema_name, table_name = (
                        parts[0],
                        parts[1],
                        parts[2],
                    )
                    object_id = (
                        f"table:{catalog_name}.{schema_name}.{table_name}"
                    )
                    resource_type = "table"
                    resource_id = f"{catalog_name}.{schema_name}.{table_name}"
                else:
                    logger.warning(
                        f"Invalid column resource_id format: {resource_id}"
                    )
                    return PermissionCheckResponse(allowed=False)

            # Check at the target resource level first
            allowed = await self.openfga.check_permission(
                user, relation, object_id
            )

            if allowed:
                logger.info(
                    f"Permission check: ALLOWED at {resource_type} level for user={request_data.user_id}"
                )
                return PermissionCheckResponse(allowed=True)

            # Special case: AccessCatalog operation
            # If user doesn't have explicit permission on catalog object,
            # check if they have ANY permission on ANY resource within this catalog
            # (e.g., permissions on schemas or tables in this catalog)
            if (
                request_data.operation == "AccessCatalog"
                and resource_type == "catalog"
            ):
                catalog_name = resource_id
                logger.info(
                    f"AccessCatalog denied at catalog level, checking for any permissions "
                    f"within catalog {catalog_name}"
                )

                # Check if user has permissions on any schema or table in this catalog
                # We'll check for common relations: select, describe, modify, create
                try:
                    for check_relation in [
                        "select",
                        "describe",
                        "modify",
                        "create",
                    ]:
                        # Check schemas in this catalog
                        try:
                            schema_objects = await self.openfga.list_objects(
                                user=user,
                                relation=check_relation,
                                object_type="schema",
                            )
                            # Check if any schema belongs to this catalog
                            for schema_obj in schema_objects:
                                # schema format: schema:catalog.schema
                                if schema_obj.startswith(
                                    f"schema:{catalog_name}."
                                ):
                                    logger.info(
                                        f"AccessCatalog: ALLOWED - user has {check_relation} "
                                        f"on {schema_obj} in catalog {catalog_name}"
                                    )
                                    return PermissionCheckResponse(allowed=True)
                        except Exception as e:
                            logger.debug(
                                f"No {check_relation} permission found on schemas: {e}"
                            )

                        # Check tables in this catalog
                        try:
                            table_objects = await self.openfga.list_objects(
                                user=user,
                                relation=check_relation,
                                object_type="table",
                            )
                            # Check if any table belongs to this catalog
                            for table_obj in table_objects:
                                # table format: table:catalog.schema.table
                                if table_obj.startswith(
                                    f"table:{catalog_name}."
                                ):
                                    logger.info(
                                        f"AccessCatalog: ALLOWED - user has {check_relation} "
                                        f"on {table_obj} in catalog {catalog_name}"
                                    )
                                    return PermissionCheckResponse(allowed=True)
                        except Exception as e:
                            logger.debug(
                                f"No {check_relation} permission found on tables: {e}"
                            )

                    logger.info(
                        f"AccessCatalog: DENIED - no permissions found in catalog {catalog_name}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Error checking catalog-level permissions: {e}, denying"
                    )

            # If not allowed at target level, check hierarchically at parent levels
            # Table -> check schema -> check catalog
            if resource_type == "table":
                parts = resource_id.split(".")
                if len(parts) >= 3:
                    catalog_name, schema_name = parts[0], parts[1]

                    # Check schema level
                    schema_object_id = f"schema:{catalog_name}.{schema_name}"
                    allowed = await self.openfga.check_permission(
                        user, relation, schema_object_id
                    )

                    if allowed:
                        logger.info(
                            f"Permission check: ALLOWED at schema level (hierarchical) for user={request_data.user_id}"
                        )
                        return PermissionCheckResponse(allowed=True)

                    # Check catalog level
                    catalog_object_id = f"catalog:{catalog_name}"
                    allowed = await self.openfga.check_permission(
                        user, relation, catalog_object_id
                    )

                    if allowed:
                        logger.info(
                            f"Permission check: ALLOWED at catalog level (hierarchical) for user={request_data.user_id}"
                        )
                        return PermissionCheckResponse(allowed=True)

            # Schema -> check catalog
            elif resource_type == "schema":
                parts = resource_id.split(".")
                if len(parts) >= 2:
                    catalog_name = parts[0]

                    # Check catalog level
                    catalog_object_id = f"catalog:{catalog_name}"
                    allowed = await self.openfga.check_permission(
                        user, relation, catalog_object_id
                    )

                    if allowed:
                        logger.info(
                            f"Permission check: ALLOWED at catalog level (hierarchical) for user={request_data.user_id}"
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

        # Build normal resource identifier
        # Note: Row filter policies should use /row-filter/grant endpoint instead
        object_id, resource_type, resource_id = (
            self._build_resource_identifiers(resource, grant.relation)
        )

        # Build user identifier
        user = build_user_identifier(grant.user_id)

        # Prepare condition dict if provided
        condition_dict = None
        if grant.condition:
            condition_dict = {
                "name": grant.condition.name,
                "context": grant.condition.context.model_dump(),
            }
            logger.info(
                f"Granting permission with condition: user={user}, relation={grant.relation}, "
                f"object={object_id}, condition={grant.condition.name}"
            )

        # Grant permission in OpenFGA
        await self.openfga.grant_permission(
            user, grant.relation, object_id, condition=condition_dict
        )

        if grant.condition:
            logger.info(
                f"Permission granted with condition: user={user}, relation={grant.relation}, "
                f"object={object_id}, condition={grant.condition.name}"
            )
        else:
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

        # Build normal resource identifier
        # Note: Row filter policies should use /row-filter/revoke endpoint instead
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
