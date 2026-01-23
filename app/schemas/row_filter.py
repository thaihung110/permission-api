"""
Row filter related Pydantic schemas
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.permission import ResourceSpec


class RowFilterRequest(BaseModel):
    """Request model for row filter endpoint"""

    user_id: str = Field(..., description="User identifier")
    resource: Dict[str, str] = Field(
        ...,
        description="Resource specification with catalog_name, schema_name, table_name",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "hung",
                "resource": {
                    "catalog_name": "lakekeeper",
                    "schema_name": "bronze",
                    "table_name": "customers",
                },
            }
        }


class RowFilterResponse(BaseModel):
    """Response model for row filter endpoint"""

    filter_expression: Optional[str] = Field(
        None, description="SQL WHERE clause for row filtering"
    )
    has_filter: bool = Field(
        ..., description="Whether a filter should be applied"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "filter_expression": "region IN ('north')",
                "has_filter": True,
            }
        }


class RowFilterPolicyGrant(BaseModel):
    """Request model for granting row filter policy"""

    user_id: str = Field(..., description="User identifier from Trino")
    resource: ResourceSpec = Field(
        ...,
        description="Resource specification with catalog, schema, table (table is required)",
    )
    attribute_name: str = Field(
        ..., description="Attribute name (e.g., 'region', 'department')"
    )
    allowed_values: List[str] = Field(
        ...,
        description="List of allowed values (e.g., ['mien_bac', 'mien_trung'])",
    )

    @model_validator(mode="after")
    def validate_table_required(self):
        """Validate that table is provided in resource"""
        if not self.resource.table:
            raise ValueError(
                "Row filter policy grant requires table in resource. "
                'Example: {"catalog": "lakekeeper_bronze", "schema": "finance", "table": "user"}'
            )
        if (
            not self.resource.catalog
            or not self.resource.schema
            or not self.resource.table
        ):
            raise ValueError(
                "Row filter policy grant requires catalog, schema, and table in resource. "
                'Example: {"catalog": "lakekeeper_bronze", "schema": "finance", "table": "user"}'
            )
        if not self.attribute_name:
            raise ValueError(
                "Row filter policy grant requires attribute_name. "
                'Example: "region"'
            )
        if not self.allowed_values or len(self.allowed_values) == 0:
            raise ValueError(
                "Row filter policy grant requires at least one allowed_value. "
                'Example: ["mien_bac", "mien_trung"]'
            )
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "sale_nam",
                "resource": {
                    "catalog": "lakekeeper_bronze",
                    "schema": "finance",
                    "table": "user",
                },
                "attribute_name": "region",
                "allowed_values": ["mien_bac"],
            }
        }


class RowFilterPolicyGrantResponse(BaseModel):
    """Response model for row filter policy grant"""

    success: bool
    user_id: str
    policy_id: str = Field(
        ...,
        description="Policy identifier (format: catalog.schema.table.attribute_name)",
    )
    object_id: str = Field(
        ...,
        description="OpenFGA object ID (format: row_filter_policy:catalog.schema.table.attribute_name)",
    )
    table_fqn: str = Field(
        ...,
        description="Fully qualified table name (format: catalog.schema.table)",
    )
    attribute_name: str
    relation: str = Field(
        default="viewer", description="Relation name (always 'viewer')"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "user_id": "sale_nam",
                "policy_id": "lakekeeper_bronze.finance.user.region",
                "object_id": "row_filter_policy:lakekeeper_bronze.finance.user.region",
                "table_fqn": "lakekeeper_bronze.finance.user",
                "attribute_name": "region",
                "relation": "viewer",
            }
        }


class RowFilterPolicyListRequest(BaseModel):
    """Request model for listing row filter policies"""

    user_id: str = Field(..., description="User identifier")
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
                "Row filter policy list requires catalog_name, schema_name, and table_name in resource. "
                'Example: {"catalog_name": "lakekeeper_bronze", "schema_name": "finance", "table_name": "user"}'
            )
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "sale_nam",
                "resource": {
                    "catalog_name": "lakekeeper_bronze",
                    "schema_name": "finance",
                    "table_name": "user",
                },
            }
        }


class RowFilterPolicyInfo(BaseModel):
    """Information about a row filter policy"""

    policy_id: str = Field(..., description="Policy identifier")
    attribute_name: str = Field(..., description="Attribute name")
    allowed_values: List[str] = Field(..., description="List of allowed values")


class RowFilterPolicyListResponse(BaseModel):
    """Response model for listing row filter policies"""

    user_id: str
    table_fqn: str = Field(
        ...,
        description="Fully qualified table name (format: catalog.schema.table)",
    )
    policies: List[RowFilterPolicyInfo] = Field(
        ..., description="List of policies that user has access to"
    )
    count: int = Field(..., description="Number of policies")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "sale_nam",
                "table_fqn": "lakekeeper_bronze.finance.user",
                "policies": [
                    {
                        "policy_id": "lakekeeper_bronze.finance.user.region",
                        "attribute_name": "region",
                        "allowed_values": ["mien_bac"],
                    }
                ],
                "count": 1,
            }
        }


# Batch Row Filter Schemas (for Trino direct integration)


class TableResource(BaseModel):
    """Table resource specification from Trino"""

    catalogName: str = Field(..., description="Catalog name")
    schemaName: str = Field(..., description="Schema name")
    tableName: str = Field(..., description="Table name")


class RowFilterResource(BaseModel):
    """Resource wrapper containing a table"""

    table: TableResource = Field(..., description="Table resource")


class RowFilterIdentityContext(BaseModel):
    """Identity context from Trino request"""

    user: str = Field(..., description="User identifier")
    groups: List[str] = Field(default_factory=list, description="User groups")


class RowFilterContext(BaseModel):
    """Context from Trino request"""

    identity: RowFilterIdentityContext = Field(
        ..., description="Identity information"
    )
    softwareStack: Dict[str, Any] = Field(
        default_factory=dict,
        description="Software stack information (e.g., {'trinoVersion': '467'})",
    )


class RowFilterAction(BaseModel):
    """Action from Trino request"""

    operation: str = Field(
        ..., description="Operation name (e.g., 'GetRowFilters')"
    )
    resource: RowFilterResource = Field(..., description="Resource with table")


class BatchRowFilterInput(BaseModel):
    """Input wrapper for batch row filter request"""

    context: RowFilterContext = Field(..., description="Request context")
    action: RowFilterAction = Field(..., description="Action with resource")


class BatchRowFilterRequest(BaseModel):
    """Request model for batch row filter check (Trino format)"""

    input: BatchRowFilterInput = Field(..., description="Input data")

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
                        "operation": "GetRowFilters",
                        "resource": {
                            "table": {
                                "catalogName": "lakekeeper_bronze",
                                "schemaName": "finance",
                                "tableName": "user",
                            }
                        },
                    },
                }
            }
        }


class RowFilterExpression(BaseModel):
    """Row filter expression result"""

    expression: str = Field(..., description="SQL WHERE clause expression")


class BatchRowFilterResponse(BaseModel):
    """Response model for batch row filter check"""

    result: List[RowFilterExpression] = Field(
        ...,
        description="Array of filter expressions (typically one expression)",
        default_factory=list,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "result": [
                    {
                        "expression": "region IN ('north')",
                    }
                ]
            }
        }
