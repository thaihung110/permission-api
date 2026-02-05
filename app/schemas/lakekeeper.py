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
    """Column information (internal use)"""

    name: str = Field(..., description="Column name")
    masked: bool = Field(False, description="Whether column is masked")


class RowFilterInfo(BaseModel):
    """Information about a row filter policy"""

    attribute_name: str = Field(
        ..., description="Column name used for filtering"
    )
    filter_expression: str = Field(
        ...,
        description='SQL filter expression (e.g., \'region IN ("north", "south")\')',
    )


class ResourceItem(BaseModel):
    """Resource item in flat list format"""

    name: str = Field(
        ...,
        description=(
            "Resource path: 'warehouse', 'warehouse.namespace', "
            "'warehouse.namespace.table', 'warehouse.namespace.table.column'"
        ),
    )
    permissions: List[str] = Field(
        default_factory=list,
        description=(
            "List of permissions. "
            "For columns: ['mask'] if masked, [] if not. "
            "For other resources: ['create', 'modify', 'select', 'describe']"
        ),
    )
    row_filters: Optional[List[RowFilterInfo]] = Field(
        None,
        description="Row filter policies (only for tables)",
    )


class ListResourcesResponse(BaseModel):
    """Response containing all resources in flat list format"""

    resources: List[ResourceItem] = Field(
        ...,
        description=(
            "Flat list of all resources (warehouses, namespaces, tables, columns). "
            "Each item has: name (resource path) + permissions + row_filters (for tables only)"
        ),
    )
    errors: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Partial errors encountered during resource fetching",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "resources": [
                    {
                        "name": "lakekeeper_demo",
                        "permissions": ["select", "describe"],
                    },
                    {
                        "name": "lakekeeper_demo.finance",
                        "permissions": ["select", "modify"],
                    },
                    {
                        "name": "lakekeeper_demo.finance.user",
                        "permissions": ["select"],
                        "row_filters": [
                            {
                                "attribute_name": "region",
                                "filter_expression": "region IN ('north', 'south')",
                            }
                        ],
                    },
                    {
                        "name": "lakekeeper_demo.finance.user.id",
                        "permissions": [],
                    },
                    {
                        "name": "lakekeeper_demo.finance.user.phone_number",
                        "permissions": ["mask"],
                    },
                    {
                        "name": "lakekeeper_demo.finance.transaction",
                        "permissions": [],
                    },
                    {
                        "name": "lakekeeper_demo.sales",
                        "permissions": ["describe"],
                    },
                ],
                "errors": None,
            }
        }
