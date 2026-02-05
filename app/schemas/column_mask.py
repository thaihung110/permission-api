"""
Column mask related Pydantic schemas
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.permission import ResourceSpec, UserType


class ColumnMaskGrant(BaseModel):
    """Request model for granting column mask permission"""

    user_id: str = Field(
        ...,
        description=(
            "User identifier. Format depends on user_type:\n"
            "- user_type='user': 'user:<id>' or 'schema:<catalog.schema>'\n"
            "- user_type='userset': 'role:<role_name>#<relation>'"
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
        description="Resource specification with catalog, schema, table, and column (column is required)",
    )

    @model_validator(mode="after")
    def validate_column_required(self):
        """Validate that column is provided in resource"""
        if not self.resource.column:
            raise ValueError(
                "Column mask grant requires column in resource. "
                'Example: {"catalog": "lakekeeper", "schema": "finance", "table": "user", "column": "email"}'
            )
        if (
            not self.resource.catalog
            or not self.resource.schema
            or not self.resource.table
        ):
            raise ValueError(
                "Column mask grant requires catalog, schema, and table in resource. "
                'Example: {"catalog": "lakekeeper", "schema": "finance", "table": "user", "column": "email"}'
            )
        return self

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "description": "Column mask for a regular user",
                    "value": {
                        "user_id": "analyst",
                        "user_type": "user",
                        "resource": {
                            "catalog": "lakekeeper_bronze",
                            "schema": "finance",
                            "table": "user",
                            "column": "email",
                        },
                    },
                },
                {
                    "description": "Column mask for a role userset",
                    "value": {
                        "user_id": "role:DE#assignee",
                        "user_type": "userset",
                        "resource": {
                            "catalog": "lakekeeper_bronze",
                            "schema": "finance",
                            "table": "user",
                            "column": "email",
                        },
                    },
                },
            ]
        }


class ColumnMaskGrantResponse(BaseModel):
    """Response model for column mask grant"""

    success: bool
    user_id: str
    column_id: str = Field(
        ...,
        description="Column identifier (format: catalog.schema.table.column)",
    )
    object_id: str = Field(
        ...,
        description="OpenFGA object ID (format: column:catalog.schema.table.column)",
    )
    relation: str = Field(
        default="mask", description="Relation name (always 'mask')"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "user_id": "analyst",
                "column_id": "lakekeeper_bronze.finance.user.email",
                "object_id": "column:lakekeeper_bronze.finance.user.email",
                "relation": "mask",
            }
        }


class ColumnMaskListRequest(BaseModel):
    """Request model for listing masked columns"""

    user_id: str = Field(..., description="User identifier")
    tenant_id: Optional[str] = Field(
        None, description="Optional tenant identifier"
    )
    resource: Dict[str, str] = Field(
        ...,
        description="Resource specification with catalog_name, schema_name, table_name",
    )

    @model_validator(mode="after")
    def validate_resource(self):
        """Validate that resource has required fields"""
        catalog_name = self.resource.get("catalog_name") or self.resource.get(
            "catalog"
        )
        schema_name = self.resource.get("schema_name") or self.resource.get(
            "schema"
        )
        table_name = self.resource.get("table_name") or self.resource.get(
            "table"
        )

        if not all([catalog_name, schema_name, table_name]):
            raise ValueError(
                "Column mask list requires catalog_name, schema_name, and table_name in resource. "
                'Example: {"catalog_name": "lakekeeper_bronze", "schema_name": "finance", "table_name": "user"}'
            )
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "analyst",
                "resource": {
                    "catalog_name": "lakekeeper_bronze",
                    "schema_name": "finance",
                    "table_name": "user",
                },
            }
        }


class ColumnMaskListResponse(BaseModel):
    """Response model for listing masked columns"""

    user_id: str
    table_fqn: str = Field(
        ...,
        description="Fully qualified table name (format: catalog.schema.table)",
    )
    masked_columns: List[str] = Field(
        ..., description="List of column names that are masked for this user"
    )
    count: int = Field(..., description="Number of masked columns")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "analyst",
                "table_fqn": "lakekeeper_bronze.finance.user",
                "masked_columns": ["email", "phone_number"],
                "count": 2,
            }
        }


# Batch Column Mask Schemas (for Trino direct integration)


class ColumnResource(BaseModel):
    """Column resource specification from Trino"""

    catalogName: str = Field(..., description="Catalog name")
    schemaName: str = Field(..., description="Schema name")
    tableName: str = Field(..., description="Table name")
    columnName: str = Field(..., description="Column name")
    columnType: str = Field(
        ..., description="Column type (e.g., 'varchar', 'integer')"
    )


class FilterResource(BaseModel):
    """Filter resource containing a column"""

    column: ColumnResource = Field(..., description="Column resource")


class IdentityContext(BaseModel):
    """Identity context from Trino request"""

    user: str = Field(..., description="User identifier")
    groups: List[str] = Field(
        default_factory=list,
        description="List of tenant IDs that the user belongs to (mapped to tenants in OpenFGA)",
    )


class Context(BaseModel):
    """Context from Trino request"""

    identity: IdentityContext = Field(..., description="Identity information")
    softwareStack: Dict[str, Any] = Field(
        default_factory=dict,
        description="Software stack information (e.g., {'trinoVersion': '467'})",
    )


class Action(BaseModel):
    """Action from Trino request"""

    operation: str = Field(
        ..., description="Operation name (e.g., 'GetColumnMask')"
    )
    filterResources: List[FilterResource] = Field(
        ..., description="Array of column resources to check"
    )


class BatchColumnMaskInput(BaseModel):
    """Input wrapper for batch column mask request"""

    context: Context = Field(..., description="Request context")
    action: Action = Field(..., description="Action with filter resources")


class BatchColumnMaskRequest(BaseModel):
    """Request model for batch column mask check (Trino format)"""

    input: BatchColumnMaskInput = Field(..., description="Input data")

    class Config:
        json_schema_extra = {
            "example": {
                "input": {
                    "context": {
                        "identity": {
                            "user": "hung",
                            "groups": [],
                        },
                        "softwareStack": {
                            "trinoVersion": "467",
                        },
                    },
                    "action": {
                        "operation": "GetColumnMask",
                        "filterResources": [
                            {
                                "column": {
                                    "catalogName": "lakekeeper_bronze",
                                    "schemaName": "finance",
                                    "tableName": "user",
                                    "columnName": "phone_number",
                                    "columnType": "varchar",
                                }
                            }
                        ],
                    },
                }
            }
        }


class ViewExpression(BaseModel):
    """View expression for column masking"""

    expression: str = Field(
        ..., description="SQL expression to mask the column (e.g., '******')"
    )


class MaskEntry(BaseModel):
    """Mask entry for a column that needs masking"""

    index: int = Field(
        ..., description="Index of the column in filterResources array"
    )
    viewExpression: ViewExpression = Field(
        ..., description="View expression for masking"
    )


class BatchColumnMaskResponse(BaseModel):
    """Response model for batch column mask check"""

    result: List[MaskEntry] = Field(
        ...,
        description="Array of mask entries for columns that need masking",
        default_factory=list,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "result": [
                    {
                        "index": 2,
                        "viewExpression": {"expression": "******"},
                    }
                ]
            }
        }
