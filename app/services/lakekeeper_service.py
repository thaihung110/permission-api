"""
Lakekeeper service - Business logic for listing resources with permissions
"""

import logging
from typing import Any, Dict, List, Set

from app.external.lakekeeper_client import LakekeeperClient
from app.external.openfga_client import OpenFGAManager
from app.schemas.lakekeeper import ListResourcesResponse
from app.utils.operation_mapper import build_user_identifier
from app.utils.type_mapper import (
    FGA_TYPE_LAKEKEEPER_TABLE,
    FGA_TYPE_NAMESPACE,
    FGA_TYPE_WAREHOUSE,
    build_fga_catalog_object_id,
    build_fga_schema_object_id,
    build_fga_table_object_id,
)

logger = logging.getLogger(__name__)


class LakekeeperService:
    """Service for handling Lakekeeper resource operations"""

    # Permissions to check for each resource
    PERMISSIONS = ["create", "modify", "select", "describe"]

    # OpenFGA resource types
    RESOURCE_TYPES = [
        FGA_TYPE_WAREHOUSE,
        FGA_TYPE_NAMESPACE,
        FGA_TYPE_LAKEKEEPER_TABLE,
    ]

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
            catalog: Warehouse name (catalog name) to list resources for

        Returns:
            ListResourcesResponse with resources and their permissions
        """
        logger.info(
            f"========================================\n"
            f"Starting resource listing for user: {user_id}, catalog: {catalog}\n"
            f"========================================"
        )

        resources = {}
        errors = []

        # Build user identifier for OpenFGA
        user = build_user_identifier(user_id)
        logger.info(f"OpenFGA user identifier: {user}")

        # Step 1: Pre-fetch all permissions from OpenFGA using list_objects()
        # This is much more efficient than checking each resource individually
        logger.info("STEP 1: Pre-fetching all permissions from OpenFGA...")
        permission_cache = await self._build_permission_cache(user)

        total_permissions = sum(
            len(objects) for objects in permission_cache.values()
        )
        logger.info(
            f"✓ Built permission cache with {total_permissions} total object permissions"
        )

        # Step 2: Get warehouse_id from catalog config
        logger.info(f"STEP 2: Fetching warehouse config for catalog: {catalog}")
        warehouse_id = await self.lakekeeper.get_warehouse_config(catalog)

        if not warehouse_id:
            error_msg = f"Failed to get warehouse_id for catalog: {catalog}"
            logger.error(error_msg)
            errors.append(
                {
                    "resource": catalog,
                    "error": error_msg,
                }
            )
            return ListResourcesResponse(
                resources=resources,
                errors=errors if errors else None,
            )

        logger.info(
            f"\n========================================\n"
            f"Processing catalog: {catalog}\n"
            f"  - Warehouse ID: {warehouse_id}\n"
            f"========================================"
        )

        # Map catalog to catalog name: "lakekeeper_" + catalog
        catalog_name = f"lakekeeper_{catalog}"
        logger.info(f"Catalog name mapping: {catalog} → {catalog_name}")

        # Get warehouse permissions from cache
        warehouse_object_id = build_fga_catalog_object_id(catalog_name)
        warehouse_permissions = self._get_permissions_from_cache(
            warehouse_object_id, permission_cache
        )
        # Use catalog_name in response (lakekeeper_demo) instead of catalog (demo)
        resources[catalog_name] = warehouse_permissions
        logger.info(
            f"✓ Warehouse '{catalog_name}' permissions: {warehouse_permissions}"
        )

        # Step 3: Fetch namespaces for this warehouse
        logger.info(f"Fetching namespaces for catalog: {catalog}")
        namespaces = await self.lakekeeper.get_namespaces(warehouse_id)
        logger.info(
            f"Found {len(namespaces)} namespaces in catalog '{catalog}'"
        )

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

            # Get namespace permissions from cache
            namespace_object_id = build_fga_schema_object_id(
                catalog_name, namespace_name
            )
            namespace_permissions = self._get_permissions_from_cache(
                namespace_object_id, permission_cache
            )
            resources[resource_path] = namespace_permissions
            logger.info(
                f"  ✓ Namespace '{resource_path}' permissions: {namespace_permissions}"
            )

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

                    # Get table permissions from cache
                    table_object_id = build_fga_table_object_id(
                        catalog_name, namespace_name, table_name
                    )
                    table_permissions = self._get_permissions_from_cache(
                        table_object_id, permission_cache
                    )
                    resources[table_resource_path] = table_permissions
                    logger.info(
                        f"    ✓ Table '{table_resource_path}' permissions: {table_permissions}"
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

        logger.info(
            f"\n========================================\n"
            f"✓ Completed listing resources\n"
            f"  - Total resources: {len(resources)}\n"
            f"  - Errors encountered: {len(errors)}\n"
            f"========================================"
        )

        return ListResourcesResponse(
            resources=resources,
            errors=errors if errors else None,
        )

    async def _build_permission_cache(self, user: str) -> Dict[str, Set[str]]:
        """
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
