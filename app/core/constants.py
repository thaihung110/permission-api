"""
Application constants
"""

# Operation to relation mapping for OpenFGA
OPERATION_TO_RELATION_MAP = {
    # Catalog operations (Trino catalogs)
    "AccessCatalog": "select",
    "ShowCatalogs": "describe",
    "CreateCatalog": "create",
    "DropCatalog": "modify",
    "FilterCatalogs": "describe",
    # Namespace operations
    "ShowSchemas": "describe",
    "CreateSchema": "create",
    "DropSchema": "modify",
    "RenameSchema": "modify",
    "SetSchemaAuthorization": "manage_grants",
    "FilterSchemas": "describe",
    "CreateTable": "create",
    "CreateView": "create",
    # Table operations - DDL
    "ShowTables": "describe",
    "DropTable": "modify",
    "RenameTable": "modify",
    "SetTableComment": "describe",
    "SetTableAuthorization": "manage_grants",
    "FilterTables": "describe",
    # Table operations - DML (data)
    "SelectFromColumns": "select",
    "InsertIntoTable": "modify",
    "UpdateTableColumns": "modify",
    "DeleteFromTable": "modify",
    "TruncateTable": "modify",
    # Column operations
    "ShowColumns": "describe",
    "FilterColumns": "describe",
    "AddColumn": "modify",
    "DropColumn": "modify",
    "RenameColumn": "modify",
    "SetColumnComment": "describe",
    # Column masking
    "MaskColumn": "mask",
    # View operations
    "DropView": "modify",
    "RenameView": "modify",
    "SetViewComment": "describe",
    "RefreshMaterializedView": "modify",
    # System operations
    "ExecuteQuery": "describe",
}

# OpenFGA object type prefixes
OBJECT_TYPE_CATALOG = "catalog"
OBJECT_TYPE_NAMESPACE = "namespace"
OBJECT_TYPE_TABLE = "table"
OBJECT_TYPE_COLUMN = "column"

# OpenFGA user type prefix
USER_TYPE_PREFIX = "user"

# Special catalog for system-level permissions
SYSTEM_CATALOG = "system"

