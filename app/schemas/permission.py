"""
Permission-related Pydantic schemas
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


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
    # Backward compatibility: support namespace as alias for schema
    namespace: Optional[str] = Field(
        None, description="Namespace name (deprecated, use 'schema' instead)"
    )

    @model_validator(mode="after")
    def normalize_schema_namespace(self):
        """Normalize: if namespace is provided but schema is not, copy to schema"""
        if self.namespace and not self.schema:
            self.schema = self.namespace
        return self


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


class PermissionGrant(BaseModel):
    """Request model for granting permission"""

    user_id: str = Field(..., description="User identifier from Trino")
    resource: ResourceSpec = Field(
        ...,
        description="Resource specification with catalog, schema, table",
    )
    relation: str = Field(
        ..., description="Relation/permission (e.g., select, ownership, create)"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "description": "Catalog-level permission (standalone)",
                    "value": {
                        "user_id": "admin",
                        "resource": {
                            "catalog": "lakekeeper",
                        },
                        "relation": "select",
                    },
                },
                {
                    "description": "Table-level permission",
                    "value": {
                        "user_id": "admin",
                        "resource": {
                            "catalog": "lakekeeper",
                            "schema": "finance",
                            "table": "user",
                        },
                        "relation": "select",
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

    user_id: str = Field(..., description="User identifier from Trino")
    resource: ResourceSpec = Field(
        ...,
        description="Resource specification with catalog, schema, table",
    )
    relation: str = Field(
        ..., description="Relation/permission (e.g., select, ownership, create)"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "description": "Catalog-level permission (standalone)",
                    "value": {
                        "user_id": "admin",
                        "resource": {
                            "catalog": "lakekeeper",
                        },
                        "relation": "select",
                    },
                },
                {
                    "description": "Table-level permission",
                    "value": {
                        "user_id": "admin",
                        "resource": {
                            "catalog": "lakekeeper",
                            "schema": "finance",
                            "table": "user",
                        },
                        "relation": "select",
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
