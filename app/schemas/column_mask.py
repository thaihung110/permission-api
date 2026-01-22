"""
Column mask related Pydantic schemas
"""

from typing import Dict, List

from pydantic import BaseModel, Field, model_validator

from app.schemas.permission import ResourceSpec


class ColumnMaskGrant(BaseModel):
    """Request model for granting column mask permission"""

    user_id: str = Field(..., description="User identifier from Trino")
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
            "example": {
                "user_id": "analyst",
                "resource": {
                    "catalog": "lakekeeper_bronze",
                    "schema": "finance",
                    "table": "user",
                    "column": "email",
                },
            }
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
