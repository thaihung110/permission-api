"""
Row filter related Pydantic schemas
"""

from typing import Dict, Optional

from pydantic import BaseModel, Field


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
