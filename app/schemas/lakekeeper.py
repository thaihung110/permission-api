"""
Lakekeeper API schemas
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ListResourcesRequest(BaseModel):
    """Request to list all Lakekeeper resources with user permissions"""

    user_id: str = Field(..., description="User ID to check permissions for")
    catalog: str = Field(
        ...,
        description=(
            "Trino catalog name (e.g., 'lakekeeper_demo'). "
            "The 'lakekeeper_' prefix will be removed to get the Lakekeeper warehouse name."
        ),
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "alice",
                "catalog": "lakekeeper_demo",
            }
        }


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

    permissions: List[str] = Field(
        ...,
        description="List of permissions user has on this namespace ['create', 'modify', 'select', 'describe']",
    )
    tables: Optional[Dict[str, TableInfo]] = Field(
        None,
        description="Map of table names to TableInfo objects",
    )


class WarehouseInfo(BaseModel):
    """Information about a warehouse (catalog) including namespaces"""

    permissions: List[str] = Field(
        ...,
        description="List of permissions user has on this warehouse ['create', 'modify', 'select', 'describe']",
    )
    namespaces: Optional[Dict[str, NamespaceInfo]] = Field(
        None,
        description="Map of namespace names to NamespaceInfo objects",
    )


class ListResourcesResponse(BaseModel):
    """Response containing all resources with user permissions in nested structure"""

    resources: Dict[str, WarehouseInfo] = Field(
        ...,
        description=(
            "Map of warehouse names to WarehouseInfo objects. "
            "Structure: warehouse -> namespaces -> tables -> columns. "
            "Each level contains permissions and nested resources."
        ),
    )
    errors: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Partial errors encountered during resource fetching",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "resources": {
                    "demo": {
                        "permissions": ["select", "describe"],
                        "namespaces": {
                            "finance": {
                                "permissions": ["select", "modify"],
                                "tables": {
                                    "user": {
                                        "permissions": ["select"],
                                        "columns": [
                                            {"name": "id", "masked": False},
                                            {
                                                "name": "phone_number",
                                                "masked": True,
                                            },
                                        ],
                                        "row_filters": [
                                            {
                                                "attribute_name": "region",
                                                "filter_expression": "region IN ('north', 'south')",
                                            }
                                        ],
                                    },
                                    "transaction": {
                                        "permissions": [],
                                        "columns": None,
                                        "row_filters": None,
                                    },
                                },
                            },
                            "sales": {
                                "permissions": ["describe"],
                                "tables": None,
                            },
                        },
                    },
                    "prod": {
                        "permissions": [],
                        "namespaces": None,
                    },
                },
                "errors": [
                    {
                        "resource": "demo.marketing",
                        "error": "Failed to fetch tables: Network timeout",
                    }
                ],
            }
        }
