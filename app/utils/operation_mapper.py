"""
Maps Trino operations to OpenFGA relations
"""

from typing import Optional

OPERATION_TO_RELATION_MAP = {
    # Catalog operations (Trino catalogs)
    # Note: CreateCatalog is controlled at the project level via the base
    # relation `create` on project:<project_id>. In the auth model,
    # `can_create_catalog` is defined as `create`, but OpenFGA tuples are
    # written with the base relation `create`, not the computed one.
    "AccessCatalog": "select",
    "ShowCatalogs": "describe",
    "CreateCatalog": "create",
    "DropCatalog": "modify",
    "FilterCatalogs": "describe",
    # Schema operations
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
    "SelectFromColumns": "select",  # Base relation for read access
    "InsertIntoTable": "modify",  # Base relation for write access
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
    # Column masking (explicit mask tuples)
    "MaskColumn": "mask",
    # View operations
    "DropView": "modify",
    "RenameView": "modify",
    "SetViewComment": "describe",
    "RefreshMaterializedView": "modify",
    # System operations
    "ExecuteQuery": "describe",
}


def map_operation_to_relation(operation: str) -> Optional[str]:
    """
    Map a Trino operation to an OpenFGA relation

    Args:
        operation: Trino operation name

    Returns:
        OpenFGA relation name or None if not mapped
    """
    return OPERATION_TO_RELATION_MAP.get(operation)


def build_user_identifier(user_id: str) -> str:
    """
    Build OpenFGA user identifier

    Args:
        user_id: User ID from Trino (e.g., "alice", "bob")

    Returns:
        OpenFGA user identifier (e.g., "user:alice")
    """
    if ":" in user_id:
        return user_id
    return f"user:{user_id}"
