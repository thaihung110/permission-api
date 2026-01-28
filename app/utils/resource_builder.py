"""
Utility functions for building OpenFGA resource identifiers

This module builds resource identifiers in API format (catalog/schema/table).
For OpenFGA v3 communication, use build_fga_resource_identifiers() which
automatically converts to FGA format (warehouse/namespace/lakekeeper_table).
"""

from typing import Optional, Tuple, Union

from app.core.constants import (
    OBJECT_TYPE_CATALOG,
    OBJECT_TYPE_COLUMN,
    OBJECT_TYPE_PROJECT,
    OBJECT_TYPE_ROLE,
    OBJECT_TYPE_SCHEMA,
    OBJECT_TYPE_TABLE,
    SYSTEM_CATALOG,
)
from app.utils.type_mapper import convert_resource_identifiers_to_fga


def _extract_resource_fields(
    resource: Union[dict, object],
) -> Tuple[
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
]:
    """
    Extract resource fields handling both dict and object types.

    Args:
        resource: Resource as dict or Pydantic model

    Returns:
        Tuple of (catalog_name, schema_name, table_name, column_name, role_name, project_name)
    """
    # Handle dict type
    if isinstance(resource, dict):
        catalog_name = resource.get("catalog_name") or resource.get("catalog")
        schema_name = resource.get("schema_name") or resource.get("schema")
        table_name = resource.get("table_name") or resource.get("table")
        column_name = resource.get("column_name") or resource.get("column")
        role_name = resource.get("role_name") or resource.get("role")
        project_name = resource.get("project_name") or resource.get("project")
    else:
        # Handle object type (Pydantic model)
        catalog_name = getattr(resource, "catalog", None)
        schema_name = getattr(resource, "schema", None)
        table_name = getattr(resource, "table", None)
        column_name = getattr(resource, "column", None)
        role_name = getattr(resource, "role", None)
        project_name = getattr(resource, "project", None)

    return (
        catalog_name,
        schema_name,
        table_name,
        column_name,
        role_name,
        project_name,
    )


def build_resource_identifiers(
    resource: Union[dict, object],
    operation_or_relation: str,
    raise_on_error: bool = False,
) -> Optional[Tuple[str, str, str]]:
    """
    Build OpenFGA resource identifiers (object_id, resource_type, resource_id).

    Unified function that handles both dict and Pydantic model inputs,
    and can be used for both permission checking and granting.

    This function intentionally does NOT resolve resources via Lakekeeper DB.
    It only uses the textual identifiers coming from the caller.

    Request body fields: catalog, schema, table, column
    OpenFGA object_id format:
    - Catalog:  catalog:<catalog_name>
    - Schema: schema:<catalog>.<schema_name> (requires catalog)
    - Table: table:<catalog>.<schema_name>.<table_name> (requires catalog and schema)
    - Column: column:<catalog>.<schema>.<table>.<column> (requires all)

    Special operations/relations:
    - CreateCatalog / create (no resource): Grants on catalog:system
    - CreateSchema / create (catalog only): Authorizes on catalog:<catalog>
    - CreateTable / create (catalog+schema): Authorizes on schema:<catalog>.<schema>

    Args:
        resource: Resource specification (dict or Pydantic model)
        operation_or_relation: Operation name (e.g., "CreateCatalog") or relation (e.g., "create")
        raise_on_error: If True, raise ValueError on invalid resource; if False, return None

    Returns:
        Tuple of (object_id, resource_type, resource_id) or None if cannot build

    Raises:
        ValueError: If raise_on_error=True and resource specification is invalid
    """
    (
        catalog_name,
        schema_name,
        table_name,
        column_name,
        role_name,
        project_name,
    ) = _extract_resource_fields(resource)

    # Project-level permissions
    if project_name:
        object_id = f"{OBJECT_TYPE_PROJECT}:{project_name}"
        resource_type = OBJECT_TYPE_PROJECT
        resource_id = project_name
        return object_id, resource_type, resource_id

    # Role-level permissions: if role is specified, use role:<role_name>
    # This takes priority over other resource types
    if role_name:
        object_id = f"{OBJECT_TYPE_ROLE}:{role_name}"
        resource_type = OBJECT_TYPE_ROLE
        resource_id = role_name
        return object_id, resource_type, resource_id

    # Special case: CreateCatalog or create relation with no resource
    # For grant: resource can be empty, grant on catalog:system
    # For check: always check on catalog:system (where permission was granted for CreateCatalog)
    if operation_or_relation == "CreateCatalog" or (
        operation_or_relation == "create"
        and not catalog_name
        and not schema_name
        and not table_name
    ):
        # Always use catalog:system for CreateCatalog permission
        object_id = f"{OBJECT_TYPE_CATALOG}:{SYSTEM_CATALOG}"
        resource_type = OBJECT_TYPE_CATALOG
        resource_id = SYSTEM_CATALOG
        return object_id, resource_type, resource_id

    # Special case: CreateSchema (Trino schema == Lakekeeper schema parented by catalog)
    # Requires catalog in resource. Schema does not exist yet, so we authorize on the catalog object.
    if operation_or_relation == "CreateSchema":
        if not catalog_name:
            if raise_on_error:
                raise ValueError(
                    "CreateSchema requires catalog in resource. "
                    'Example: {"catalog": "lakekeeper"}'
                )
            return None
        object_id = f"{OBJECT_TYPE_CATALOG}:{catalog_name}"
        resource_type = OBJECT_TYPE_CATALOG
        resource_id = catalog_name
        return object_id, resource_type, resource_id

    # Special case: CreateTable is controlled at the schema level
    # Requires catalog and schema in resource. The table does not exist yet,
    # so we check the `create` relation on schema.
    if operation_or_relation == "CreateTable":
        if not catalog_name or not schema_name:
            if raise_on_error:
                raise ValueError(
                    "CreateTable requires catalog and schema in resource. "
                    'Example: {"catalog": "lakekeeper", "schema": "finance"}'
                )
            return None
        object_id = f"{OBJECT_TYPE_SCHEMA}:{catalog_name}.{schema_name}"
        resource_type = OBJECT_TYPE_SCHEMA
        resource_id = f"{catalog_name}.{schema_name}"
        return object_id, resource_type, resource_id

    # Column-level permissions: requires catalog, schema, table, and column
    # NOTE: Column identifiers are built here, but in check_permission:
    # - 'mask' relation is checked at column level (column-specific)
    # - All other relations (select, describe, modify) are redirected to table level
    #   because columns inherit these permissions from their parent table in FGA model
    if column_name:
        if not (catalog_name and schema_name and table_name):
            if raise_on_error:
                raise ValueError(
                    "Column-level permission requires catalog, schema, table, and column. "
                    'Example: {"catalog": "lakekeeper", "schema": "finance", "table": "user", "column": "email"}'
                )
            return None
        object_id = f"{OBJECT_TYPE_COLUMN}:{catalog_name}.{schema_name}.{table_name}.{column_name}"
        resource_type = OBJECT_TYPE_COLUMN
        resource_id = f"{catalog_name}.{schema_name}.{table_name}.{column_name}"
        return object_id, resource_type, resource_id

    # Generic mapping by priority: catalog (standalone) > table > schema

    # Catalog-level access (standalone - no schema or table)
    if catalog_name and not schema_name and not table_name:
        object_id = f"{OBJECT_TYPE_CATALOG}:{catalog_name}"
        resource_type = OBJECT_TYPE_CATALOG
        resource_id = catalog_name
        return object_id, resource_type, resource_id

    # Table-level permission (requires catalog and schema)
    if table_name and schema_name:
        if not catalog_name:
            if raise_on_error:
                raise ValueError(
                    "Table-level permission requires catalog, schema, and table. "
                    'Example: {"catalog": "lakekeeper", "schema": "finance", "table": "user"}'
                )
            return None
        object_id = (
            f"{OBJECT_TYPE_TABLE}:{catalog_name}.{schema_name}.{table_name}"
        )
        resource_type = OBJECT_TYPE_TABLE
        resource_id = f"{catalog_name}.{schema_name}.{table_name}"
        return object_id, resource_type, resource_id

    # Schema-level permission (requires catalog)
    if schema_name:
        if not catalog_name:
            if raise_on_error:
                raise ValueError(
                    "Schema-level permission requires catalog and schema. "
                    'Example: {"catalog": "lakekeeper", "schema": "finance"}'
                )
            return None
        object_id = f"{OBJECT_TYPE_SCHEMA}:{catalog_name}.{schema_name}"
        resource_type = OBJECT_TYPE_SCHEMA
        resource_id = f"{catalog_name}.{schema_name}"
        return object_id, resource_type, resource_id

    # If we reach here, we don't have enough information to build identifiers
    if raise_on_error:
        raise ValueError(
            "Resource must specify at least one of: catalog (standalone), "
            "schema (with catalog), table (with catalog and schema), or column (with all)."
        )
    return None


def build_object_id_from_resource(
    resource: dict, operation: str
) -> Optional[str]:
    """
    Build OpenFGA object_id directly from the request resource payload.

    DEPRECATED: Use build_resource_identifiers() instead for consistency.
    This function is kept for backward compatibility.

    Args:
        resource: Resource dictionary with keys: catalog, schema, table
        operation: Operation name (e.g., "CreateCatalog", "CreateSchema", "CreateTable")

    Returns:
        OpenFGA object_id string or None if cannot build
    """
    result = build_resource_identifiers(
        resource, operation, raise_on_error=False
    )
    if result:
        return result[0]  # Return only object_id
    return None


def build_fga_resource_identifiers(
    resource: Union[dict, object],
    operation_or_relation: str,
    raise_on_error: bool = False,
) -> Optional[Tuple[str, str, str]]:
    """
    Build OpenFGA v3 resource identifiers for FGA communication.

    This is a wrapper around build_resource_identifiers() that automatically
    converts the result to OpenFGA v3 format:
    - catalog -> warehouse
    - schema -> namespace
    - table -> lakekeeper_table
    - column -> column (unchanged)

    Use this function when you need to write/read tuples from OpenFGA.

    Args:
        resource: Resource specification (dict or Pydantic model)
        operation_or_relation: Operation name or relation
        raise_on_error: If True, raise ValueError on invalid resource

    Returns:
        Tuple of (fga_object_id, fga_resource_type, resource_id) or None

    Example:
        # API format: ("catalog:lakekeeper", "catalog", "lakekeeper")
        # FGA format: ("warehouse:lakekeeper", "warehouse", "lakekeeper")
    """
    result = build_resource_identifiers(
        resource, operation_or_relation, raise_on_error
    )
    if result is None:
        return None

    api_object_id, api_resource_type, resource_id = result
    return convert_resource_identifiers_to_fga(
        api_object_id, api_resource_type, resource_id
    )
