"""
Application constants
"""

# =============================================================================
# API Object Type Prefixes
# These are used in the API layer (request/response) and service logic
# =============================================================================
OBJECT_TYPE_CATALOG = "catalog"
OBJECT_TYPE_SCHEMA = "schema"
OBJECT_TYPE_TABLE = "table"
OBJECT_TYPE_COLUMN = "column"
OBJECT_TYPE_ROLE = "role"
OBJECT_TYPE_PROJECT = "project"

# =============================================================================
# OpenFGA v3 Object Type Prefixes
# These are the actual types used in OpenFGA v3 model
# Mapping: catalog -> warehouse, schema -> namespace, table -> lakekeeper_table
# =============================================================================
FGA_TYPE_WAREHOUSE = "warehouse"
FGA_TYPE_NAMESPACE = "namespace"
FGA_TYPE_LAKEKEEPER_TABLE = "lakekeeper_table"
FGA_TYPE_COLUMN = "column"

# =============================================================================
# Other Constants
# =============================================================================

# OpenFGA user type prefix
USER_TYPE_PREFIX = "user"

# Special catalog for system-level permissions
SYSTEM_CATALOG = "system"

# Special row filter policy type
FGA_TYPE_ROW_FILTER_POLICY = "row_filter_policy"
