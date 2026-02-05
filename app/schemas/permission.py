"""
Permission-related Pydantic schemas
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class UserType(str, Enum):
    """User type for OpenFGA tuple user field"""

    USER = "user"
    USERSET = "userset"


class ResourceSpec(BaseModel):
    """Resource specification for grant/revoke operations"""

    catalog: Optional[str] = Field(
        None, description="Catalog name (e.g., 'lakekeeper')"
    )
    schema: Optional[str] = Field(
        None, description="Schema name (e.g., 'finance')"
    )
    table: Optional[str] = Field(None, description="Table name (e.g., 'user')")
    column: Optional[str] = Field(
        None, description="Column name (e.g., 'email')"
    )
    role: Optional[str] = Field(
        None,
        description="Role name for role-based operations (e.g., 'DE', 'Sales')",
    )
    project: Optional[str] = Field(
        None, description="Project name (e.g., 'lakekeeper')"
    )
    tenant: Optional[str] = Field(
        None, description="Tenant name (e.g., 'viettel', 'acme_corp')"
    )


class PermissionCheckRequest(BaseModel):
    """Request model for permission check (from OPA)"""

    user_id: str = Field(
        ..., description="User identifier from Trino (e.g., alice, bob)"
    )
    resource: Dict[str, Any] = Field(
        ...,
        description="Resource object with schema_name, table_name, etc.",
    )
    operation: str = Field(
        ..., description="Trino operation (e.g., SelectFromColumns)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "admin",
                "resource": {
                    "catalog": "lakekeeper",
                    "schema": "finance",
                    "table": "user",
                    "column": "phone_number",
                },
                "operation": "SelectFromColumns",
            }
        }


class PermissionCheckResponse(BaseModel):
    """Response model for permission check"""

    allowed: bool = Field(..., description="Whether the operation is allowed")

    class Config:
        json_schema_extra = {"example": {"allowed": True}}


class ConditionContext(BaseModel):
    """Condition context for row filtering"""

    attribute_name: str = Field(
        ..., description="Attribute name (e.g., 'region', 'department')"
    )
    allowed_values: List[str] = Field(
        ...,
        description="List of allowed values (e.g., ['mien_bac', 'mien_trung'])",
    )


class ConditionSpec(BaseModel):
    """Condition specification for tuple with condition context"""

    name: str = Field(
        ..., description="Condition name (e.g., 'has_attribute_access')"
    )
    context: ConditionContext = Field(
        ...,
        description="Condition context with attribute_name and allowed_values",
    )


class PermissionGrant(BaseModel):
    """Request model for granting permission"""

    user_id: str = Field(
        ...,
        description=(
            "User identifier. Format depends on user_type:\n"
            "- user_type='user': 'user:<id>' (e.g., 'user:alice') or 'schema:<catalog.schema>' "
            "(auto-mapped to warehouse/namespace)\n"
            "- user_type='userset': 'role:<role_name>#<relation>' (e.g., 'role:DE#assignee')"
        ),
    )
    user_type: UserType = Field(
        default=UserType.USER,
        description=(
            "Type of user identifier:\n"
            "- 'user': Regular user or schema resource\n"
            "- 'userset': Role-based userset (format: role:<role_name>#<relation>)"
        ),
    )
    resource: ResourceSpec = Field(
        ...,
        description="Resource specification with catalog, schema, table",
    )
    relation: str = Field(
        ..., description="Relation/permission (e.g., select, ownership, create)"
    )
    condition: Optional[ConditionSpec] = Field(
        None,
        description="Optional condition context for row filtering (e.g., has_attribute_access)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "description": "Catalog-level permission for a regular user",
                    "value": {
                        "user_id": "admin",
                        "user_type": "user",
                        "resource": {
                            "catalog": "lakekeeper",
                        },
                        "relation": "select",
                    },
                },
                {
                    "description": "Table-level permission for a regular user",
                    "value": {
                        "user_id": "admin",
                        "user_type": "user",
                        "resource": {
                            "catalog": "lakekeeper",
                            "schema": "finance",
                            "table": "user",
                        },
                        "relation": "select",
                    },
                },
                {
                    "description": "Grant permission to a role userset",
                    "value": {
                        "user_id": "role:DE#assignee",
                        "user_type": "userset",
                        "resource": {
                            "catalog": "lakekeeper",
                            "schema": "finance",
                        },
                        "relation": "select",
                    },
                },
                {
                    "description": "Grant permission to schema resource (auto-mapped to namespace)",
                    "value": {
                        "user_id": "schema:lakekeeper.finance",
                        "user_type": "user",
                        "resource": {
                            "catalog": "lakekeeper",
                            "schema": "finance",
                            "table": "user",
                        },
                        "relation": "select",
                    },
                },
                {
                    "description": "Row filter policy with condition context",
                    "value": {
                        "user_id": "sale_nam",
                        "user_type": "user",
                        "resource": {},
                        "relation": "viewer",
                        "condition": {
                            "name": "has_attribute_access",
                            "context": {
                                "attribute_name": "region",
                                "allowed_values": ["mien_bac"],
                            },
                        },
                    },
                },
                {
                    "description": "Assign user to a role (grant assignee relation on role)",
                    "value": {
                        "user_id": "alice",
                        "user_type": "user",
                        "resource": {
                            "role": "DE",
                        },
                        "relation": "assignee",
                    },
                },
            ]
        }


class PermissionGrantResponse(BaseModel):
    """Response model for permission grant"""

    success: bool
    user_id: str
    resource_type: str
    resource_id: str
    object_id: str
    relation: str


class PermissionRevoke(BaseModel):
    """Request model for revoking permission"""

    user_id: str = Field(
        ...,
        description=(
            "User identifier. Format depends on user_type:\n"
            "- user_type='user': 'user:<id>' (e.g., 'user:alice') or 'schema:<catalog.schema>' "
            "(auto-mapped to warehouse/namespace)\n"
            "- user_type='userset': 'role:<role_name>#<relation>' (e.g., 'role:DE#assignee')"
        ),
    )
    user_type: UserType = Field(
        default=UserType.USER,
        description=(
            "Type of user identifier:\n"
            "- 'user': Regular user or schema resource\n"
            "- 'userset': Role-based userset (format: role:<role_name>#<relation>)"
        ),
    )
    resource: ResourceSpec = Field(
        ...,
        description="Resource specification with catalog, schema, table",
    )
    relation: str = Field(
        ...,
        description="Relation/permission (e.g., select, ownership, create, viewer)",
    )
    condition: Optional[ConditionSpec] = Field(
        None,
        description="Optional condition context for row filter revocation (provide attribute_name to identify policy)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "description": "Catalog-level permission for a regular user",
                    "value": {
                        "user_id": "admin",
                        "user_type": "user",
                        "resource": {
                            "catalog": "lakekeeper",
                        },
                        "relation": "select",
                    },
                },
                {
                    "description": "Table-level permission for a regular user",
                    "value": {
                        "user_id": "admin",
                        "user_type": "user",
                        "resource": {
                            "catalog": "lakekeeper",
                            "schema": "finance",
                            "table": "user",
                        },
                        "relation": "select",
                    },
                },
                {
                    "description": "Revoke permission from a role userset",
                    "value": {
                        "user_id": "role:DE#assignee",
                        "user_type": "userset",
                        "resource": {
                            "catalog": "lakekeeper",
                            "schema": "finance",
                        },
                        "relation": "select",
                    },
                },
                {
                    "description": "Row filter policy revocation",
                    "value": {
                        "user_id": "hung",
                        "user_type": "user",
                        "resource": {
                            "catalog": "lakekeeper_bronze",
                            "schema": "finance",
                            "table": "user",
                        },
                        "relation": "viewer",
                        "condition": {
                            "name": "has_attribute_access",
                            "context": {
                                "attribute_name": "region",
                                "allowed_values": [],
                            },
                        },
                    },
                },
            ]
        }


class PermissionRevokeResponse(BaseModel):
    """Response model for permission revoke"""

    success: bool
    user_id: str
    resource_type: str
    resource_id: str
    object_id: str
    relation: str
