"""
Utility functions for building OpenFGA resource identifiers
"""

from typing import Optional


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
    # For grant: resource can be empty, grant on catalog:system
    # For check: always check on catalog:system (where permission was granted for CreateCatalog)
    # Note: When granting CreateCatalog permission with empty resource, we grant on catalog:system
    #       So when checking CreateCatalog, we should always check on catalog:system regardless of catalog name
    if operation == "CreateCatalog":
        # Always check on catalog:system where CreateCatalog permission was granted
        return "catalog:system"

    # Special case: CreateSchema (Trino schema == Lakekeeper namespace parented by catalog).
    # Requires catalog in resource. Namespace does not exist yet, so we authorize on the catalog object.
    if operation == "CreateSchema":
        if not catalog_name:
            return None  # Catalog is required
        return f"catalog:{catalog_name}"

    # Special case: CreateTable is controlled at the namespace level.
    # Requires catalog and schema in resource. The table does not exist yet,
    # so we check the `create` relation on namespace.
    if operation == "CreateTable":
        if not catalog_name or not schema_name:
            return None  # Both catalog and schema are required
        return f"namespace:{catalog_name}.{schema_name}"

    # Column-level masking: requires catalog, schema, table, and column
    if column_name:
        if not (catalog_name and schema_name and table_name):
            return None  # Column requires catalog, schema, and table
        return f"column:{catalog_name}.{schema_name}.{table_name}.{column_name}"

    # Generic mapping by priority: catalog (standalone) > table > namespace
    if catalog_name and not schema_name and not table_name:
        # Catalog-level access
        return f"catalog:{catalog_name}"

    if table_name and schema_name:
        if not catalog_name:
            return None  # Catalog is required for table
        return f"table:{catalog_name}.{schema_name}.{table_name}"

    if schema_name:
        if not catalog_name:
            return None  # Catalog is required for namespace
        return f"namespace:{catalog_name}.{schema_name}"

    # If we reach here, we don't have enough information to build an object_id.
    return None
