"""
Build OpenFGA object identifiers from resource specifications
"""

from typing import Optional

from app.core.constants import (
    OBJECT_TYPE_CATALOG,
    OBJECT_TYPE_COLUMN,
    OBJECT_TYPE_NAMESPACE,
    OBJECT_TYPE_TABLE,
    SYSTEM_CATALOG,
)


def build_object_id_from_resource(
    resource: dict, operation: str
) -> Optional[str]:
    """
    Build OpenFGA object_id directly from the request resource payload.

    This function intentionally does NOT resolve resources via Lakekeeper DB.
    It only uses the textual identifiers coming from the caller.

    Request body fields: catalog, schema, table
    OpenFGA object_id format:
    - Catalog:  catalog:<catalog_name>
    - Namespace: namespace:<catalog>.<schema_name> (requires catalog)
    - Table: table:<catalog>.<schema_name>.<table_name> (requires catalog and schema)

    Special operations:
    - CreateCatalog: Requires catalog name in resource (or can be empty for grant)
    - CreateSchema: Requires catalog in resource
    - CreateTable: Requires catalog and schema in resource

    Args:
        resource: Resource dictionary with keys: catalog, schema, table
        operation: Operation name (e.g., "CreateCatalog", "CreateSchema", "CreateTable")

    Returns:
        OpenFGA object_id string or None if cannot build
    """
    # Support both catalog_name/catalog and schema_name/schema for backward compatibility
    catalog_name = resource.get("catalog_name") or resource.get("catalog")
    schema_name = resource.get("schema_name") or resource.get("schema")
    table_name = resource.get("table_name") or resource.get("table")
    column_name = resource.get("column_name") or resource.get("column")

    # Special case: CreateCatalog
    if operation == "CreateCatalog":
        return f"{OBJECT_TYPE_CATALOG}:{SYSTEM_CATALOG}"

    # Special case: CreateSchema
    if operation == "CreateSchema":
        if not catalog_name:
            return None
        return f"{OBJECT_TYPE_CATALOG}:{catalog_name}"

    # Special case: CreateTable
    if operation == "CreateTable":
        if not catalog_name or not schema_name:
            return None
        return f"{OBJECT_TYPE_NAMESPACE}:{catalog_name}.{schema_name}"

    # Column-level masking
    if column_name:
        if not (catalog_name and schema_name and table_name):
            return None
        return f"{OBJECT_TYPE_COLUMN}:{catalog_name}.{schema_name}.{table_name}.{column_name}"

    # Generic mapping by priority: catalog (standalone) > table > namespace
    if catalog_name and not schema_name and not table_name:
        return f"{OBJECT_TYPE_CATALOG}:{catalog_name}"

    if table_name and schema_name:
        if not catalog_name:
            return None
        return f"{OBJECT_TYPE_TABLE}:{catalog_name}.{schema_name}.{table_name}"

    if schema_name:
        if not catalog_name:
            return None
        return f"{OBJECT_TYPE_NAMESPACE}:{catalog_name}.{schema_name}"

    return None

