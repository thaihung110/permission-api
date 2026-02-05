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
    Build OpenFGA user identifier (backward compatible version)

    Args:
        user_id: User ID from Trino (e.g., "alice", "bob")

    Returns:
        OpenFGA user identifier (e.g., "user:alice")
    """
    if ":" in user_id:
        return user_id
    return f"user:{user_id}"


def build_user_identifier_with_type(
    user_id: str, user_type: str = "user"
) -> str:
    """
    Build OpenFGA user identifier based on user_type.

    Args:
        user_id: User identifier. Format depends on user_type:
            - user_type='user':
                - 'user:<id>' (e.g., 'user:alice') - returned as-is
                - 'schema:<catalog.schema>' - mapped to 'namespace:<catalog.schema>'
                - 'catalog:<catalog>' - mapped to 'warehouse:<catalog>'
                - 'table:<catalog.schema.table>' - mapped to 'lakekeeper_table:<catalog.schema.table>'
                - '<id>' (plain) - prefixed with 'user:'
            - user_type='userset':
                - 'role:<role_name>#<relation>' (e.g., 'role:DE#assignee') - returned as-is
                - 'tenant:<tenant_name>#<relation>' (e.g., 'tenant:viettel#member') - returned as-is
        user_type: Type of user identifier ('user' or 'userset')

    Returns:
        OpenFGA user identifier string

    Raises:
        ValueError: If user_type is 'userset' but format is invalid
    """
    if user_type == "userset":
        # Userset format: role:<role_name>#<relation> or tenant:<tenant_name>#<relation>
        # Validate format
        if "#" not in user_id:
            raise ValueError(
                f"Invalid userset format: '{user_id}'. "
                "Expected format: 'role:<role_name>#<relation>' (e.g., 'role:DE#assignee') "
                "or 'tenant:<tenant_name>#<relation>' (e.g., 'tenant:viettel#member')"
            )

        # Check if it starts with valid userset type
        valid_userset_types = ["role:", "tenant:"]
        if not any(
            user_id.startswith(prefix) for prefix in valid_userset_types
        ):
            raise ValueError(
                f"Invalid userset format: '{user_id}'. "
                "Expected format: 'role:<role_name>#<relation>' (e.g., 'role:DE#assignee') "
                "or 'tenant:<tenant_name>#<relation>' (e.g., 'tenant:viettel#member')"
            )

        return user_id

    # user_type == "user" (default)
    if ":" not in user_id:
        # Plain user ID, add user: prefix
        return f"user:{user_id}"

    # Check for schema: prefix and map to namespace:
    if user_id.startswith("schema:"):
        # Map schema:<catalog.schema> to namespace:<catalog.schema>
        schema_path = user_id.replace("schema:", "")
        return f"namespace:{schema_path}"

    # Check for catalog: prefix and map to warehouse:
    if user_id.startswith("catalog:"):
        # Map catalog:<catalog_name> to warehouse:<catalog_name>
        catalog_name = user_id.replace("catalog:", "")
        return f"warehouse:{catalog_name}"

    # Check for table: prefix and map to lakekeeper_table:
    if user_id.startswith("table:"):
        # Map table:<catalog.schema.table> to lakekeeper_table:<catalog.schema.table>
        table_path = user_id.replace("table:", "")
        return f"lakekeeper_table:{table_path}"

    # Already has a colon prefix (user:, namespace:, warehouse:, lakekeeper_table:, etc.)
    return user_id
