"""
Lakekeeper API schemas
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    """Information about a column"""

    name: str = Field(..., description="Column name")
    masked: bool = Field(
        False, description="Whether column is masked for this user"
    )


class RowFilterInfo(BaseModel):
    """Information about a row filter policy"""

    attribute_name: str = Field(
        ..., description="Column name used for filtering"
    )
    filter_expression: str = Field(
        ...,
        description='SQL filter expression (e.g., \'region IN ("north", "south")\')',
    )


class TableInfo(BaseModel):
    """Information about a table including columns and row filters"""

    name: str = Field(..., description="Table name")
    permissions: List[str] = Field(
        ...,
        description="List of permissions user has on this table ['create', 'modify', 'select', 'describe']",
    )
    columns: Optional[List[ColumnInfo]] = Field(
        None,
        description="List of columns in this table (if table metadata available)",
    )
    row_filters: Optional[List[RowFilterInfo]] = Field(
        None,
        description="List of row filter policies applied to this table for this user",
    )


class NamespaceInfo(BaseModel):
    """Information about a namespace (schema) including tables"""

    name: str = Field(..., description="Namespace name")
    permissions: List[str] = Field(
        ...,
        description="List of permissions user has on this namespace ['create', 'modify', 'select', 'describe']",
    )
    tables: Optional[List[TableInfo]] = Field(
        None,
        description="List of tables in this namespace",
    )


class WarehouseInfo(BaseModel):
    """Information about a warehouse (catalog) including namespaces"""

    name: str = Field(..., description="Warehouse name (catalog name)")
    permissions: List[str] = Field(
        ...,
        description="List of permissions user has on this warehouse ['create', 'modify', 'select', 'describe']",
    )
    namespaces: Optional[List[NamespaceInfo]] = Field(
        None,
        description="List of namespaces in this warehouse",
    )


class ListResourcesResponse(BaseModel):
    """Response containing warehouse with permissions and nested resources"""

    name: str = Field(..., description="Warehouse name (catalog name)")
    permissions: List[str] = Field(
        ...,
        description="List of permissions user has on this warehouse ['create', 'modify', 'select', 'describe']",
    )
    namespaces: Optional[List[NamespaceInfo]] = Field(
        None,
        description="List of namespaces in this warehouse",
    )
    errors: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Partial errors encountered during resource fetching",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "lakekeeper_demo",
                "permissions": ["select", "describe"],
                "namespaces": [
                    {
                        "name": "finance",
                        "permissions": ["select", "modify"],
                        "tables": [
                            {
                                "name": "user",
                                "permissions": ["select"],
                                "columns": [
                                    {"name": "id", "masked": False},
                                    {"name": "phone_number", "masked": True},
                                ],
                                "row_filters": [
                                    {
                                        "attribute_name": "region",
                                        "filter_expression": "region IN ('north', 'south')",
                                    }
                                ],
                            },
                            {
                                "name": "transaction",
                                "permissions": [],
                                "columns": None,
                                "row_filters": None,
                            },
                        ],
                    },
                    {
                        "name": "sales",
                        "permissions": ["describe"],
                        "tables": None,
                    },
                ],
                "errors": [
                    {
                        "resource": "lakekeeper_demo.marketing",
                        "error": "Failed to fetch tables: Network timeout",
                    }
                ],
            }
        }
