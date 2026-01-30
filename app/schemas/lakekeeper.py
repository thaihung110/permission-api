"""
Lakekeeper API schemas
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ListResourcesRequest(BaseModel):
    """Request to list all Lakekeeper resources with user permissions"""

    user_id: str = Field(..., description="User ID to check permissions for")
    catalog: str = Field(
        ..., description="Warehouse name (catalog) to list resources for"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "alice",
                "catalog": "demo",
            }
        }


class ListResourcesResponse(BaseModel):
    """Response containing all resources with user permissions"""

    resources: Dict[str, List[str]] = Field(
        ...,
        description=(
            "Map of resource paths to granted permissions. "
            "Key format: 'warehouse', 'warehouse.namespace', 'warehouse.namespace.table'. "
            "Value: list of permissions ['create', 'modify', 'select', 'describe']. "
            "Empty list means no permissions on that resource."
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
                    "demo": ["select", "describe"],
                    "demo.finance": ["select", "modify"],
                    "demo.finance.user": ["select"],
                    "demo.finance.transaction": [],
                    "demo.sales": ["describe"],
                    "prod": [],
                },
                "errors": [
                    {
                        "resource": "demo.marketing",
                        "error": "Failed to fetch tables: Network timeout",
                    }
                ],
            }
        }
