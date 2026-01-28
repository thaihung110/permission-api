"""
Type Mapper for OpenFGA v3 Model

This module handles the mapping between API (Trino) types and OpenFGA v3 types.

API (Trino) types:
- catalog
- schema
- table
- column

OpenFGA v3 types:
- warehouse (was catalog)
- namespace (was schema)
- lakekeeper_table (was table)
- column (unchanged)

The mapping is performed bidirectionally:
- API -> OpenFGA: When writing/reading tuples to/from OpenFGA
- OpenFGA -> API: When returning results to API consumers
"""

from typing import Optional, Tuple

# =============================================================================
# Type Mapping Constants
# =============================================================================

# API types (used in service layer and API endpoints)
API_TYPE_CATALOG = "catalog"
API_TYPE_SCHEMA = "schema"
API_TYPE_TABLE = "table"
API_TYPE_COLUMN = "column"
API_TYPE_PROJECT = "project"

# OpenFGA v3 types (used in OpenFGA tuples)
FGA_TYPE_WAREHOUSE = "warehouse"
FGA_TYPE_PROJECT = "project"  # Added project type
FGA_TYPE_NAMESPACE = "namespace"
FGA_TYPE_LAKEKEEPER_TABLE = "lakekeeper_table"
FGA_TYPE_COLUMN = "column"

# Special constants
SYSTEM_CATALOG = "system"
FGA_SYSTEM_WAREHOUSE = "system"
FGA_SYSTEM_PROJECT = (
    "00000000-0000-0000-0000-000000000000"  # Default project ID
)

# =============================================================================
# Mapping Dictionaries
# =============================================================================

# API type -> OpenFGA type mapping
API_TO_FGA_TYPE_MAP = {
    API_TYPE_CATALOG: FGA_TYPE_WAREHOUSE,
    API_TYPE_SCHEMA: FGA_TYPE_NAMESPACE,
    API_TYPE_TABLE: FGA_TYPE_LAKEKEEPER_TABLE,
    API_TYPE_COLUMN: FGA_TYPE_COLUMN,
    API_TYPE_PROJECT: FGA_TYPE_PROJECT,
}

# OpenFGA type -> API type mapping (reverse)
FGA_TO_API_TYPE_MAP = {
    FGA_TYPE_WAREHOUSE: API_TYPE_CATALOG,
    FGA_TYPE_NAMESPACE: API_TYPE_SCHEMA,
    FGA_TYPE_LAKEKEEPER_TABLE: API_TYPE_TABLE,
    FGA_TYPE_COLUMN: API_TYPE_COLUMN,
    FGA_TYPE_PROJECT: API_TYPE_PROJECT,
}


# =============================================================================
# Type Conversion Functions
# =============================================================================


def api_type_to_fga_type(api_type: str) -> str:
    """
    Convert API type to OpenFGA v3 type.

    Args:
        api_type: API/Trino type (e.g., "catalog", "schema", "table")

    Returns:
        OpenFGA v3 type (e.g., "warehouse", "namespace", "lakekeeper_table")
    """
    return API_TO_FGA_TYPE_MAP.get(api_type, api_type)


def fga_type_to_api_type(fga_type: str) -> str:
    """
    Convert OpenFGA v3 type to API type.

    Args:
        fga_type: OpenFGA v3 type (e.g., "warehouse", "namespace", "lakekeeper_table")

    Returns:
        API/Trino type (e.g., "catalog", "schema", "table")
    """
    return FGA_TO_API_TYPE_MAP.get(fga_type, fga_type)


# =============================================================================
# Object ID Conversion Functions
# =============================================================================


def api_object_id_to_fga(api_object_id: str) -> str:
    """
    Convert API object_id to OpenFGA v3 object_id.

    Handles the type prefix conversion:
    - "catalog:my_catalog" -> "warehouse:my_catalog"
    - "schema:my_catalog.my_schema" -> "namespace:my_catalog.my_schema"
    - "table:my_catalog.my_schema.my_table" -> "lakekeeper_table:my_catalog.my_schema.my_table"
    - "project:my_project" -> "project:my_project" (unchanged)
    - "column:..." -> "column:..." (unchanged)

    Args:
        api_object_id: API-style object_id (e.g., "catalog:lakekeeper")

    Returns:
        OpenFGA v3 object_id (e.g., "warehouse:lakekeeper")
    """
    if not api_object_id or ":" not in api_object_id:
        return api_object_id

    type_part, id_part = api_object_id.split(":", 1)
    fga_type = api_type_to_fga_type(type_part)
    return f"{fga_type}:{id_part}"


def fga_object_id_to_api(fga_object_id: str) -> str:
    """
    Convert OpenFGA v3 object_id to API object_id.

    Handles the type prefix conversion:
    - "warehouse:my_catalog" -> "catalog:my_catalog"
    - "namespace:my_catalog.my_schema" -> "schema:my_catalog.my_schema"
    - "lakekeeper_table:my_catalog.my_schema.my_table" -> "table:my_catalog.my_schema.my_table"
    - "project:my_project" -> "project:my_project" (unchanged)
    - "column:..." -> "column:..." (unchanged)

    Args:
        fga_object_id: OpenFGA v3 object_id (e.g., "warehouse:lakekeeper")

    Returns:
        API-style object_id (e.g., "catalog:lakekeeper")
    """
    if not fga_object_id or ":" not in fga_object_id:
        return fga_object_id

    type_part, id_part = fga_object_id.split(":", 1)
    api_type = fga_type_to_api_type(type_part)
    return f"{api_type}:{id_part}"


def parse_object_id(object_id: str) -> Tuple[str, str]:
    """
    Parse an object_id into type and id parts.

    Args:
        object_id: Object ID (e.g., "catalog:lakekeeper")

    Returns:
        Tuple of (type, id)
    """
    if not object_id or ":" not in object_id:
        return ("", object_id or "")

    parts = object_id.split(":", 1)
    return (parts[0], parts[1] if len(parts) > 1 else "")


# =============================================================================
# Resource Identifier Conversion
# =============================================================================


def convert_resource_identifiers_to_fga(
    object_id: str, resource_type: str, resource_id: str
) -> Tuple[str, str, str]:
    """
    Convert API resource identifiers to OpenFGA v3 format.

    Args:
        object_id: API-style object_id (e.g., "catalog:lakekeeper")
        resource_type: API resource type (e.g., "catalog")
        resource_id: Resource ID (unchanged)

    Returns:
        Tuple of (fga_object_id, fga_resource_type, resource_id)
    """
    fga_object_id = api_object_id_to_fga(object_id)
    fga_resource_type = api_type_to_fga_type(resource_type)
    return (fga_object_id, fga_resource_type, resource_id)


def convert_resource_identifiers_from_fga(
    fga_object_id: str, fga_resource_type: str, resource_id: str
) -> Tuple[str, str, str]:
    """
    Convert OpenFGA v3 resource identifiers to API format.

    Args:
        fga_object_id: OpenFGA v3 object_id (e.g., "warehouse:lakekeeper")
        fga_resource_type: OpenFGA resource type (e.g., "warehouse")
        resource_id: Resource ID (unchanged)

    Returns:
        Tuple of (api_object_id, api_resource_type, resource_id)
    """
    api_object_id = fga_object_id_to_api(fga_object_id)
    api_resource_type = fga_type_to_api_type(fga_resource_type)
    return (api_object_id, api_resource_type, resource_id)


# =============================================================================
# Hierarchical Object ID Building (for permission checks)
# =============================================================================


def build_fga_catalog_object_id(catalog_name: str) -> str:
    """
    Build OpenFGA v3 warehouse object_id from catalog name.

    Args:
        catalog_name: Catalog name (e.g., "lakekeeper")

    Returns:
        OpenFGA object_id (e.g., "warehouse:lakekeeper")
    """
    return f"{FGA_TYPE_WAREHOUSE}:{catalog_name}"


def build_fga_project_object_id(project_name: str) -> str:
    """
    Build OpenFGA v3 project object_id from project name.

    Args:
        project_name: Project name (e.g., "lakekeeper")

    Returns:
        OpenFGA object_id (e.g., "project:lakekeeper")
    """
    return f"{FGA_TYPE_PROJECT}:{project_name}"


def build_fga_schema_object_id(catalog_name: str, schema_name: str) -> str:
    """
    Build OpenFGA v3 namespace object_id from catalog and schema names.

    Args:
        catalog_name: Catalog name (e.g., "lakekeeper")
        schema_name: Schema name (e.g., "finance")

    Returns:
        OpenFGA object_id (e.g., "namespace:lakekeeper.finance")
    """
    return f"{FGA_TYPE_NAMESPACE}:{catalog_name}.{schema_name}"


def build_fga_table_object_id(
    catalog_name: str, schema_name: str, table_name: str
) -> str:
    """
    Build OpenFGA v3 lakekeeper_table object_id from catalog, schema, and table names.

    Args:
        catalog_name: Catalog name (e.g., "lakekeeper")
        schema_name: Schema name (e.g., "finance")
        table_name: Table name (e.g., "user")

    Returns:
        OpenFGA object_id (e.g., "lakekeeper_table:lakekeeper.finance.user")
    """
    return (
        f"{FGA_TYPE_LAKEKEEPER_TABLE}:{catalog_name}.{schema_name}.{table_name}"
    )


def build_fga_column_object_id(
    catalog_name: str, schema_name: str, table_name: str, column_name: str
) -> str:
    """
    Build OpenFGA v3 column object_id.

    Args:
        catalog_name: Catalog name
        schema_name: Schema name
        table_name: Table name
        column_name: Column name

    Returns:
        OpenFGA object_id (e.g., "column:lakekeeper.finance.user.email")
    """
    return f"{FGA_TYPE_COLUMN}:{catalog_name}.{schema_name}.{table_name}.{column_name}"
