"""
Health check schemas
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    openfga_connected: bool

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "openfga_connected": True,
            }
        }

