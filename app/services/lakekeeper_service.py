"""
Lakekeeper service - Business logic for listing resources with permissions
"""

import logging
from typing import Any, Dict, List, Set

from app.external.lakekeeper_client import LakekeeperClient
from app.external.openfga_client import OpenFGAManager
from app.schemas.lakekeeper import (
    ColumnInfo,
    ListResourcesResponse,
    NamespaceInfo,
    RowFilterInfo,
    TableInfo,
    WarehouseInfo,
)
from app.services.row_filter_service import RowFilterService, escape_sql_value
from app.utils.operation_mapper import build_user_identifier
from app.utils.type_mapper import (
    FGA_TYPE_COLUMN,
    FGA_TYPE_LAKEKEEPER_TABLE,
    FGA_TYPE_NAMESPACE,
    FGA_TYPE_WAREHOUSE,
    build_fga_catalog_object_id,
    build_fga_column_object_id,
    build_fga_schema_object_id,
    build_fga_table_object_id,
)

logger = logging.getLogger(__name__)


class LakekeeperService:
    """Service for handling Lakekeeper resource operations"""

    # Permissions to check for each resource type
    WAREHOUSE_PERMISSIONS = ["create", "modify", "select", "describe"]
    NAMESPACE_PERMISSIONS = ["create", "modify", "select", "describe"]
    TABLE_PERMISSIONS = [
        "modify",
        "select",
        "describe",
    ]  # Table không có create

    def __init__(
        self,
        openfga: OpenFGAManager,
        lakekeeper_client: LakekeeperClient,
    ):
        """
        Initialize Lakekeeper service

        Args:
            openfga: OpenFGA manager instance
            lakekeeper_client: Lakekeeper HTTP client instance
        """
        self.openfga = openfga
        self.lakekeeper = lakekeeper_client

    async def list_resources_with_permissions(
        self, user_id: str, catalog: str
    ) -> ListResourcesResponse:
        """
        List all Lakekeeper resources with user permissions for a specific catalog

        Fetches namespaces and tables from Lakekeeper for the specified catalog,
        then checks permissions for the user on each resource using
        batch list_objects() calls for efficiency.

        Args:
            user_id: User ID to check permissions for
            catalog: Trino catalog name (e.g., 'lakekeeper_demo').
                    Will be parsed to extract Lakekeeper warehouse name by removing 'lakekeeper_' prefix.

        Returns:
            ListResourcesResponse with resources and their permissions
        """
        logger.info(
            f"========================================\n"
            f"Starting resource listing for user: {user_id}, catalog: {catalog}\n"
            f"========================================"
        )

        errors = []

        # Build user identifier for OpenFGA
        user = build_user_identifier(user_id)
        logger.info(f"OpenFGA user identifier: {user}")

        # Parse Trino catalog name to Lakekeeper warehouse name
        # Trino catalog: "lakekeeper_demo" -> Lakekeeper warehouse: "demo"
        if catalog.startswith("lakekeeper_"):
            warehouse_name = catalog.replace("lakekeeper_", "", 1)
            catalog_name = catalog  # Keep original as catalog_name for OpenFGA
        else:
            # If no prefix, assume catalog is already warehouse name (backward compatibility)
            warehouse_name = catalog
            catalog_name = f"lakekeeper_{catalog}"

        logger.info(
            f"Catalog name parsing:\n"
            f"  - Input (Trino catalog): {catalog}\n"
            f"  - Warehouse name (Lakekeeper): {warehouse_name}\n"
            f"  - Catalog name (OpenFGA): {catalog_name}"
        )

        # Note: We use check_permission instead of list_objects for accuracy
        # This ensures we get all inherited and derived permissions correctly
        logger.info(
            "Using direct permission checks for accurate inheritance resolution"
        )

        # Step 2: Get warehouse_id from catalog config using warehouse_name
        logger.info(
            f"STEP 2: Fetching warehouse config for warehouse: {warehouse_name}"
        )
        warehouse_id = await self.lakekeeper.get_warehouse_config(
            warehouse_name
        )

        if not warehouse_id:
            error_msg = (
                f"Failed to get warehouse_id for warehouse: {warehouse_name}"
            )
            logger.error(error_msg)
            errors.append(
                {
                    "resource": catalog,
                    "error": error_msg,
                }
            )
            return ListResourcesResponse(
                name=catalog_name,
                permissions=[],
                namespaces=None,
                errors=errors,
            )

        logger.info(
            f"\n========================================\n"
            f"Processing warehouse: {warehouse_name}\n"
            f"  - Warehouse ID: {warehouse_id}\n"
            f"  - Catalog name (OpenFGA): {catalog_name}\n"
            f"========================================"
        )

        # Check warehouse permissions directly
        warehouse_object_id = build_fga_catalog_object_id(catalog_name)
        warehouse_permissions = await self._check_permissions(
            user, warehouse_object_id, self.WAREHOUSE_PERMISSIONS
        )
        # Use catalog_name in response (lakekeeper_demo) instead of catalog (demo)
        logger.info(
            f"✓ Warehouse '{catalog_name}' permissions: {warehouse_permissions}"
        )

        # Store warehouse permissions for cascading to children
        # (since OpenFGA parent tuples may not exist)
        inherited_from_warehouse = set(warehouse_permissions)

        # Step 3: Fetch namespaces for this warehouse
        logger.info(f"Fetching namespaces for warehouse: {warehouse_name}")
        namespaces = await self.lakekeeper.get_namespaces(warehouse_id)
        logger.info(
            f"Found {len(namespaces)} namespaces in warehouse '{warehouse_name}'"
        )

        # Build nested structure for namespaces as list
        namespaces_list = []

        # Step 4: Process each namespace
        for ns_idx, namespace_parts in enumerate(namespaces, 1):
            # Namespace is returned as a list of parts, join them
            if not namespace_parts:
                logger.debug(
                    f"  [{ns_idx}/{len(namespaces)}] Skipping empty namespace"
                )
                continue

            namespace_name = (
                ".".join(namespace_parts)
                if isinstance(namespace_parts, list)
                else str(namespace_parts)
            )

            # Build resource path: catalog_name.namespace (use catalog_name for response)
            resource_path = f"{catalog_name}.{namespace_name}"
            logger.info(
                f"\n  [{ns_idx}/{len(namespaces)}] ----------------------------------\n"
                f"  Processing namespace: {resource_path}"
            )

            # Check namespace permissions directly
            namespace_object_id = build_fga_schema_object_id(
                catalog_name, namespace_name
            )
            namespace_permissions_direct = await self._check_permissions(
                user, namespace_object_id, self.NAMESPACE_PERMISSIONS
            )

            # Cascade permissions from warehouse to namespace
            namespace_permissions = list(
                set(namespace_permissions_direct) | inherited_from_warehouse
            )

            logger.info(
                f"  ✓ Namespace '{resource_path}' permissions: {namespace_permissions}"
            )
            if namespace_permissions_direct != namespace_permissions:
                logger.debug(
                    f"    (inherited from warehouse: {list(inherited_from_warehouse - set(namespace_permissions_direct))})"
                )

            # Store for cascading to tables
            inherited_from_namespace = set(namespace_permissions)

            # Build nested structure for tables as list
            tables_list = []

            # Step 5: Fetch tables for this namespace
            try:
                logger.info(
                    f"  Fetching tables for namespace: {namespace_name}"
                )
                tables = await self.lakekeeper.get_tables(
                    warehouse_id, namespace_name
                )
                logger.info(
                    f"  Found {len(tables)} tables in '{resource_path}'"
                )

                # Step 6: Process each table
                for table_idx, table_identifier in enumerate(tables, 1):
                    table_name = table_identifier.get("name")

                    if not table_name:
                        logger.warning(
                            f"    [{table_idx}/{len(tables)}] ✗ Skipping table with missing name: {table_identifier}"
                        )
                        continue

                    # Build resource path: catalog.namespace.table
                    table_resource_path = f"{resource_path}.{table_name}"
                    logger.info(
                        f"    [{table_idx}/{len(tables)}] Processing table: {table_resource_path}"
                    )

                    # Check table permissions directly (no create for tables)
                    table_object_id = build_fga_table_object_id(
                        catalog_name, namespace_name, table_name
                    )
                    table_permissions_direct = await self._check_permissions(
                        user, table_object_id, self.TABLE_PERMISSIONS
                    )

                    # Cascade permissions from namespace to table (excluding 'create')
                    inherited_from_namespace_for_table = (
                        inherited_from_namespace - {"create"}
                    )
                    table_permissions = list(
                        set(table_permissions_direct)
                        | inherited_from_namespace_for_table
                    )

                    if table_permissions_direct != table_permissions:
                        logger.debug(
                            f"      (inherited from parent: {list(inherited_from_namespace_for_table - set(table_permissions_direct))})"
                        )

                    # Fetch table metadata and process columns
                    columns = await self._fetch_and_process_columns(
                        warehouse_id,
                        namespace_name,
                        table_name,
                        catalog_name,
                        user,
                    )

                    # Fetch row filter policies for this table
                    row_filters = await self._fetch_row_filters(
                        catalog_name,
                        namespace_name,
                        table_name,
                        user_id,
                    )

                    # Create TableInfo object and add to tables list
                    tables_list.append(
                        TableInfo(
                            name=table_name,  # Table name only (not FQN)
                            permissions=table_permissions,
                            columns=columns if columns else None,
                            row_filters=row_filters if row_filters else None,
                        )
                    )

                    logger.info(
                        f"    ✓ Table '{table_resource_path}' permissions: {table_permissions}, "
                        f"columns: {len(columns) if columns else 0}, "
                        f"row_filters: {len(row_filters) if row_filters else 0}"
                    )

            except Exception as e:
                error_msg = f"Failed to fetch/process tables: {str(e)}"
                logger.warning(
                    f"  ✗ Error for {resource_path}: {error_msg}",
                    exc_info=True,
                )
                errors.append(
                    {
                        "resource": resource_path,
                        "error": error_msg,
                    }
                )

            # Create NamespaceInfo and add to namespaces list
            namespaces_list.append(
                NamespaceInfo(
                    name=namespace_name,
                    permissions=namespace_permissions,
                    tables=tables_list if tables_list else None,
                )
            )

        logger.info(
            f"\n========================================\n"
            f"✓ Completed listing resources\n"
            f"  - Warehouse: {catalog_name}\n"
            f"  - Namespaces: {len(namespaces_list)}\n"
            f"  - Errors encountered: {len(errors)}\n"
            f"========================================"
        )

        # Return ListResourcesResponse with warehouse info
        return ListResourcesResponse(
            name=catalog_name,
            permissions=warehouse_permissions,
            namespaces=namespaces_list if namespaces_list else None,
            errors=errors if errors else None,
        )

    async def _check_permissions(
        self, user: str, object_id: str, permissions: List[str]
    ) -> List[str]:
        """
        Check which permissions the user has on a specific resource using check_permission.
        This ensures we get all inherited and derived permissions correctly.

        Args:
            user: User identifier (format: "user:userid")
            object_id: OpenFGA object ID (e.g., "warehouse:lakekeeper_demo")
            permissions: List of permissions to check (e.g., ["create", "modify", "select", "describe"])

        Returns:
            List of granted permissions
        """
        granted = []

        for permission in permissions:
            try:
                has_permission = await self.openfga.check_permission(
                    user=user,
                    relation=permission,
                    object_id=object_id,
                )
                if has_permission:
                    granted.append(permission)
            except Exception as e:
                logger.debug(
                    f"Failed to check {permission} on {object_id} for {user}: {e}"
                )

        return granted

    async def _build_permission_cache(self, user: str) -> Dict[str, Set[str]]:
        """
        [DEPRECATED - Not used anymore, kept for reference]
        Build a cache of all permissions for the user using list_objects()

        This is much more efficient than checking each resource individually,
        as it batches all permission checks into 12 API calls instead of
        potentially hundreds.

        Args:
            user: User identifier (format: "user:userid")

        Returns:
            Dictionary mapping permission+type to set of object_ids
            Format: {"{relation}:{object_type}": {object_ids}}
        """
        cache = {}

        logger.info(f"Building permission cache for user: {user}")
        logger.info(f"  Resource types: {self.RESOURCE_TYPES}")
        logger.info(f"  Relations: {self.PERMISSIONS}")

        # For each combination of relation and resource type
        for relation in self.PERMISSIONS:
            for object_type in self.RESOURCE_TYPES:
                cache_key = f"{relation}:{object_type}"

                try:
                    logger.debug(
                        f"  Fetching: user={user}, relation={relation}, type={object_type}"
                    )

                    # Call list_objects to get all objects user has this relation on
                    object_ids = await self.openfga.list_objects(
                        user=user,
                        relation=relation,
                        object_type=object_type,
                    )

                    # Convert list to set for O(1) lookup
                    cache[cache_key] = set(object_ids)

                    logger.info(f"  ✓ {cache_key}: {len(object_ids)} objects")

                    if object_ids and len(object_ids) <= 10:
                        logger.debug(f"    Objects: {object_ids}")

                except Exception as e:
                    logger.warning(f"  ✗ Failed to fetch {cache_key}: {e}")
                    cache[cache_key] = set()

        return cache

    def _get_permissions_from_cache(
        self, object_id: str, cache: Dict[str, Set[str]]
    ) -> List[str]:
        """
        Get all permissions for an object from the pre-built cache

        Args:
            object_id: OpenFGA object ID (e.g., "warehouse:lakekeeper_demo")
            cache: Permission cache from _build_permission_cache()

        Returns:
            List of granted permissions
        """
        granted = []

        # Extract object type from object_id
        # Format: "type:id" -> type
        object_type = object_id.split(":", 1)[0] if ":" in object_id else None

        if not object_type:
            logger.warning(f"Cannot extract object type from: {object_id}")
            return granted

        # Check each permission
        for relation in self.PERMISSIONS:
            cache_key = f"{relation}:{object_type}"

            # Check if object_id is in the cached set for this permission
            if object_id in cache.get(cache_key, set()):
                granted.append(relation)

        return granted

    async def _fetch_and_process_columns(
        self,
        warehouse_id: str,
        namespace_name: str,
        table_name: str,
        catalog_name: str,
        user: str,
    ) -> List[ColumnInfo]:
        """
        Fetch table metadata and process columns with mask information

        Args:
            warehouse_id: Warehouse UUID
            namespace_name: Namespace name
            table_name: Table name
            catalog_name: Catalog name (for OpenFGA object ID)
            user: User identifier for permission checks

        Returns:
            List of ColumnInfo objects, or empty list if metadata unavailable
        """
        try:
            # Fetch table metadata from Lakekeeper
            table_metadata = await self.lakekeeper.get_table_metadata(
                warehouse_id, namespace_name, table_name
            )

            if not table_metadata:
                logger.debug(
                    f"      No metadata available for {namespace_name}.{table_name}"
                )
                return []

            # Extract schemas from metadata
            metadata = table_metadata.get("metadata", {})
            schemas = metadata.get("schemas", [])

            if not schemas:
                logger.debug(
                    f"      No schemas found in metadata for {namespace_name}.{table_name}"
                )
                return []

            # Get the latest schema (usually the first one or with highest schema-id)
            # For simplicity, use the first schema
            schema = schemas[0]
            fields = schema.get("fields", [])

            if not fields:
                logger.debug(
                    f"      No fields found in schema for {namespace_name}.{table_name}"
                )
                return []

            logger.debug(
                f"      Processing {len(fields)} columns for {namespace_name}.{table_name}"
            )

            # Process each column
            columns = []
            for field in fields:
                column_name = field.get("name")

                if not column_name:
                    logger.warning(
                        f"        Skipping field with no name: {field}"
                    )
                    continue

                # Build column object ID for OpenFGA
                column_object_id = build_fga_column_object_id(
                    catalog_name, namespace_name, table_name, column_name
                )

                # Check if user has mask permission on this column
                has_mask = await self.openfga.check_permission(
                    user=user,
                    relation="mask",
                    object_id=column_object_id,
                )

                columns.append(
                    ColumnInfo(
                        name=column_name,
                        masked=has_mask,
                    )
                )

            logger.debug(
                f"      ✓ Processed {len(columns)} columns, "
                f"{sum(1 for c in columns if c.masked)} masked"
            )
            return columns

        except Exception as e:
            logger.warning(
                f"      ✗ Failed to fetch/process columns for {namespace_name}.{table_name}: {e}",
                exc_info=True,
            )
            return []

    async def _fetch_row_filters(
        self,
        catalog_name: str,
        namespace_name: str,
        table_name: str,
        user_id: str,
    ) -> List[RowFilterInfo]:
        """
        Fetch row filter policies for a table that user has access to

        Args:
            catalog_name: Catalog name (for OpenFGA object ID)
            namespace_name: Namespace name
            table_name: Table name
            user_id: User identifier (can be with or without "user:" prefix)

        Returns:
            List of RowFilterInfo objects, or empty list if no filters
        """
        try:
            # Build table FQN for OpenFGA
            table_fqn = f"{catalog_name}.{namespace_name}.{table_name}"

            # Strip "user:" prefix if present, since get_user_policy_filters expects raw user_id
            raw_user_id = (
                user_id.replace("user:", "")
                if user_id.startswith("user:")
                else user_id
            )

            logger.debug(
                f"      Fetching row filters for {table_fqn}, user={raw_user_id}"
            )

            # Create RowFilterService instance
            row_filter_service = RowFilterService(self.openfga)

            # Get all policies for this table
            policy_ids = await row_filter_service.get_table_policies(table_fqn)

            if not policy_ids:
                logger.debug(f"      No row filter policies for {table_fqn}")
                return []

            logger.debug(
                f"      Found {len(policy_ids)} row filter policies for {table_fqn}"
            )

            # Get user's filters (policies that user has access to)
            # Note: tenant_id is None here since we don't have tenant context in list-resources
            filters = await row_filter_service.get_user_policy_filters(
                raw_user_id, policy_ids, tenant_id=None
            )

            if not filters:
                logger.debug(
                    f"      User {raw_user_id} has no access to row filter policies for {table_fqn}"
                )
                return []

            # Build RowFilterInfo objects
            row_filters = []
            for f in filters:
                attribute_name = f["attribute_name"]
                allowed_values = f["allowed_values"]

                # Check for wildcard
                if "*" in allowed_values:
                    # Wildcard means no filter
                    logger.debug(
                        f"      Skipping wildcard filter for attribute {attribute_name}"
                    )
                    continue

                # Build SQL filter expression
                values = [escape_sql_value(v) for v in allowed_values]
                values_str = "', '".join(values)
                filter_expression = f"{attribute_name} IN ('{values_str}')"

                row_filters.append(
                    RowFilterInfo(
                        attribute_name=attribute_name,
                        filter_expression=filter_expression,
                    )
                )

            logger.debug(
                f"      ✓ User {raw_user_id} has {len(row_filters)} row filters for {table_fqn}"
            )
            return row_filters

        except Exception as e:
            logger.warning(
                f"      ✗ Failed to fetch row filters for {namespace_name}.{table_name}: {e}",
                exc_info=True,
            )
            return []
